"""Epic 1.7 real-principal verification. Run only with separate live-SQL approval.

Uses DB_* and the current application Admin credential from the process or a
hidden prompt. Only disposable SQL accounts for existing business rows change.
No deployment, Docker operation, business writes, password reset or session kill.
"""

import getpass
import os
from pathlib import Path
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.database import open_sql_connection
from app.services.auth_service import AuthService, InvalidCredentialsError
from app.services.change_password_service import ChangePasswordService, ChangePasswordError
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
        parameters = ()
        cursor.close()


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def assert_absent(connection, name):
    rows = query(connection, """
SELECT (SELECT COUNT(*) FROM sys.server_principals WHERE name=?),
       (SELECT COUNT(*) FROM sys.database_principals WHERE name=?);
""", name, name)
    check(len(rows) == 1 and tuple(rows[0]) == (0, 0),
          "Disposable Login/User is not absent; preexisting principals are never reused")


def account_snapshot(connection, name, role, sid):
    rows = query(connection, """
SELECT sp.sid, dp.sid, sl.is_policy_checked, sl.is_expiration_checked, sl.is_disabled,
       (SELECT COUNT(*) FROM sys.database_role_members WHERE member_principal_id=dp.principal_id)
FROM sys.server_principals sp
JOIN sys.sql_logins sl ON sl.principal_id=sp.principal_id
JOIN sys.database_principals dp ON dp.name=sp.name AND dp.sid=sp.sid
JOIN sys.database_role_members rm ON rm.member_principal_id=dp.principal_id
JOIN sys.database_principals r ON r.principal_id=rm.role_principal_id
WHERE sp.name=? AND sp.type='S' AND dp.type='S' AND dp.authentication_type=1 AND r.name=?;
""", name, role)
    check(len(rows) == 1 and rows[0][0] == sid and rows[0][1] == sid
          and not rows[0][4] and rows[0][5] == 1, "Disposable mapping/SID/role changed")
    # Non-Admin callers need no visibility grant on the technical server role.
    memberships = query(connection, """
SELECT r.name FROM sys.server_role_members rm
JOIN sys.server_principals r ON r.principal_id=rm.role_principal_id
JOIN sys.server_principals m ON m.principal_id=rm.member_principal_id
WHERE m.name=?;
""", name)
    expected = {"QLDSV_ACCOUNT_ADMIN", "dbcreator"} if role == "QLDSV_ADMIN" else set()
    server_roles = {row[0] for row in memberships}
    check(server_roles == expected, "Unexpected server-role memberships")
    return tuple(rows[0]) + (tuple(sorted(server_roles)),)


def assert_identity(name, role):
    rows = query(session.require_qldsv_connection(), "EXEC dbo.sp_ThongTinDangNhap;")
    check(len(rows) == 1 and tuple(rows[0]) == (name, name, role), "Business identity/role changed")
    check(not any("password" in key.lower() for key in session.current_user), "Credential retained in session")


def verify_self_change(control, name, role, sid, initial_password):
    new_password = " Change17'Aa9!" + secrets.token_hex(20) + " "
    wrong_password = "Wrong17#Aa9!" + secrets.token_hex(20)
    try:
        user = AuthService().login(name, initial_password)
        check(user.username == name, "Initial application login failed")
        assert_identity(name, role)
        before = account_snapshot(control, name, role, sid)
        expected_policy = role != "QLDSV_SINHVIEN"
        check(bool(before[2]) == expected_policy, "Unexpected initial SQL password policy")
        privileges = query(session.require_qldsv_connection(),
                           "SELECT HAS_PERMS_BY_NAME(NULL,NULL,N'ALTER ANY LOGIN');")[0][0]
        check(privileges == (1 if role == "QLDSV_ADMIN" else 0),
              "Unexpected server privileges for the disposable role")
        service = ChangePasswordService()
        try:
            service.change_password(wrong_password, new_password, new_password)
        except ChangePasswordError as error:
            check(str(error) == service.SQL_ERRORS[52102], "Wrong current password had an unexpected rejection")
        else:
            raise RuntimeError("Wrong OLD_PASSWORD unexpectedly succeeded")
        wrong_password = ""
        session.clear_session()
        AuthService().login(name, initial_password)  # Wrong-old attempt preserved credential.
        assert_identity(name, role)
        active = session.require_qldsv_connection()
        service.change_password(initial_password, new_password, new_password)
        check(session.require_qldsv_connection() is active, "Password change replaced the authenticated session")
        assert_identity(name, role)  # Existing connection remains usable after ALTER LOGIN.
        check(account_snapshot(control, name, role, sid) == before, "Mapping/role/policy changed")
        session.clear_session()
        try:
            AuthService().login(name, initial_password)  # Pooling is disabled by app config.
        except InvalidCredentialsError:
            pass
        else:
            raise RuntimeError("Fresh login with OLD password unexpectedly succeeded")
        initial_password = ""
        AuthService().login(name, new_password)
        new_password = ""
        assert_identity(name, role)
        check(account_snapshot(control, name, role, sid) == before, "Final mapping/role/policy changed")
        print("PASS " + role + ": wrong-old rejected, live session usable, fresh OLD denied/NEW accepted; identity/policy unchanged")
    finally:
        initial_password = new_password = wrong_password = ""
        session.clear_session()


