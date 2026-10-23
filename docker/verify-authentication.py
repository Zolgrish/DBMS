"""Epic 1.5 real SQL connections; no password reset, business writes or restore.

Run with .venv Python. QLDSV_ADMIN_PASSWORD (current password) or hidden prompt;
requires unused seed account SV00000002. Never uses sa as an app principal.
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
from app.repositories.account_repository import AccountRepository
from app.services.auth_service import AuthService
from app.services.account_service import AccountService
from app.utils import session


STUDENT = os.getenv("QLDSV_VERIFY_STUDENT", "SV00000002")
LECTURER = os.getenv("QLDSV_VERIFY_LECTURER", "GV00000002")


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


def denied(operation, number):
    try:
        operation()
    except pyodbc.Error as error:
        check(re.search(r"\(" + str(number) + r"\)", str(error)) is not None,
              f"Expected SQL rejection {number} was not returned")
    else:
        raise RuntimeError(f"Expected SQL rejection {number}, but operation succeeded")


def delete(connection, name):
    query(connection, "EXEC dbo.sp_XoaTaiKhoan @LoginName=?;", name)


def assert_absent(connection, name):
    rows = query(connection, """
SELECT (SELECT COUNT(*) FROM sys.server_principals WHERE name=?),
       (SELECT COUNT(*) FROM sys.database_principals WHERE name=?);
""", name, name)
    check(tuple(rows[0]) == (0, 0), "Disposable Login/User remains")


def assert_session_identity(name, role):
    with session.qldsv_cursor() as cursor:
        row = cursor.execute("SELECT SUSER_SNAME(), USER_NAME(), @@TRANCOUNT;").fetchone()
        check(tuple(row) == (name, name, 0), "Borrowed QLDSV principal/transaction mismatch")
    check(session.current_user["username"] == name and session.current_user["role"] == role,
          "Published session identity mismatch")
    check(session.require_qldsv_connection().autocommit, "QLDSV must use autocommit")


def main():
    admin = os.getenv("QLDSV_ADMIN_LOGIN", "GV00000001")
    if not os.getenv("QLDSV_ADMIN_PASSWORD") and not sys.stdin.isatty():
        raise RuntimeError("BLOCKED: current Admin password unavailable; no guessing/reset or sa substitution.")
    current_password = os.getenv("QLDSV_ADMIN_PASSWORD") or getpass.getpass("Current Admin SQL password: ")
    temporary_admin = os.getenv("QLDSV_VERIFY_ADMIN", "GV00000003")
    temporary_password = "Auth15#Aa9!" + secrets.token_hex(16)
    control = None
    created = []
    try:
        AuthService().login(admin, current_password)
        # Keep a control session solely for disposable-principal cleanup.
        control = open_sql_connection(admin, current_password)
        current_password = ""
        assert_session_identity(admin, "Admin")
        check(AccountRepository().student_exists(STUDENT), "Seed Student is missing")
        master_rows = query(session.require_master_connection(), "SELECT SUSER_SNAME(), DB_NAME();")
        check(tuple(master_rows[0]) == (admin, "master"), "Admin master principal mismatch")
        assert_absent(control, STUDENT)
        assert_absent(control, temporary_admin)
        assert_absent(control, LECTURER)
        for magv in (temporary_admin, LECTURER):
            check(query(control, "SELECT 1 FROM dbo.Giangvien WHERE MAGV=?;", magv), "Seed MAGV is missing")
        check(query(control, "SELECT OBJECT_ID(N'dbo.TaiKhoan',N'U');")[0][0] is None, "TaiKhoan unexpectedly exists")
        print("PASS bootstrap Admin: application login, identity SP, repository QLDSV and master principals")

        query(control, "EXEC dbo.sp_TaoTaiKhoan @LoginName=?, @Role=?, @Password=?;",
              temporary_admin, "QLDSV_ADMIN", temporary_password)
        created.append(temporary_admin)
        user = AuthService().login(temporary_admin, temporary_password)
        check(user.magv == temporary_admin and user.masv is None, "Admin MAGV mismatch")
        temporary_password = ""
        assert_session_identity(temporary_admin, "Admin")
        check(AccountRepository().student_exists(STUDENT), "Admin repository read failed")
        # Proves pooling is disabled: either owned physical connection prevents
        # DROP LOGIN; after logout both must be gone for DROP to succeed.
        denied(lambda: delete(control, temporary_admin), 52015)
        session.clear_session()
        delete(control, temporary_admin)
        created.remove(temporary_admin)
        assert_absent(control, temporary_admin)
        assert_absent(control, LECTURER)
        print("PASS delegated Admin: app login and logout physically close QLDSV + master sessions")

        query(control, "EXEC dbo.sp_TaoTaiKhoan @LoginName=?, @Role=?;", LECTURER, "QLDSV_GIANGVIEN")
        created.append(LECTURER)
        user = AuthService().login(LECTURER, "Qldsv@123456")
        assert_session_identity(LECTURER, "GiangVien")
        check(user.magv == LECTURER and user.masv is None, "Lecturer trusted MAGV mismatch")
        try:
            session.require_master_connection()
        except session.SessionRequiredError:
            pass
        else:
            raise RuntimeError("Lecturer unexpectedly owns master")
        for operation in (AccountService().find_all_accounts,
                          lambda: AccountService().create_lecturer_account(LECTURER),
                          lambda: AccountService().delete_account(LECTURER)):
            try:
                operation()
            except PermissionError:
                pass
            else:
                raise RuntimeError("Lecturer gained account-management access")
        denied(AccountRepository().find_all_accounts, 52001)
        denied(lambda: delete(control, LECTURER), 52015)
        session.clear_session()
        session.clear_session()
        delete(control, LECTURER)
        created.remove(LECTURER)
        assert_absent(control, LECTURER)
        print("PASS Lecturer: MAGV, SQL identity, no master/account access, physical logout")

        query(control, "EXEC dbo.sp_TaoTaiKhoan @LoginName=?, @Role=?;", STUDENT, "QLDSV_SINHVIEN")
        created.append(STUDENT)
        user = AuthService().login(STUDENT, "123456")
        assert_session_identity(STUDENT, "SinhVien")
        check(user.masv == STUDENT, "Student trusted MASV mismatch")
        with session.qldsv_cursor() as cursor:
            memberships = cursor.execute("""
