"""Epic 1.6 real-principal app verification; no business writes, resets or KILL.

Uses DB_* targets and current QLDSV_ADMIN_PASSWORD or a hidden prompt. Without
an environment password, prompts again for the explicit Admin login after the
Student logout. QLDSV_VERIFY_STUDENT defaults to unused seed MASV SV00000002.
Ownership comes from the create procedure's SID output; SQL guards every
disposable deletion against that exact SID inside its delete transaction.
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
from app.services.account_service import AccountService, AccountServiceError
from app.services.auth_service import AuthService
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


def assert_absent(connection, name, database_user=None):
    database_user = database_user or name
    row = query(connection, """
SELECT (SELECT COUNT(*) FROM sys.server_principals WHERE name=?),
       (SELECT COUNT(*) FROM sys.database_principals WHERE name=?);
""", name, database_user)[0]
    check(tuple(row) == (0, 0), "Disposable Login/User is not absent; existing principals are never reused")


def assert_managed(connection, name, role, database_user=None):
    database_user = database_user or name
    rows = query(connection, """
SELECT sp.sid, sl.is_disabled, sl.is_policy_checked
FROM sys.server_principals sp
JOIN sys.sql_logins sl ON sl.principal_id=sp.principal_id
JOIN sys.database_principals dp ON dp.sid=sp.sid AND dp.name=?
WHERE sp.name=? AND sp.type='S' AND dp.type='S' AND dp.authentication_type=1;
""", database_user, name)
    check(len(rows) == 1 and not rows[0][1], "Login/User mapping or enabled status mismatch")
    check(bool(rows[0][2]) == (role in {"QLDSV_ADMIN", "QLDSV_GIANGVIEN"}), "Password policy mismatch")
    database_roles = query(connection, """
SELECT r.name FROM sys.database_role_members rm
JOIN sys.database_principals r ON r.principal_id=rm.role_principal_id
JOIN sys.database_principals u ON u.principal_id=rm.member_principal_id WHERE u.name=?;
""", database_user)
    check({row[0] for row in database_roles} == {role}, "Business role mismatch")
    server_roles = query(connection, """
