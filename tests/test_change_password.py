"""Epic 1.7 repository, service, SQL, UI and offline verifier contracts."""

import importlib.util
import os
from pathlib import Path
import re
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pyodbc
from PySide6.QtCore import QTimer
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QMessageBox, QPushButton

from app.config import database
from app.models.user import User
from app.repositories.account_repository import AccountRepository
from app.services.change_password_service import ChangePasswordError, ChangePasswordService
from app.ui.admin_dashboard import AdminDashboard
from app.ui.change_password import ChangePasswordDialog
from app.ui.lecturer_dashboard import LecturerDashboard
from app.ui.student_dashboard import StudentDashboard
from app.utils import session


ROOT = Path(__file__).resolve().parents[1]
ADMIN = User("GV00000001", "Admin", None, "GV00000001", True)


class Cursor:
    def __init__(self, error=None):
        self.error = error
        self.calls = []
        self.closed = 0

    def execute(self, sql, *params):
        self.calls.append((sql, params))
        if self.error is not None:
            raise self.error
        return self

    def close(self):
        self.closed += 1


class Connection:
    def __init__(self, error=None):
        self.statement = Cursor(error)
        self.closed = 0

    def cursor(self):
        return self.statement

    def close(self):
        self.closed += 1


class SessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.connection = Connection()
        session.set_authenticated(ADMIN, self.connection)

    def tearDown(self):
        session.clear_session()
        self.application.processEvents()


class PasswordRepositoryTests(SessionTests):
    def test_only_old_and_new_parameters_on_borrowed_qldsv_cursor(self):
        session.clear_session()
        self.connection = Connection()
        master = Connection()
        session.set_authenticated(ADMIN, self.connection, master)
        with patch.object(database, "open_sql_connection") as open_connection, \
                patch.object(database.pyodbc, "connect") as connect, \
                patch.object(session, "master_cursor") as master_cursor:
            self.assertIsNone(AccountRepository().update_password(" old' ", " new' "))
        open_connection.assert_not_called()
        connect.assert_not_called()
        master_cursor.assert_not_called()
        self.assertEqual(self.connection.statement.calls, [
            ("EXEC dbo.sp_DoiMatKhau @OldPassword=?, @NewPassword=?;", (" old' ", " new' ")),
        ])
        sql, parameters = self.connection.statement.calls[0]
        self.assertNotIn("dbo.TaiKhoan", sql)
        self.assertNotIn("LoginName", sql)
        self.assertNotIn(ADMIN.username, parameters)
        self.assertEqual((self.connection.closed, self.connection.statement.closed), (0, 1))
        self.assertEqual(master.closed, 0)

    def test_sql_failure_closes_only_cursor_and_propagates(self):
        self.connection.statement.error = pyodbc.Error("42000", "safe (52102)")
        with self.assertRaises(pyodbc.Error):
            AccountRepository().update_password("old", "new")
        self.assertEqual((self.connection.closed, self.connection.statement.closed), (0, 1))