SELECT ISNULL(IS_SRVROLEMEMBER(N'QLDSV_ACCOUNT_ADMIN'),-1),
       ISNULL(IS_SRVROLEMEMBER(N'dbcreator'),-1),
       ISNULL(IS_SRVROLEMEMBER(N'sysadmin'),-1),
       ISNULL(IS_SRVROLEMEMBER(N'securityadmin'),-1);
""").fetchone()
            check(tuple(memberships) == (0, 0, 0, 0), "Student server role mismatch")
        try:
            session.require_master_connection()
        except session.SessionRequiredError:
            pass
        else:
            raise RuntimeError("Student unexpectedly owns a master connection")
        with session.qldsv_cursor() as cursor:
            rows = cursor.execute("EXEC dbo.sp_SinhVien_XemDiem;").fetchall()
        actual = [(str(row[0]).strip(), int(row[2]), row[3]) for row in rows]
        expected = [(str(row[0]).strip(), int(row[1]), row[2]) for row in query(
            control, "SELECT MAMH, LAN, DIEM FROM dbo.Diem WHERE MASV=? ORDER BY MAMH, LAN;", STUDENT)]
        check(actual == expected and len(actual) > 0, "Own-score SP differs from trusted Student data")

        def student_sql(sql):
            with session.qldsv_cursor() as cursor:
                cursor.execute(sql)

        for sql in (
            "SELECT * FROM dbo.Diem;",
            "INSERT dbo.Diem(MASV,MAMH,LAN,DIEM) SELECT NULL,NULL,NULL,NULL WHERE 1=0;",
            "UPDATE dbo.Diem SET DIEM=NULL WHERE 1=0;",
            "DELETE dbo.Diem WHERE 1=0;",
        ):
            denied(lambda sql=sql: student_sql(sql), 229)
        denied(lambda: AccountRepository().student_exists(STUDENT), 229)
        denied(lambda: student_sql("EXEC dbo.sp_TaoTaiKhoan @LoginName=NULL,@Role=NULL;"), 229)
        denied(lambda: student_sql("EXEC dbo.sp_XoaTaiKhoan @LoginName=NULL;"), 229)
        denied(lambda: delete(control, STUDENT), 52015)
        session.clear_session()
        delete(control, STUDENT)
        created.remove(STUDENT)
        assert_absent(control, STUDENT)
        print("PASS Student: app principal/MASV, self scores, direct SELECT/DML denied, physical logout")
        check(query(control, "SELECT OBJECT_ID(N'dbo.TaiKhoan',N'U');")[0][0] is None,
              "Unexpected legacy account table")
        print("PASS Epic 1.5 real-principal verification; disposable principals removed")
    finally:
        current_password = temporary_password = ""
        session.clear_session()
        try:
            if control is not None:
                for name in reversed(created):
                    delete(control, name)
                    assert_absent(control, name)
        finally:
            session.close_connection(control)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        if not os.getenv("QLDSV_ADMIN_PASSWORD") and not sys.stdin.isatty():
            print("BLOCKED: current Admin password unavailable; no guessing/reset or sa substitution.", file=sys.stderr)
            raise SystemExit(2) from None
        # Driver diagnostics can include connection details; never echo them.
        print("FAIL Epic 1.5 verification; check current Admin credentials, target and disposable account availability.", file=sys.stderr)
        raise SystemExit(1) from None