SELECT r.name FROM sys.server_role_members rm
JOIN sys.server_principals r ON r.principal_id=rm.role_principal_id
JOIN sys.server_principals u ON u.principal_id=rm.member_principal_id WHERE u.name=?;
""", name)
    expected = {"QLDSV_ACCOUNT_ADMIN", "dbcreator"} if role == "QLDSV_ADMIN" else set()
    check({row[0] for row in server_roles} == expected, "Technical server-role membership mismatch")
    return rows[0][0]


def expect_service_error(operation, number):
    try:
        operation()
    except AccountServiceError as error:
        check(str(error) == AccountService.SQL_ERRORS[number], "Unexpected service error translation")
    else:
        raise RuntimeError("An account operation unexpectedly succeeded")


def expect_sql_error(operation, number):
    try:
        operation()
    except pyodbc.Error as error:
        check(re.search(r"\b" + str(number) + r"\b", " ".join(map(str, error.args))) is not None,
              "Unexpected SQL rejection")
    else:
        raise RuntimeError("SQL boundary unexpectedly allowed the operation")


def login_admin(name, *, cleanup_connection=False):
    if not os.getenv("QLDSV_ADMIN_PASSWORD") and not sys.stdin.isatty():
        raise RuntimeError("BLOCKED: current Admin password unavailable; no guessing/reset or sa substitution.")
    password = os.getenv("QLDSV_ADMIN_PASSWORD") or getpass.getpass("Current Admin SQL password: ")
    try:
        user = AuthService().login(name, password)
        check(user.role == "Admin", "Verifier requires a real Admin")
        return open_sql_connection(name, password) if cleanup_connection else None
    finally:
        password = ""


def main():
    admin = os.getenv("QLDSV_ADMIN_LOGIN", "GV00000001")
    student = os.getenv("QLDSV_VERIFY_STUDENT", "SV00000002")
    demo = os.getenv("QLDSV_STUDENT_LOGIN", "SV00000001")
    temporary_admin = os.getenv("QLDSV_VERIFY_ADMIN", "GV00000003")
    lecturer = os.getenv("QLDSV_VERIFY_LECTURER", "GV00000002")
    temporary_admin_login = os.getenv("QLDSV_VERIFY_ADMIN_LOGIN", "QLDSV_VERIFY_ADMIN_ALIAS")
    lecturer_login = os.getenv("QLDSV_VERIFY_LECTURER_LOGIN", "QLDSV_VERIFY_LECTURER_ALIAS")
    admin_user = os.getenv("QLDSV_ADMIN_USERNAME") or admin
    demo_user = os.getenv("QLDSV_STUDENT_USERNAME") or demo
    temporary_password = "Accounts16#Aa9!" + secrets.token_hex(16)
    control = active = None
    owned: dict[str, bytes] = {}
    unverified_created: set[str] = set()
    try:
        control = login_admin(admin, cleanup_connection=True)
        service = AccountService()
        accounts = service.find_all_accounts()
        check(any(a.username == admin_user and a.login_name == admin and a.role == "Admin" for a in accounts), "Current Admin missing from list")
        check(any(a.username == demo_user and a.login_name == demo and a.role == "SinhVien" for a in accounts), "Demo Student missing from list")
        check(query(control, "SELECT OBJECT_ID(N'dbo.TaiKhoan',N'U');")[0][0] is None,
              "Run this verifier against the target database without the legacy account table")
        check(AccountRepository().student_exists(student), "Disposable Student business row does not exist")
        assert_absent(control, student)
        assert_absent(control, temporary_admin)
        assert_absent(control, temporary_admin_login, temporary_admin)
        assert_absent(control, lecturer)
        assert_absent(control, lecturer_login, lecturer)
        for magv in (temporary_admin, lecturer):
            check(AccountRepository().lecturer_exists(magv), "Disposable MAGV business row does not exist")
        expect_service_error(lambda: service.delete_account(admin), 52014)
        expect_sql_error(lambda: AccountRepository().delete_account(admin), 52014)
        print("PASS Admin app login, SQL metadata list and self-delete boundaries")

        sid = service.create_account("Admin", temporary_password, magv=temporary_admin, login_name=temporary_admin_login)
        unverified_created.add(temporary_admin_login)
        check(isinstance(sid, bytes) and bool(sid), "Create did not return an ownership SID")
        owned[temporary_admin_login] = sid
        unverified_created.remove(temporary_admin_login)
        check(assert_managed(control, temporary_admin_login, "QLDSV_ADMIN", temporary_admin) == owned[temporary_admin_login],
              "Managed Admin SID changed during validation")
        wrong_sid = b"\x00" if sid != b"\x00" else b"\x01"
        expect_sql_error(lambda: query(
            control, "EXEC dbo.sp_XoaTaiKhoan @LoginName=?, @ExpectedSid=?;", temporary_admin_login, wrong_sid
        ), 52016)
        check(assert_managed(control, temporary_admin_login, "QLDSV_ADMIN", temporary_admin) == owned[temporary_admin_login],
              "ExpectedSid rejection did not preserve principal/memberships")
        active = open_sql_connection(temporary_admin_login, temporary_password)
        temporary_password = ""
        expect_service_error(lambda: service.delete_account(temporary_admin_login), 52015)
        check(assert_managed(control, temporary_admin_login, "QLDSV_ADMIN", temporary_admin) == owned[temporary_admin_login],
              "Active-session rejection did not preserve principal/memberships")
        check(query(active, "SELECT 1;")[0][0] == 1, "Target connection was interrupted")
        session.close_connection(active)
        active = None
        AccountRepository().delete_account(temporary_admin_login, expected_sid=owned[temporary_admin_login])
        assert_absent(control, temporary_admin_login, temporary_admin)
        assert_absent(control, lecturer)
        del owned[temporary_admin_login]
        print("PASS Admin service create, memberships, active-session rollback and SID-guarded delete")

        sid = service.create_student_account(student)
        unverified_created.add(student)
        check(isinstance(sid, bytes) and bool(sid), "Create did not return an ownership SID")
        owned[student] = sid
        unverified_created.remove(student)
        check(assert_managed(control, student, "QLDSV_SINHVIEN") == owned[student],
              "Managed Student SID changed during validation")
        user = AuthService().login(student, "123456")
        check(user.role == "SinhVien" and user.masv == student, "Default Student authentication failed")
        expect_sql_error(AccountRepository().find_all_accounts, 52001)
        expect_sql_error(lambda: AccountRepository().create_account(temporary_admin, None, "QLDSV_ADMIN"), 229)
        expect_sql_error(lambda: AccountRepository().delete_account(student), 229)
        for operation in (service.find_all_accounts,
                          lambda: service.create_student_account(student),
                          lambda: service.delete_account(student)):
            try:
                operation()
            except PermissionError:
                pass
            else:
                raise RuntimeError("Student service authorization unexpectedly succeeded")
        session.clear_session()
        # Explicit user authentication after logout, never an automatic reconnect.
        login_admin(admin)
        AccountRepository().delete_account(student, expected_sid=owned[student])
        assert_absent(control, student)
        del owned[student]
        print("PASS Student service create, SQL default password login, denials, logout and SID-guarded delete")
        sid = service.create_account("GiangVien", magv=lecturer, login_name=lecturer_login)
        unverified_created.add(lecturer_login)
        check(isinstance(sid, bytes) and bool(sid), "Create did not return an ownership SID")
        owned[lecturer_login] = sid
        unverified_created.remove(lecturer_login)
        check(assert_managed(control, lecturer_login, "QLDSV_GIANGVIEN", lecturer) == owned[lecturer_login],
              "Managed Lecturer SID changed during validation")
        user = AuthService().login(lecturer_login, "Qldsv@123456")
        check(user.role == "GiangVien" and user.magv == lecturer and user.masv is None, "Lecturer login mismatch")
        expect_sql_error(AccountRepository().find_all_accounts, 52001)
        expect_sql_error(lambda: AccountRepository().create_account(lecturer_login, None, "QLDSV_GIANGVIEN", lecturer), 229)
        expect_sql_error(lambda: AccountRepository().delete_account(lecturer_login), 229)
        for operation in (service.find_all_accounts,
                          lambda: service.create_account("GiangVien", magv=lecturer),
                          lambda: service.delete_account(lecturer_login)):
            try:
                operation()
            except PermissionError:
                pass
            else:
                raise RuntimeError("Lecturer service authorization unexpectedly succeeded")
        try:
            session.require_master_connection()
        except session.SessionRequiredError:
            pass
        else:
            raise RuntimeError("Lecturer unexpectedly owns master")
        session.clear_session()
        login_admin(admin)
        AccountRepository().delete_account(lecturer_login, expected_sid=owned[lecturer_login])
        assert_absent(control, lecturer_login, lecturer)
        del owned[lecturer_login]
        print("PASS Lecturer: service create, policy ON, no server roles/master/account access, SID-guarded delete")
        print("PASS Epic 1.6 real-principal verification; all three role types and cleanup")
    finally:
        temporary_password = ""
        session.close_connection(active)
        session.clear_session()
        cleanup_failed = bool(unverified_created)
        try:
            if control is not None:
                for name, sid in reversed(list(owned.items())):
                    try:
                        # Observation handles absence only; SQL is the final identity guard.
                        rows = query(control, "SELECT sid FROM sys.server_principals WHERE name=? AND type='S';", name)
                        database_user = (temporary_admin if name == temporary_admin_login else lecturer if name == lecturer_login else name)
                        if not rows:
                            assert_absent(control, name, database_user)
                            continue
                        query(control, "EXEC dbo.sp_XoaTaiKhoan @LoginName=?, @ExpectedSid=?;", name, sid)
                        assert_absent(control, name, database_user)
                    except Exception:
                        cleanup_failed = True
        finally:
            session.close_connection(control)
        if cleanup_failed:
            raise RuntimeError("Disposable-principal cleanup incomplete; inspect verifier principals") from None


if __name__ == "__main__":
    try:
        main()
    except Exception:
        if not os.getenv("QLDSV_ADMIN_PASSWORD") and not sys.stdin.isatty():
            print("BLOCKED: current Admin password unavailable; no guessing/reset or sa substitution.", file=sys.stderr)
            raise SystemExit(2) from None
        # Never print driver diagnostics, connection strings or passwords.
        print("FAIL Epic 1.6 verification; check credentials, DB_* target, seed availability and disposable-principal cleanup.",
              file=sys.stderr)
        raise SystemExit(1) from None