class PasswordServiceTests(SessionTests):
    def setUp(self):
        super().setUp()
        self.repository = Mock(spec=AccountRepository)
        self.service = ChangePasswordService(self.repository)

    def test_success_uses_only_old_and_new_and_ignores_no_rowcount(self):
        self.repository.update_password.return_value = None
        self.assertIsNone(self.service.change_password("old", "new", "new"))
        self.repository.update_password.assert_called_once_with("old", "new")

    def test_session_required_before_repository(self):
        for identity_only in (False, True):
            with self.subTest(identity_only=identity_only):
                session.clear_session()
                if identity_only:
                    session.set_current_user(ADMIN)
                with self.assertRaisesRegex(ChangePasswordError, "đăng nhập lại"):
                    self.service.change_password("old", "new", "new")
        self.repository.update_password.assert_not_called()

    def test_empty_fields_and_mismatch(self):
        for old, new, confirm, expected in (
            ("", "new", "new", "Mật khẩu hiện tại không được để trống"),
            ("old", "", "", "Mật khẩu mới không được để trống"),
            ("old", "new", "", "Vui lòng xác nhận"),
            ("old", "new", "different", "không khớp"),
        ):
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(ChangePasswordError, expected):
                    self.service.change_password(old, new, confirm)
        self.repository.update_password.assert_not_called()

    def test_exact_limit_including_supplementary_utf16(self):
        for password in ("a" * 128, "😀" * 64, "a" * 126 + "😀"):
            with self.subTest(units=len(password.encode("utf-16-le")) // 2):
                self.repository.reset_mock()
                self.service.change_password(password, password, password)
                self.repository.update_password.assert_called_once_with(password, password)

    def test_over_limit_old_or_new_counts_utf16_units(self):
        for password in ("a" * 129, "😀" * 65, "a" * 127 + "😀"):
            for old, new in ((password, "new"), ("old", password)):
                with self.subTest(units=len(password.encode("utf-16-le")) // 2, old_over=old == password):
                    with self.assertRaisesRegex(ChangePasswordError, "128 đơn vị UTF-16"):
                        self.service.change_password(old, new, new)
        self.repository.update_password.assert_not_called()

    def test_invalid_unicode_is_safe_without_exception_context(self):
        for old, new in (("\ud800", "new"), ("old", "\udc00")):
            try:
                self.service.change_password(old, new, new)
            except ChangePasswordError as error:
                self.assertIn("Unicode không hợp lệ", str(error))
                self.assertIsNone(error.__context__)
                self.assertIsNone(error.__cause__)
            else:
                self.fail("Invalid Unicode was accepted")
        self.repository.update_password.assert_not_called()

    def test_spaces_are_data_and_sql_owns_complexity(self):
        for old, new in ((" old' ", " new' "), (" ", " "), ("x", "y")):
            self.repository.reset_mock()
            self.service.change_password(old, new, new)
            self.repository.update_password.assert_called_once_with(old, new)

    def test_52101_invalidates_identity_connections_and_emits_once(self):
        for with_master in (False, True):
            with self.subTest(with_master=with_master):
                connection = Connection()
                master = Connection() if with_master else None
                session.set_authenticated(ADMIN, connection, master)
                self.repository.reset_mock()
                self.repository.update_password.side_effect = pyodbc.Error(
                    "42000", "private-driver-details old-secret new-secret (52101)")
                invalidated = QSignalSpy(session.events.invalidated)
                with patch("logging.exception") as log:
                    try:
                        self.service.change_password("old-secret", "new-secret", "new-secret")
                    except ChangePasswordError as error:
                        self.assertEqual(str(error), self.service.SQL_ERRORS[52101])
                        self.assertIsNone(error.__context__)
                        self.assertIsNone(error.__cause__)
                        self.assertNotIn("secret", repr(error))
                        self.assertNotIn("private-driver", repr(error))
                    else:
                        self.fail("Invalid SQL identity reported success")
                    log.assert_not_called()
                self.assertIsNone(session.current_user)
                self.assertEqual(connection.closed, 1)
                if master is not None:
                    self.assertEqual(master.closed, 1)
                self.assertEqual(invalidated.count(), 1)
                self.repository.update_password.assert_called_once_with("old-secret", "new-secret")

    def test_nonidentity_sql_errors_are_safe_and_preserve_session(self):
        for number in (52102, 52103, 52104, 52199, 50000):
            with self.subTest(number=number):
                invalidated = QSignalSpy(session.events.invalidated)
                self.repository.update_password.side_effect = pyodbc.Error(
                    "42000", f"private-driver-details old-secret new-secret ({number})")
                with patch("logging.exception") as log:
                    try:
                        self.service.change_password("old-secret", "new-secret", "new-secret")
                    except ChangePasswordError as error:
                        self.assertEqual(str(error), self.service.SQL_ERRORS.get(number, self.service.SQL_ERRORS[52104]))
                        self.assertIsNone(error.__context__)
                        self.assertIsNone(error.__cause__)
                        self.assertNotIn("secret", repr(error))
                        self.assertNotIn("private-driver", repr(error))
                        # Even a retained safe traceback has no local password values.
                        frame = error.__traceback__.tb_next.tb_frame
                        for key in ("current_password", "new_password", "confirm_password"):
                            self.assertEqual(frame.f_locals[key], "")
                    else:
                        self.fail("SQL failure reported success")
                    log.assert_not_called()
                self.assertIsNotNone(session.current_user)
                self.assertIs(session.require_qldsv_connection(), self.connection)
                self.assertEqual(self.connection.closed, 0)
                self.assertEqual(invalidated.count(), 0)

    def test_repository_session_required_becomes_safe_relogin_error(self):
        self.repository.update_password.side_effect = session.SessionRequiredError("private diagnostic")
        with self.assertRaisesRegex(ChangePasswordError, "đăng nhập lại") as caught:
            self.service.change_password("old", "new", "new")
        self.assertNotIn("private", str(caught.exception))

    def test_real_borrowed_cursor_connection_loss_invalidates_session(self):
        invalidated = QSignalSpy(session.events.invalidated)
        self.connection.statement.error = pyodbc.OperationalError("08S01", "private connection detail")
        with self.assertRaisesRegex(ChangePasswordError, "đăng nhập lại") as caught:
            ChangePasswordService().change_password("old", "new", "new")
        self.assertNotIn("private", str(caught.exception))
        self.assertIsNone(session.current_user)
        self.assertEqual((self.connection.closed, self.connection.statement.closed), (1, 1))
        self.assertEqual(invalidated.count(), 1)

    def test_no_password_retained_and_session_remains_active(self):
        before = session.current_user.copy()
        self.service.change_password("old-secret", "new-secret", "new-secret")
        self.assertEqual(session.current_user, before)
        self.assertIs(session.require_qldsv_connection(), self.connection)
        self.assertEqual(self.connection.closed, 0)
        self.assertEqual(set(vars(self.service)), {"_accounts"})
        self.assertFalse(any("password" in key.lower() for key in vars(session)))
        self.assertFalse(any("password" in key.lower() for key in ADMIN.__slots__))


class PasswordUITests(SessionTests):
    def test_all_three_dashboards_can_open_password_dialog(self):
        for user, dashboard_type in (
            (ADMIN, AdminDashboard),
            (User("GV00000002", "GiangVien", None, "GV00000002", True), LecturerDashboard),
            (User("SV00000002", "SinhVien", "SV00000002", None, True), StudentDashboard),
        ):
            with self.subTest(role=user.role):
                session.set_current_user(user)
                dashboard = dashboard_type(user)
                inspections = []

                def inspect_dialog():
                    dialogs = [w for w in QApplication.topLevelWidgets()
                               if isinstance(w, ChangePasswordDialog) and w.isVisible()]
                    for dialog in dialogs:
                        inspections.append((dialog.parent() is dashboard, len(dialog.findChildren(QLineEdit))))
                        dialog.reject()

                QTimer.singleShot(0, inspect_dialog)
                next(button for button in dashboard.findChildren(QPushButton)
                     if button.text() == "Đổi mật khẩu").click()
                self.assertEqual(inspections, [(True, 3)])
                dashboard.close()

    def test_three_masked_inputs_with_128_limit(self):
        dialog = ChangePasswordDialog()
        try:
            fields = dialog.findChildren(QLineEdit)
            self.assertEqual(len(fields), 3)
            for field in fields:
                self.assertEqual(field.echoMode(), QLineEdit.EchoMode.Password)
                self.assertEqual(field.maxLength(), 128)
        finally:
            dialog.close()

    def test_submit_clears_all_fields_before_success_or_safe_failure_message(self):
        for failure in (False, True):
            with self.subTest(failure=failure):
                connection = Connection(error=pyodbc.Error("42000", "private SQL old-secret new-secret (52102)")
                                        if failure else None)
                session.set_authenticated(ADMIN, connection)
                dialog = ChangePasswordDialog()
                dialog.show()
                dialog.current_password_input.setText("old-secret")
                dialog.new_password_input.setText("new-secret")
                dialog.confirm_password_input.setText("new-secret")

                def inspect_message(*args):
                    self.assertTrue(all(field.text() == "" for field in dialog.findChildren(QLineEdit)))
                    self.assertNotIn("private", args[2])
                    self.assertNotIn("secret", args[2])

                with patch.object(QMessageBox, "warning", side_effect=inspect_message) as warning, \
                        patch.object(QMessageBox, "information", side_effect=inspect_message) as information:
                    dialog._change_password()
                self.assertEqual(warning.call_count, int(failure))
                self.assertEqual(information.call_count, int(not failure))
                if failure:
                    self.assertTrue(dialog.isVisible())
                    self.assertEqual(warning.call_args.args[2], ChangePasswordService.SQL_ERRORS[52102])
                else:
                    self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
                    self.assertEqual(information.call_args.args[2], "Đổi mật khẩu thành công.")
                self.assertIs(session.require_qldsv_connection(), connection)
                dialog.close()


class PasswordSQLContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / "database/StoredProcedures_Security.sql").read_text(encoding="utf-8")
        cls.sql = re.sub(r"/\*.*?\*/|--[^\n]*", "", source, flags=re.S)
        cls.procedure = re.search(r"CREATE PROCEDURE dbo.sp_DoiMatKhau\b(.*?)\nGO", cls.sql, re.S).group(1)

    def test_drop_create_and_only_two_max_password_inputs(self):
        self.assertIn("DROP PROCEDURE dbo.sp_DoiMatKhau;", self.sql)
        signature = self.procedure.split("\nAS\n", 1)[0]
        self.assertEqual(re.findall(r"@\w+", signature), ["@OldPassword", "@NewPassword"])
        self.assertEqual(signature.count("nvarchar(max)"), 2)

    def test_caller_mapping_sid_and_system_principal_guards(self):
        for token in ("SUSER_SNAME()", "ORIGINAL_LOGIN()", "USER_NAME()", "@Login<>ORIGINAL_LOGIN()",
                      "@Login<>@User", "dp.name=sp.name AND dp.sid=sp.sid", "sp.name=@Login",
                      "sp.type='S'", "sp.principal_id<>1", "sp.sid=SUSER_SID()", "dp.type='S'",
                      "dp.authentication_type=1", "dp.principal_id>4", "THROW 52101"):
            self.assertIn(token, self.procedure)

    def test_one_direct_role_owned_by_dbo_and_real_business_entity(self):
        for token in ("QLDSV_ADMIN", "QLDSV_GIANGVIEN", "QLDSV_SINHVIEN", "@Admin+@Lecturer+@Student<>1",
                      "@Admin NOT IN (0,1)", "@Lecturer NOT IN (0,1)", "@Student NOT IN (0,1)",
                      "SELECT COUNT(*) FROM sys.database_role_members",
                      "member_principal_id=DATABASE_PRINCIPAL_ID(@User))<>1", "r.name=@BusinessRole",
                      "r.type='R'", "r.owning_principal_id=DATABASE_PRINCIPAL_ID(N'dbo')",
                      "DATALENGTH(@User)<>20", "dbo.Giangvien WHERE MAGV=@User", "dbo.Sinhvien WHERE MASV=@User"):
            self.assertIn(token, self.procedure)

    def test_password_validation_and_secret_cleanup_in_both_paths(self):
        for password in ("OldPassword", "NewPassword"):
            self.assertIn(f"@{password} IS NULL OR DATALENGTH(@{password}) NOT BETWEEN 2 AND 256", self.procedure)
            self.assertGreaterEqual(self.procedure.count(f"SET @{password}=NULL;"), 2)
        self.assertGreaterEqual(self.procedure.count("SET @sql=NULL;"), 2)
        self.assertNotRegex(self.procedure, r"\b(?:LTRIM|RTRIM|TRIM)\s*\(")

    def test_one_unconditional_alter_login_with_quoted_identifier_and_both_escaped_passwords(self):
        statement = self.procedure.split("SET @sql=", 1)[1].split("SET @OldPassword=NULL;", 1)[0]
        self.assertEqual(self.procedure.count("ALTER LOGIN"), 1)
        self.assertEqual(self.procedure.count("SET @sql="), 3)  # build + success/failure clearing
        self.assertIn("N'ALTER LOGIN '+QUOTENAME(@Login)", statement)
        self.assertIn("WITH PASSWORD = N", statement)
        self.assertIn("OLD_PASSWORD = N", statement)
        for password in ("OldPassword", "NewPassword"):
            self.assertIn(f"REPLACE(@{password},N'''',N'''''')", statement)
        self.assertNotRegex(statement, r"\b(?:IF|CASE|WHEN)\b")
        self.assertIn("EXEC (@sql);", self.procedure)

    def test_safe_error_family_and_no_policy_or_privilege_mutation(self):
        for number in (52101, 52102, 52103, 52104):
            self.assertIn("THROW " + str(number), self.procedure)
        for forbidden in ("ERROR_MESSAGE", "sp_password", "dbo.TaiKhoan", "EXECUTE AS", "CHECK_POLICY",
                          "CHECK_EXPIRATION", "BEGIN TRANSACTION", "KILL", "ALTER ANY LOGIN", "PRINT"):
            self.assertNotIn(forbidden, self.procedure)

    def test_sql_error_mapping_separates_lockout_and_unexpected_validation(self):
        catch = self.procedure.split("BEGIN CATCH", 1)[1]
        # Assert the actual complete native-error dispatch, including fallthrough.
        dispatch = catch.split("IF @Error IN (52101,52102,52103,52104) THROW;", 1)[1]
        self.assertRegex(dispatch, r"(?s)^\s*IF @Error=15151\s+THROW 52102, '[^']*', 1;"
                         r"\s*IF @Error BETWEEN 15114 AND 15119\s+THROW 52103, '[^']*', 1;"
                         r"\s*THROW 52104, '[^']*', 1;\s*END CATCH;\s*END;\s*$")
        self.assertNotIn("15113", dispatch)
        self.assertNotIn("15120", dispatch)


    def test_object_specific_execute_for_three_roles_and_no_unsafe_global_grants(self):
        for role in ("QLDSV_ADMIN", "QLDSV_GIANGVIEN", "QLDSV_SINHVIEN"):
            self.assertIn(f"GRANT EXECUTE ON OBJECT::dbo.sp_DoiMatKhau TO {role};", self.sql)
        self.assertNotRegex(self.sql, r"GRANT\s+EXECUTE\s+ON\s+SCHEMA")
        self.assertNotIn("EXECUTE AS OWNER", self.sql)
        self.assertNotIn("dbo.TaiKhoan", self.sql)
        self.assertNotIn("sp_password", self.sql)


class PasswordBootstrapContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / "database/Security.sql").read_text(encoding="utf-8")
        cls.sql = re.sub(r"/\*.*?\*/|--[^\n]*", "", source, flags=re.S)

    def _allowlist(self, error_message):
        guard = self.sql.split("THROW 51005, '" + error_message, 1)[0].rsplit("IF EXISTS", 1)[1]
        expression = guard.split("AND NOT", 1)[1].lstrip()
        self.assertTrue(expression.startswith("("))
        depth = 0
        for index, character in enumerate(expression):
            depth += (character == "(") - (character == ")")
            if depth == 0:
                return guard, re.sub(r"\s+", "", expression[1:index])
        self.fail("Unbalanced drift-preflight allowlist")

    def test_lecturer_preflight_allows_only_connect_identity_and_password_execute(self):
        guard, allowlist = self._allowlist("SEC-05: Lecturer has unexpected ownership/grants.")
        self.assertEqual(allowlist,
                         "(p.class=0ANDp.permission_name=N'CONNECT'ANDp.state='G')OR"
                         "(p.class=1ANDp.major_idIN(ISNULL(OBJECT_ID(N'dbo.sp_ThongTinDangNhap'),-1),"
                         "ISNULL(OBJECT_ID(N'dbo.sp_DoiMatKhau'),-1))ANDp.permission_name=N'EXECUTE'ANDp.state='G')")
        for token in ("sys.schemas", "sys.objects", "u.name=N'QLDSV_GIANGVIEN'",
                      "IS_ROLEMEMBER(N'QLDSV_GIANGVIEN',u.name)=1", "p.state IN ('G','W') AND NOT"):
            self.assertIn(token, guard)

    def test_student_preflight_allows_only_connect_identity_scores_and_password_execute(self):
        guard, allowlist = self._allowlist("SEC-05: Unexpected Student grants exist.")
        self.assertEqual(allowlist,
                         "(p.class=0ANDp.permission_name=N'CONNECT')OR"
                         "(p.class=1ANDp.major_idIN(ISNULL(OBJECT_ID(N'dbo.sp_SinhVien_XemDiem'),-1),"
                         "ISNULL(OBJECT_ID(N'dbo.sp_ThongTinDangNhap'),-1),"
                         "ISNULL(OBJECT_ID(N'dbo.sp_DoiMatKhau'),-1))ANDp.permission_name=N'EXECUTE'ANDp.state='G')")
        self.assertIn("DATABASE_PRINCIPAL_ID(@Student), DATABASE_PRINCIPAL_ID(N'QLDSV_SINHVIEN')", guard)
        self.assertIn("p.state IN ('G', 'W') AND NOT", guard)

    def test_no_schema_database_or_unscoped_execute_grant(self):
        self.assertNotRegex(self.sql, r"(?i)\bGRANT\s+EXECUTE\s+(?:TO\b|ON\s+(?:SCHEMA|DATABASE)\s*::)")


class PasswordVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("verify_change_password", ROOT / "docker/verify-change-password.py")
        cls.verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.verifier)

    def test_missing_current_admin_credential_fails_before_connecting(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(self.verifier.sys.stdin, "isatty", return_value=False), \
                patch.object(self.verifier, "open_sql_connection") as connect, \
                patch.object(self.verifier, "AuthService") as auth:
            with self.assertRaisesRegex(RuntimeError, "current Admin password unavailable"):
                self.verifier.main()
        connect.assert_not_called()
        auth.assert_not_called()

    def test_sa_is_rejected_before_application_authentication(self):
        with patch.dict(os.environ, {"QLDSV_ADMIN_LOGIN": "sa", "QLDSV_ADMIN_PASSWORD": "unit-only"}), \
                patch.object(self.verifier, "AuthService") as auth, \
                patch.object(self.verifier, "open_sql_connection") as connect:
            with self.assertRaisesRegex(RuntimeError, "system logins are forbidden"):
                self.verifier.main()
        auth.assert_not_called()
        connect.assert_not_called()

    def test_cleanup_uses_original_sid_even_when_verification_fails(self):
        verifier = self.verifier
        control = Mock()
        sid = b"created-sid"
        calls = []

        def fake_query(connection, sql, *params):
            calls.append((sql, params))
            if "EXEC dbo.sp_TaoTaiKhoan" in sql:
                return [(sid,)]
            return []

        with patch.dict(os.environ, {"QLDSV_ADMIN_PASSWORD": "unit-only"}), \
                patch.object(verifier, "AuthService") as auth, \
                patch.object(verifier, "open_sql_connection", return_value=control), \
                patch.object(verifier, "preflight"), patch.object(verifier, "query", side_effect=fake_query), \
                patch.object(verifier, "assert_absent"), patch.object(verifier, "verify_self_change", side_effect=RuntimeError("stop")), \
                patch("builtins.print"):
            auth.return_value.login.return_value = ADMIN
            with self.assertRaisesRegex(RuntimeError, "stop"):
                verifier.main()
        deletions = [(sql, params) for sql, params in calls if "EXEC dbo.sp_XoaTaiKhoan" in sql]
        self.assertEqual(len(deletions), 1)
        self.assertIn("@ExpectedSid=?", deletions[0][0])
        self.assertEqual(deletions[0][1][1], sid)
        control.close.assert_called_once()

    def test_three_role_verification_requires_fresh_old_rejection_and_new_success(self):
        verifier = self.verifier
        for role in ("QLDSV_ADMIN", "QLDSV_GIANGVIEN", "QLDSV_SINHVIEN"):
            with self.subTest(role=role), \
                    patch.object(verifier, "AuthService") as auth, \
                    patch.object(verifier, "ChangePasswordService") as change, \
                    patch.object(verifier, "assert_identity") as identity, \
                    patch.object(verifier, "account_snapshot", return_value=(b"sid", b"sid", role != "QLDSV_SINHVIEN", 0, 0, 1)), \
                    patch.object(verifier, "query", return_value=[(1 if role == "QLDSV_ADMIN" else 0,)]), \
                    patch.object(session, "require_qldsv_connection", return_value=Mock()), \
                    patch.object(session, "clear_session") as logout, patch("builtins.print"):
                auth.return_value.login.side_effect = [
                    User("disposable", "Admin", None, "disposable", True), Mock(),
                    verifier.InvalidCredentialsError("expected fresh-old denial"), Mock(),
                ]
                change.return_value.SQL_ERRORS = ChangePasswordService.SQL_ERRORS
                change.return_value.change_password.side_effect = [
                    ChangePasswordError(ChangePasswordService.SQL_ERRORS[52102]), None,
                ]
                verifier.verify_self_change(Mock(), "disposable", role, b"sid", "initial")
                changes = change.return_value.change_password.call_args_list
                self.assertEqual(len(changes), 2)
                self.assertNotEqual(changes[0].args[0], "initial")
                self.assertEqual(changes[1].args[0], "initial")
                new = changes[1].args[1]
                self.assertEqual(changes[1].args[1:], (new, new))
                self.assertEqual([call.args for call in auth.return_value.login.call_args_list], [
                    ("disposable", "initial"), ("disposable", "initial"),
                    ("disposable", "initial"), ("disposable", new),
                ])
                self.assertEqual(identity.call_count, 4)
                self.assertEqual(logout.call_count, 3)

    def test_preexisting_principal_is_rejected_without_any_account_mutation(self):
        verifier = self.verifier
        with patch.object(verifier, "query", side_effect=[[], [(1, 0)]]) as query:
            with self.assertRaisesRegex(RuntimeError, "preexisting principals are never reused"):
                verifier.preflight(Mock(), [("SV00000002", "QLDSV_SINHVIEN")])
        self.assertFalse(any("EXEC dbo.sp_TaoTaiKhoan" in call.args[1] or "EXEC dbo.sp_XoaTaiKhoan" in call.args[1]
                             for call in query.call_args_list))

    def test_cleanup_error_is_visible_and_never_retried_by_name(self):
        verifier = self.verifier
        sid = b"original-creation-sid"

        def fake_query(connection, sql, *params):
            if "EXEC dbo.sp_TaoTaiKhoan" in sql:
                return [(sid,)]
            if "EXEC dbo.sp_XoaTaiKhoan" in sql:
                raise pyodbc.Error("42000", "private SID mismatch")
            return []

        with patch.dict(os.environ, {"QLDSV_ADMIN_PASSWORD": "unit-only"}), \
                patch.object(verifier, "AuthService") as auth, \
                patch.object(verifier, "open_sql_connection"), patch.object(verifier, "preflight"), \
                patch.object(verifier, "query", side_effect=fake_query) as query, \
                patch.object(verifier, "verify_self_change", side_effect=RuntimeError("stop")), \
                patch("builtins.print") as output:
            auth.return_value.login.return_value = ADMIN
            with self.assertRaisesRegex(RuntimeError, "cleanup incomplete"):
                verifier.main()
        deletions = [call for call in query.call_args_list if "sp_XoaTaiKhoan" in call.args[1]]
        self.assertEqual(len(deletions), 1)
        self.assertEqual(deletions[0].args[3], sid)
        self.assertIn("@ExpectedSid=?", deletions[0].args[1])
        self.assertTrue(any("Cleanup failed" in str(call.args) for call in output.call_args_list))
        self.assertFalse(any("private SID" in str(call.args) for call in output.call_args_list))

    def test_uncertain_creation_has_visible_cleanup_failure_without_delete_by_name(self):
        verifier = self.verifier
        with patch.dict(os.environ, {"QLDSV_ADMIN_PASSWORD": "unit-only"}), \
                patch.object(verifier, "AuthService") as auth, \
                patch.object(verifier, "open_sql_connection"), patch.object(verifier, "preflight"), \
                patch.object(verifier, "query", return_value=[]) as query, patch("builtins.print") as output:
            auth.return_value.login.return_value = ADMIN
            with self.assertRaisesRegex(RuntimeError, "cleanup incomplete"):
                verifier.main()
        self.assertFalse(any("sp_XoaTaiKhoan" in call.args[1] for call in query.call_args_list))
        self.assertTrue(any("creation SID unavailable" in str(call.args) for call in output.call_args_list))


if __name__ == "__main__":
    unittest.main()
