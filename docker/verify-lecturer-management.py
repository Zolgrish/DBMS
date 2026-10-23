"""Future real-principal lecturer regression. Run only after explicit SQL deployment.

Uses current QLDSV_ADMIN_PASSWORD (or a hidden interactive prompt) and DB_*.
No deployment, password resets, session termination, database restore or sa.
Only uniquely named disposable lecturer/account/assignment state is mutated.
"""

import getpass
import os
from pathlib import Path
import re
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pyodbc

from app.config.database import open_sql_connection
from app.services.auth_service import AuthService
from app.services.lecturer_service import LecturerService, LecturerServiceError
from app.utils import session


def query(connection, sql, *parameters):
    cursor = connection.cursor()
    try:
        cursor.execute(sql, *parameters)
        rows = []
        while True:
            if cursor.description is not None:
                rows = cursor.fetchall()
            if not cursor.nextset():
                return rows
    finally:
        cursor.close()


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def expect_sql_error(operation, number):
    try:
        operation()
    except pyodbc.Error as error:
        check(re.search(r"\b" + str(number) + r"\b", " ".join(map(str, error.args))),
              "Unexpected SQL rejection")
    else:
        raise RuntimeError("Expected SQL denial was not returned")


def expect_business_error(operation, number):
    try:
        operation()
    except LecturerServiceError as error:
        check(str(error) == LecturerService.SQL_ERRORS[number], "Unexpected business error")
    else:
        raise RuntimeError("Expected lecturer deletion rejection was not returned")


def assert_absent(connection, magv):
    row = query(connection, """
SELECT (SELECT COUNT(*) FROM dbo.Giangvien WHERE MAGV=?),
       (SELECT COUNT(*) FROM sys.server_principals WHERE name=?),
       (SELECT COUNT(*) FROM sys.database_principals WHERE name=?),
       (SELECT COUNT(*) FROM dbo.PhanCong WHERE MAGV=?);
""", magv, magv, magv, magv)[0]
    check(tuple(row) == (0, 0, 0, 0), "Disposable MAGV/principal state is not absent; existing state is never reused")


def preflight(connection, magv):
    query(connection, """
IF ORIGINAL_LOGIN()<>SUSER_SNAME() OR USER_NAME()<>SUSER_SNAME()
 OR ISNULL(IS_ROLEMEMBER(N'QLDSV_ADMIN'),-1)<>1
 OR ISNULL(IS_ROLEMEMBER(N'QLDSV_GIANGVIEN'),-1)<>0
 OR ISNULL(IS_ROLEMEMBER(N'QLDSV_SINHVIEN'),-1)<>0
 OR ISNULL(IS_SRVROLEMEMBER(N'QLDSV_ACCOUNT_ADMIN'),-1)<>1
 OR ISNULL(IS_SRVROLEMEMBER(N'dbcreator'),-1)<>1
 OR ISNULL(HAS_PERMS_BY_NAME(NULL,NULL,N'ALTER ANY LOGIN'),0)<>1
 OR ISNULL(HAS_PERMS_BY_NAME(DB_NAME(),N'DATABASE',N'CONTROL'),0)<>1
 OR (SELECT COUNT(*) FROM sys.database_principals WHERE type='R'
     AND owning_principal_id=DATABASE_PRINCIPAL_ID(N'dbo')
     AND name IN(N'QLDSV_ADMIN',N'QLDSV_GIANGVIEN',N'QLDSV_SINHVIEN'))<>3
 OR (SELECT COUNT(*) FROM sys.database_role_members
     WHERE member_principal_id=DATABASE_PRINCIPAL_ID(USER_NAME()))<>1
    THROW 53100, 'Verifier requires the deployed three-role mapped application Admin.', 1;
IF OBJECT_ID(N'dbo.sp_GetGiangVien',N'P') IS NULL
 OR OBJECT_ID(N'dbo.sp_ThemGiangVien',N'P') IS NULL
 OR OBJECT_ID(N'dbo.sp_CapNhatGiangVien',N'P') IS NULL
 OR OBJECT_ID(N'dbo.sp_XoaGiangVien',N'P') IS NULL
 OR OBJECT_ID(N'dbo.PhanCong',N'U') IS NULL
 OR NOT EXISTS(SELECT 1 FROM sys.parameters WHERE object_id=OBJECT_ID(N'dbo.sp_TaoTaiKhoan')
               AND name=N'@CreatedSid' AND is_output=1)
 OR NOT EXISTS(SELECT 1 FROM sys.parameters WHERE object_id=OBJECT_ID(N'dbo.sp_XoaTaiKhoan') AND name=N'@ExpectedSid')
 OR NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE parent_object_id=OBJECT_ID(N'dbo.PhanCong')
               AND referenced_object_id=OBJECT_ID(N'dbo.Giangvien') AND is_disabled=0
               AND is_not_trusted=0 AND delete_referential_action=0)
    THROW 53100, 'Lecturer/security procedures and assignment FK must be deployed first.', 1;
""")
    assert_absent(connection, magv)
    rows = query(connection, "SELECT TOP (1) l.MALOP,m.MAMH FROM dbo.Lop l CROSS JOIN dbo.Monhoc m ORDER BY l.MALOP,m.MAMH;")
    check(rows, "Existing class/course required for the disposable assignment")
    return tuple(rows[0])