def preflight(control, principals):
    query(control, """
IF CONVERT(int,SERVERPROPERTY('ProductMajorVersion'))<>16
 OR (SELECT compatibility_level FROM sys.databases WHERE database_id=DB_ID())<>160
 OR OBJECT_ID(N'dbo.sp_DoiMatKhau',N'P') IS NULL
 OR (SELECT COUNT(*) FROM sys.parameters WHERE object_id=OBJECT_ID(N'dbo.sp_DoiMatKhau'))<>2
 OR NOT EXISTS(SELECT 1 FROM sys.parameters WHERE object_id=OBJECT_ID(N'dbo.sp_DoiMatKhau') AND name=N'@OldPassword')
 OR NOT EXISTS(SELECT 1 FROM sys.parameters WHERE object_id=OBJECT_ID(N'dbo.sp_DoiMatKhau') AND name=N'@NewPassword')
 OR NOT EXISTS(SELECT 1 FROM sys.parameters WHERE object_id=OBJECT_ID(N'dbo.sp_TaoTaiKhoan') AND name=N'@CreatedSid' AND is_output=1)
 OR NOT EXISTS(SELECT 1 FROM sys.parameters WHERE object_id=OBJECT_ID(N'dbo.sp_XoaTaiKhoan') AND name=N'@ExpectedSid')
    THROW 53110, 'Deploy Epic 1.7 security procedures on the SQL Server 2022 target first.', 1;
IF (SELECT COUNT(*) FROM sys.database_permissions p
    JOIN sys.database_principals r ON r.principal_id=p.grantee_principal_id
    WHERE p.class=1 AND p.major_id=OBJECT_ID(N'dbo.sp_DoiMatKhau') AND p.minor_id=0
      AND p.permission_name=N'EXECUTE' AND p.state='G'
      AND r.name IN(N'QLDSV_ADMIN',N'QLDSV_GIANGVIEN',N'QLDSV_SINHVIEN'))<>3
    THROW 53110, 'All three object-specific password-change grants are required.', 1;
""")
    check(len({name.casefold() for name, _ in principals}) == len(principals), "Disposable identities must be distinct")
    for name, role in principals:
        assert_absent(control, name)
        sql = ("SELECT 1 FROM dbo.Sinhvien WHERE MASV=?;" if role == "QLDSV_SINHVIEN"
               else "SELECT 1 FROM dbo.Giangvien WHERE MAGV=?;")
        check(query(control, sql, name), "Disposable identity requires an existing business row")


def main():
    admin = os.getenv("QLDSV_ADMIN_LOGIN", "GV00000001")
    check(len(admin.encode("utf-16-le")) == 20, "Application Admin must be an existing 10-unit MAGV; system logins are forbidden")
    password = os.getenv("QLDSV_ADMIN_PASSWORD")
    if not password:
        if not sys.stdin.isatty():
            raise RuntimeError("BLOCKED: current Admin password unavailable; no guessing or reset")
        password = getpass.getpass("Current application Admin SQL password: ")
    principals = (
        (os.getenv("QLDSV_VERIFY_STUDENT", "SV00000002"), "QLDSV_SINHVIEN"),
        (os.getenv("QLDSV_VERIFY_LECTURER", "GV00000002"), "QLDSV_GIANGVIEN"),
        (os.getenv("QLDSV_VERIFY_ADMIN", "GV00000003"), "QLDSV_ADMIN"),
    )
    control = None
    owned = {}
    uncertain = set()
    initial_password = ""
    try:
        user = AuthService().login(admin, password)
        check(user.role == "Admin" and user.magv == admin, "Real mapped application Admin required")
        control = open_sql_connection(admin, password)
        password = ""
        preflight(control, principals)  # All prerequisites pass before any mutation.
        session.clear_session()
        for name, role in principals:
            print("Disposable identity: " + name + " (" + role + ")", flush=True)
            initial_password = "123456" if role == "QLDSV_SINHVIEN" else " Initial17'Aa9!" + secrets.token_hex(20) + " "
            uncertain.add(name)
            rows = query(control, """
SET NOCOUNT ON;
DECLARE @CreatedSid varbinary(85);
EXEC dbo.sp_TaoTaiKhoan @LoginName=?,@Role=?,@Password=?,@CreatedSid=@CreatedSid OUTPUT;
SELECT @CreatedSid;
""", name, role, None if role == "QLDSV_SINHVIEN" else initial_password)
            check(len(rows) == 1 and isinstance(rows[0][0], bytes) and bool(rows[0][0]), "Create returned no ownership SID")
            sid = rows[0][0]
            owned[name] = sid
            uncertain.remove(name)
            verify_self_change(control, name, role, sid, initial_password)
            initial_password = ""
        print("PASS Epic 1.7 real-principal checks for all three roles; cleanup follows")
    finally:
        password = initial_password = ""
        session.clear_session()  # Close disposable connections before DROP LOGIN.
        cleanup_failed = bool(uncertain)
        for name in uncertain:
            print("Cleanup blocked: creation SID unavailable for " + name + "; inspect manually, never delete by name", file=sys.stderr)
        try:
            for name, sid in reversed(list(owned.items())):
                try:
                    query(control, "EXEC dbo.sp_XoaTaiKhoan @LoginName=?,@ExpectedSid=?;", name, sid)
                    assert_absent(control, name)
                    print("PASS SID-guarded cleanup: " + name)
                except Exception:
                    cleanup_failed = True
                    print("Cleanup failed for " + name + "; original SID=0x" + sid.hex()
                          + "; no delete-by-name fallback", file=sys.stderr)
        finally:
            session.close_connection(control)
        if cleanup_failed:
            raise RuntimeError("Disposable-principal cleanup incomplete") from None


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Never print raw server/ODBC errors, connection details or credentials.
        print("FAIL/BLOCKED Epic 1.7: check current Admin credential, DB_* target, deployed procedures, unused business identities and cleanup.", file=sys.stderr)
        raise SystemExit(1) from None