def main():
    admin = os.getenv("QLDSV_ADMIN_LOGIN", "GV00000001")
    password = os.getenv("QLDSV_ADMIN_PASSWORD")
    if not password:
        if not sys.stdin.isatty():
            raise RuntimeError("BLOCKED: current Admin credential required")
        password = getpass.getpass("Current application Admin SQL password: ")
    magv = "L" + secrets.token_hex(5)[:9].upper()
    control = lecturer_connection = None
    sid = None
    entity_owned = assignment_owned = False
    entity_uncertain = account_uncertain = assignment_uncertain = False
    mutation_started = False
    staff_password = "Lecturer#Aa9!" + secrets.token_hex(16)
    pair = None
    try:
        user = AuthService().login(admin, password)
        check(user.role == "Admin" and user.magv == user.username, "Real mapped application Admin required")
        control = open_sql_connection(admin, password)
        password = ""
        pair = preflight(control, magv)  # No mutation before all prerequisites pass.
        service = LecturerService()
        print("Disposable lecturer MAGV: " + magv, flush=True)
        mutation_started = True
        entity_uncertain = True
        service.create_lecturer(magv, "Verifier", "Staff", True)
        entity_owned, entity_uncertain = True, False
        service.update_lecturer(magv, "Verifier", "Updated", False)
        check(next(v for v in service.find_all_lecturers() if v.magv == magv).ten == "Updated", "Lecturer update mismatch")
        account_uncertain = True
        rows = query(control, """
SET NOCOUNT ON;
DECLARE @CreatedSid varbinary(85);
EXEC dbo.sp_TaoTaiKhoan @LoginName=?,@Role=N'QLDSV_GIANGVIEN',@Password=?,@CreatedSid=@CreatedSid OUTPUT;
SELECT @CreatedSid;
""", magv, staff_password)
        check(len(rows) == 1 and isinstance(rows[0][0], bytes) and bool(rows[0][0]), "Missing account ownership SID")
        sid, account_uncertain = rows[0][0], False
        lecturer_connection = open_sql_connection(magv, staff_password)
        staff_password = ""
        identity = query(lecturer_connection, "EXEC dbo.sp_ThongTinDangNhap;")
        check(tuple(identity[0]) == (magv, magv, "QLDSV_GIANGVIEN"), "Lecturer SQL identity mismatch")
        for sql, args in (
            ("EXEC dbo.sp_GetGiangVien;", ()),
            ("EXEC dbo.sp_ThemGiangVien @MAGV=?,@PHAI=1;", (magv,)),
            ("EXEC dbo.sp_CapNhatGiangVien @MAGV=?,@PHAI=0;", (magv,)),
            ("EXEC dbo.sp_XoaGiangVien @MAGV=?;", (magv,)),
        ):
            expect_sql_error(lambda sql=sql, args=args: query(lecturer_connection, sql, *args), 229)
        expect_business_error(lambda: service.delete_lecturer(magv), 53006)
        session.close_connection(lecturer_connection)
        lecturer_connection = None
        query(control, "EXEC dbo.sp_XoaTaiKhoan @LoginName=?,@ExpectedSid=?;", magv, sid)
        sid = None
        assignment_uncertain = True
        query(control, "INSERT dbo.PhanCong(MAGV,MALOP,MAMH) VALUES(?,?,?);", magv, *pair)
        assignment_owned, assignment_uncertain = True, False
        expect_business_error(lambda: service.delete_lecturer(magv), 53007)
        query(control, "DELETE dbo.PhanCong WHERE MAGV=? AND MALOP=? AND MAMH=?;", magv, *pair)
        assignment_owned = False
        service.delete_lecturer(magv)
        entity_owned = False
        assert_absent(control, magv)
        print("PASS lecturer CRUD, SQL account boundary, real Lecturer denials, assignment guard and SID-safe deletion")
    finally:
        password = staff_password = ""
        session.close_connection(lecturer_connection)
        cleanup_failed = entity_uncertain or account_uncertain or assignment_uncertain
        try:
            if control is not None:
                operations = []
                if sid is not None:
                    operations.append(("EXEC dbo.sp_XoaTaiKhoan @LoginName=?,@ExpectedSid=?;", (magv, sid)))
                if assignment_owned:
                    operations.append(("DELETE dbo.PhanCong WHERE MAGV=? AND MALOP=? AND MAMH=?;", (magv, *pair)))
                if entity_owned:
                    operations.append(("EXEC dbo.sp_XoaGiangVien @MAGV=?;", (magv,)))
                for sql, args in operations:
                    try:
                        query(control, sql, *args)
                    except Exception:
                        cleanup_failed = True
                if mutation_started:
                    try:
                        assert_absent(control, magv)
                    except Exception:
                        cleanup_failed = True
        finally:
            session.close_connection(control)
            session.clear_session()
        if cleanup_failed:
            print("Cleanup incomplete for disposable MAGV: " + magv, file=sys.stderr)
            raise RuntimeError("Disposable cleanup incomplete; inspect MAGV " + magv + ". Never retry account deletion without its original SID.") from None


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("FAIL/BLOCKED lecturer verifier: check current Admin credential, deployed prerequisites and disposable cleanup.", file=sys.stderr)
        raise SystemExit(1) from None
