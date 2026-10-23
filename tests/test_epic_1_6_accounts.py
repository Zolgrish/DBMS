"""Epic 1.6 account metadata, stored-procedure contracts and UI boundaries."""

import os
import importlib.util
from pathlib import Path
import re
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pyodbc
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QLineEdit, QLabel

from app.config import database
from app.models.user import User
from app.repositories.account_repository import AccountRepository
from app.services.account_service import AccountService, AccountServiceError
from app.ui.account_management import AccountFormDialog, AccountManagementDialog
from app.utils import session


ADMIN = User("admin", "Admin", None, None, True)


class Cursor:
    def __init__(self, rows=(), error=None):
        self.rows = list(rows)
        self.error = error
        self.calls = []
        self.closed = 0

    def execute(self, sql, *params):
        self.calls.append((sql, params))
        if self.error:
            raise self.error
        return self

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def close(self):
        self.closed += 1


class Connection:
    def __init__(self, rows=(), error=None):
        self.statement = Cursor(rows, error)
        self.closed = 0

    def cursor(self):
        return self.statement

    def close(self):
        self.closed += 1


class AccountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        session.set_authenticated(ADMIN, Connection())
        self.repository = Mock(spec=AccountRepository)
        self.service = AccountService(self.repository)

    def tearDown(self):
        session.clear_session()
        self.application.processEvents()

    def test_metadata_list_maps_business_roles_names_and_sql_disabled_status(self):
        connection = Connection([
            ("GV00000002", "QLDSV_GIANGVIEN", None, "GV00000002", False, None, None, "Le", "Lan"),
            ("GV00000001", "QLDSV_ADMIN", None, "GV00000001", True, None, None, " Tran ", " Binh "),
            ("SV00000002", "QLDSV_SINHVIEN", "SV00000002", None, False, " Nguyen ", " An ", None, None),
        ])
        session.set_authenticated(ADMIN, connection)
        with patch.object(database.pyodbc, "connect") as connect:
            accounts = AccountRepository().find_all_accounts()
            connect.assert_not_called()
        self.assertEqual(accounts, [
            User("GV00000002", "GiangVien", None, "GV00000002", True, "Le Lan"),
            User("GV00000001", "Admin", None, "GV00000001", False, "Tran Binh"),
            User("SV00000002", "SinhVien", "SV00000002", None, True, "Nguyen An"),
        ])
        sql = connection.statement.calls[0][0]
        for source in ("sys.server_principals", "sys.sql_logins", "sys.database_principals",
                       "sys.database_role_members", "dbo.Sinhvien", "dbo.Giangvien"):
            self.assertIn(source, sql)
        self.assertNotIn("dbo.TaiKhoan", sql)
        self.assertIn("sp.sid = dp.sid", sql)
        self.assertIn("sp.name = dp.name", sql)
        self.assertIn("authentication_type = 1", sql)
        self.assertIn("COUNT(*)", sql)
        self.assertEqual((connection.closed, connection.statement.closed), (0, 1))

    def test_repository_listing_has_fail_closed_sql_guard_before_select(self):
        connection = Connection()
        session.set_authenticated(ADMIN, connection)
        AccountRepository().find_all_accounts()
        sql = connection.statement.calls[0][0]
        guard, query = sql.split("THROW 52001", 1)
        for check in ("ISNULL(IS_ROLEMEMBER(N'QLDSV_ADMIN'), -1) <> 1",
                      "ISNULL(IS_ROLEMEMBER(N'QLDSV_SINHVIEN'), -1) <> 0",
                      "ISNULL(IS_ROLEMEMBER(N'QLDSV_GIANGVIEN'), -1) <> 0",
                      "ORIGINAL_LOGIN() <> SUSER_SNAME()", "USER_NAME() <> SUSER_SNAME()"):
            self.assertIn(check, guard)
        self.assertIn("SELECT", query)

    def test_repository_propagates_sql_denial_even_with_python_admin_identity(self):
        connection = Connection(error=pyodbc.Error("42000", "Only mapped Admin (52001)"))
        session.set_authenticated(ADMIN, connection)
        with self.assertRaises(pyodbc.Error):
            AccountRepository().find_all_accounts()
        self.assertIsNotNone(session.current_user)

    def test_repository_create_uses_only_parameterized_security_procedure(self):
        for role, password in (("QLDSV_ADMIN", "unit-password"), ("QLDSV_GIANGVIEN", "unit-password"), ("QLDSV_SINHVIEN", None)):
            with self.subTest(role=role):
                sid = b"created-by-procedure"
                connection = Connection([(sid,)])
                session.set_authenticated(ADMIN, connection)
                self.assertIs(AccountRepository().create_account("target", password, role), sid)
                self.assertEqual(len(connection.statement.calls), 1)
                sql, params = connection.statement.calls[0]
                self.assertEqual(params, ("target", role, password))
                self.assertIn("EXEC dbo.sp_TaoTaiKhoan", sql)
                self.assertRegex(sql, r"@CreatedSid\s*=\s*@CreatedSid\s+OUTPUT")
                self.assertRegex(sql, r"SELECT\s+@CreatedSid\s*;")
                self.assertNotIn("sys.server_principals", sql)
                self.assertEqual((connection.closed, connection.statement.closed), (0, 1))

    def test_repository_delete_uses_only_parameterized_security_procedure(self):
        connection = Connection()
        session.set_authenticated(ADMIN, connection)
        for expected_sid in (None, b"owned"):
            with self.subTest(expected_sid=expected_sid):
                AccountRepository().delete_account("target", expected_sid=expected_sid)
                self.assertEqual(connection.statement.calls[-1], (
                    "EXEC dbo.sp_XoaTaiKhoan @LoginName=?, @ExpectedSid=?;", ("target", expected_sid),
                ))

    def test_default_repository_delete_sends_null_expected_sid(self):
        connection = Connection()
        session.set_authenticated(ADMIN, connection)
        AccountRepository().delete_account("target")
        self.assertEqual(connection.statement.calls[0][1], ("target", None))

    def test_staff_create_derives_magv_and_accepts_default_or_custom_password(self):
        self.repository.create_account.return_value = b"staff-owned"
        for role in ("Admin", "GiangVien"):
            for password in (None, "", "unit-password"):
                with self.subTest(role=role, custom=bool(password)):
                    self.repository.reset_mock()
                    result = self.service.create_account(role, password, magv=" gv00000002 ")
                    self.assertEqual(result, b"staff-owned")
                    self.repository.create_account.assert_called_once_with(
                        "GV00000002", password or None, "QLDSV_" + ("ADMIN" if role == "Admin" else "GIANGVIEN"))
                    self.repository.lecturer_exists.assert_not_called()
        self.repository.reset_mock()
        self.service.create_lecturer_account("gv00000002")
        self.repository.create_account.assert_called_once_with("GV00000002", None, "QLDSV_GIANGVIEN")
        with self.assertRaises(TypeError):
            self.service.create_account(username="unrelated", role="Admin", magv="GV00000002")

    def test_student_create_and_integration_api_send_null_password(self):
        self.repository.create_account.return_value = b"student-owned"
        self.assertEqual(self.service.create_account("SinhVien", masv="sv00000002"),
                         b"student-owned")
        self.repository.create_account.assert_called_once_with("SV00000002", None, "QLDSV_SINHVIEN")
        self.repository.reset_mock()
        self.assertEqual(self.service.create_student_account(" sv00000002 "), b"student-owned")
        self.repository.create_account.assert_called_once_with("SV00000002", None, "QLDSV_SINHVIEN")
        self.repository.student_exists.assert_not_called()
        self.assertNotIn("exists_username", AccountRepository.__dict__)

    def test_invalid_role_identity_or_password_is_rejected_before_create(self):
        cases = (
            dict(role="Other", magv="GV00000002"),
            dict(role="Admin"), dict(role="GiangVien"), dict(role="SinhVien"),
            dict(role="SinhVien", masv="SV00000002", password="123456"),
            dict(role="SinhVien", masv="SV00000002", magv="GV00000002"),
            dict(role="Admin", masv="SV00000002", magv="GV00000002"),
            dict(role="GiangVien", masv="SV00000002", magv="GV00000002"),
        )
        for kwargs in cases:
            with self.subTest(role=kwargs["role"]):
                with self.assertRaises(AccountServiceError):
                    self.service.create_account(**kwargs)
        self.repository.create_account.assert_not_called()

    def test_sql_missing_lecturer_is_translated_for_both_staff_roles(self):
        self.repository.create_account.side_effect = pyodbc.Error("42000", "private (52017)")
        for role in ("Admin", "GiangVien"):
            with self.assertRaisesRegex(AccountServiceError, "MAGV"):
                self.service.create_account(role, magv="GV99999999")

    def test_create_sql_errors_are_safe_and_specific_without_logging_diagnostics(self):
        expected = {52001: "quyền", 52002: "đăng nhập", 52003: "Vai trò", 52004: "tồn tại",
                    52005: "User", 52006: "Mật khẩu", 52007: "MASV", 52008: "role", 52009: "chính sách"}
        for number, text in expected.items():
            with self.subTest(number=number):
                self.repository.create_account.side_effect = pyodbc.Error("42000", f"sensitive-driver-detail ({number})")
                with patch("logging.exception") as log:
                    with self.assertRaisesRegex(AccountServiceError, text) as caught:
                        self.service.create_account("Admin", "pw", magv="GV00000002")
                    log.assert_not_called()
                self.assertNotIn("sensitive-driver-detail", str(caught.exception))

    def test_delete_calls_repository_and_self_delete_never_reaches_it(self):
        self.service.delete_account("target")
        self.repository.delete_account.assert_called_once_with("target")
        self.repository.reset_mock()
        with self.assertRaisesRegex(AccountServiceError, "đang đăng nhập"):
            self.service.delete_account("ADMIN")
        self.repository.delete_account.assert_not_called()

    def test_delete_sql_errors_include_active_session_and_missing_target(self):
        for number, text in {52010: "tồn tại", 52011: "mapping", 52012: "role", 52013: "sở hữu",
                             52014: "đang đăng nhập", 52015: "đăng xuất", 52016: "thay đổi"}.items():
            with self.subTest(number=number):
                self.repository.delete_account.side_effect = pyodbc.Error("42000", f"private ({number})")
                with self.assertRaisesRegex(AccountServiceError, text) as caught:
                    self.service.delete_account("target")
                self.assertNotIn("private", str(caught.exception))

    def test_unknown_sql_error_is_safe(self):
        self.repository.find_all_accounts.side_effect = pyodbc.Error("42000", "private SQL diagnostic")
        with self.assertRaises(AccountServiceError) as caught:
            self.service.find_all_accounts()
        self.assertNotIn("private", str(caught.exception))

    def test_blank_delete_name_is_rejected_before_repository_access(self):
        with self.assertRaises(AccountServiceError):
            self.service.delete_account("  ")
        self.repository.delete_account.assert_not_called()

    def test_session_required_error_is_translated_without_any_connection_attempt(self):
        session.set_current_user(ADMIN)
        with patch.object(database.pyodbc, "connect") as connect:
            with self.assertRaisesRegex(AccountServiceError, "đăng nhập lại"):
                AccountService().find_all_accounts()
            connect.assert_not_called()

    def test_guest_and_student_cannot_list_create_or_delete(self):
        for user in (None, User("SV00000002", "SinhVien", "SV00000002", None, True),
                     User("GV00000002", "GiangVien", None, "GV00000002", True)):
            session.set_authenticated(user, None) if user else session.clear_session()
            for method, args in (("find_all_accounts", ()), ("create_account", ("Admin", "pw", "", "GV00000002")),
                                 ("create_student_account", ("SV00000002",)), ("delete_account", ("target",))):
                with self.subTest(user=user, method=method):
                    with self.assertRaises(PermissionError):
                        getattr(self.service, method)(*args)
        self.assertEqual(self.repository.mock_calls, [])

    def test_connection_loss_invalidates_every_account_operation_without_reconnect(self):
        for method, args in (("find_all_accounts", ()), ("create_account", ("Admin", "pw", "", "GV00000002")),
                             ("create_student_account", ("SV00000002",)), ("delete_account", ("target",)),
                             ("create_account", ("GiangVien", "pw", "", "GV00000001"))):
            with self.subTest(method=method, username=args[0] if args else ""):
                qldsv, master = Connection(error=pyodbc.Error("08S01", "lost")), Connection()
                session.set_authenticated(ADMIN, qldsv, master)
                with patch.object(database.pyodbc, "connect") as connect:
                    with self.assertRaisesRegex(AccountServiceError, "đăng nhập lại"):
                        getattr(AccountService(), method)(*args)
                    connect.assert_not_called()
                self.assertIsNone(session.current_user)
                self.assertEqual((qldsv.closed, master.closed), (1, 1))

    def test_unrelated_value_error_is_not_swallowed(self):
        for method, args, repository_method in (
            ("find_all_accounts", (), "find_all_accounts"),
            ("create_account", ("Admin", "pw", "", "GV00000002"), "create_account"),
            ("delete_account", ("target",), "delete_account"),
            ("create_account", ("GiangVien", "pw", "", "GV00000001"), "create_account"),
        ):
            with self.subTest(method=method):
                error = ValueError("unrelated")
                getattr(self.repository, repository_method).side_effect = error
                with self.assertRaises(ValueError) as caught:
                    getattr(self.service, method)(*args)
                self.assertIs(caught.exception, error)

    def test_form_has_three_roles_no_username_and_only_applicable_identity(self):
        values = []
        form = AccountFormDialog("Thêm tài khoản", values.append)
        self.addCleanup(form.close)
        self.assertEqual([form.role_combo.itemText(i) for i in range(form.role_combo.count())],
                         ["Admin", "GiangVien", "SinhVien"])
        self.assertIsNone(form.findChild(QLineEdit, "accountUsernameInput"))
        self.assertFalse(hasattr(form, "username_input"))
        self.assertNotIn("Username", [x.text() for x in form.findChildren(QLabel)])
        for role in ("Admin", "GiangVien", "SinhVien"):
            form.role_combo.setCurrentText(role)
            student = role == "SinhVien"
            self.assertEqual(form.masv_input.isEnabled(), student)
            self.assertEqual(form.masv_input.isHidden(), not student)
            self.assertEqual(form.magv_input.isEnabled(), not student)
            self.assertEqual(form.magv_input.isHidden(), student)
        form.password_input.setText("programmatic-override")
        form.masv_input.setText("sv00000002")
        self.assertEqual(form.masv_input.text(), "SV00000002")
        form._save()
        self.assertEqual(values[0], dict(role="SinhVien", masv="SV00000002", magv="", password=None))
        self.assertEqual(form.password_input.text(), "")

    def test_staff_form_submits_magv_and_clears_password_before_callback(self):
        for role in ("Admin", "GiangVien"):
            for password in ("", "unit-password"):
                with self.subTest(role=role, custom=bool(password)):
                    values = []
                    form = AccountFormDialog("Thêm tài khoản", lambda data: (
                        self.assertEqual(form.password_input.text(), ""),
                        values.append(data), self.service.create_account(**data)
                    ))
                    self.addCleanup(form.close)
                    form.role_combo.setCurrentText(role)
                    form.magv_input.setText("gv00000002")
                    self.assertEqual(form.magv_input.text(), "GV00000002")
                    form.password_input.setText(password)
                    form._save()
                    self.assertEqual(values[0], dict(role=role, masv="", magv="GV00000002", password=password or None))
                    self.repository.create_account.assert_called_with(
                        "GV00000002", password or None, AccountService.SQL_ROLES[role])

    def _dialog(self):
        self.repository.find_all_accounts.return_value = [User("other", "Admin", None, None, True)]
        dialog = AccountManagementDialog(self.service)
        self.addCleanup(dialog.close)
        dialog.account_table.selectRow(0)
        return dialog

    def test_list_ui_has_add_delete_close_without_edit_or_lock(self):
        dialog = self._dialog()
        labels = [button.text() for button in dialog.findChildren(QPushButton)]
        self.assertEqual(labels, ["Thêm tài khoản", "Xóa tài khoản", "Đóng"])
        self.assertEqual(dialog.ROLE_LABELS["GiangVien"], "Giảng viên")
        self.assertEqual(dialog.HEADERS, ("Mã", "Họ và tên", "Vai trò", "Trạng thái"))

    def test_delete_confirmation_cancel_does_not_call_service(self):
        dialog = self._dialog()
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No) as question:
            dialog.delete_button.click()
        question.assert_called_once()
        self.repository.delete_account.assert_not_called()
        self.assertEqual(self.repository.find_all_accounts.call_count, 1)

    def test_confirmed_delete_calls_service_then_reloads_empty_list(self):
        dialog = self._dialog()
        self.repository.find_all_accounts.return_value = []
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            dialog.delete_button.click()
        self.repository.delete_account.assert_called_once_with("other")
        self.assertEqual(self.repository.find_all_accounts.call_count, 2)
        self.assertEqual(dialog.account_table.rowCount(), 0)

    def test_delete_failure_keeps_dialog_and_reports_safe_error(self):
        dialog = self._dialog()
        self.repository.delete_account.side_effect = pyodbc.Error("42000", "private (52015)")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            with patch.object(QMessageBox, "warning") as warning:
                dialog._delete_account()
        self.assertIn("đăng xuất", warning.call_args.args[2])
        self.assertEqual(dialog.account_table.rowCount(), 1)
        self.assertEqual(dialog.result(), dialog.DialogCode.Rejected)
        self.assertEqual(self.repository.find_all_accounts.call_count, 1)


class VerifierSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "docker" / "verify-account-management.py"
        spec = importlib.util.spec_from_file_location("verify_accounts16", path)
        cls.verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.verifier)

    def setUp(self):
        connection_guard = patch.object(database.pyodbc, "connect", side_effect=AssertionError("Unit test SQL connection"))
        connection_guard.start()
        self.addCleanup(connection_guard.stop)

    def test_preexisting_principal_aborts_before_any_creation_or_cleanup(self):
        verifier = self.verifier
        control = Mock()
        service = Mock()
        service.find_all_accounts.return_value = [ADMIN, User("SV00000001", "SinhVien", "SV00000001", None, True)]
        with (
            patch.dict(os.environ, {"QLDSV_ADMIN_LOGIN": "admin", "QLDSV_STUDENT_LOGIN": "SV00000001"}),
            patch.object(verifier, "login_admin", return_value=control),
            patch.object(verifier, "AccountService", return_value=service),
            patch.object(verifier.AccountRepository, "student_exists", return_value=True),
            patch.object(verifier.AccountRepository, "lecturer_exists", return_value=True),
            patch.object(verifier, "query", return_value=[(None,)]) as query,
            patch.object(verifier, "assert_absent", side_effect=RuntimeError("already exists")),
        ):
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                verifier.main()
        service.create_account.assert_not_called()
        service.delete_account.assert_not_called()
        self.assertEqual(query.call_count, 1)
        control.close.assert_called_once()

    def _run_admin_failure(self, *, created_sid=b"owned", visible_sid=b"owned",
                           precheck_sid=b"owned", delete_error=None, fail_validation=False, run_probe=False):
        verifier = self.verifier
        control = Mock()
        service = Mock()
        service.create_account.return_value = created_sid
        service.find_all_accounts.return_value = [ADMIN, User("SV00000001", "SinhVien", "SV00000001", None, True)]
        actual_expect_sql_error = verifier.expect_sql_error

        def query(connection, sql, *parameters):
            if "OBJECT_ID" in sql:
                return [(None,)]
            if "SELECT sp.sid" in sql:
                if fail_validation:
                    raise RuntimeError("validation failed")
                return [(visible_sid, False, True)]
            if "sys.database_role_members" in sql:
                return [("QLDSV_ADMIN",)]
            if "sys.server_role_members" in sql:
                return [("QLDSV_ACCOUNT_ADMIN",), ("dbcreator",)]
            if "SELECT sid" in sql:
                return [] if precheck_sid is None else [(precheck_sid,)]
            if "EXEC dbo.sp_XoaTaiKhoan" in sql:
                if delete_error:
                    raise delete_error
                if "@ExpectedSid" in sql and parameters[1] != visible_sid:
                    raise pyodbc.Error("42000", "Target principal identity changed (52016)")
            return []

        def expect_sql_error(operation, number):
            if run_probe and number == 52016:
                actual_expect_sql_error(operation, number)

        with (
            patch.dict(os.environ, {"QLDSV_ADMIN_LOGIN": "admin", "QLDSV_STUDENT_LOGIN": "SV00000001"}),
            patch.object(verifier, "login_admin", return_value=control),
            patch.object(verifier, "AccountService", return_value=service),
            patch.object(verifier.AccountRepository, "student_exists", return_value=True),
            patch.object(verifier.AccountRepository, "lecturer_exists", return_value=True),
            patch.object(verifier, "query", side_effect=query) as sql,
            patch.object(verifier, "assert_absent") as absent,
            patch.object(verifier, "expect_service_error"),
            patch.object(verifier, "expect_sql_error", side_effect=expect_sql_error),
            patch.object(verifier, "open_sql_connection", side_effect=RuntimeError("late failure")),
            patch("builtins.print"),
        ):
            with self.assertRaises(RuntimeError) as caught:
                verifier.main()
        name = service.create_account.call_args.kwargs["magv"]
        deletions = [call for call in sql.call_args_list if "EXEC dbo.sp_XoaTaiKhoan" in call.args[1]]
        control.close.assert_called_once()
        return caught.exception, name, deletions, absent, sql.call_args_list

    def assert_owned_delete(self, deletion, name, sid):
        self.assertIn("@ExpectedSid=?", deletion.args[1])
        self.assertEqual(deletion.args[2:], (name, sid))

    def test_replacement_before_old_capture_window_never_becomes_owned(self):
        error, name, deletions, _, _ = self._run_admin_failure(
            visible_sid=b"replacement", precheck_sid=b"replacement"
        )
        self.assertEqual(len(deletions), 1)
        self.assert_owned_delete(deletions[0], name, b"owned")
        self.assertIn("cleanup incomplete", str(error))

    def test_replacement_between_precheck_and_delete_is_not_retried(self):
        error, name, deletions, _, _ = self._run_admin_failure(
            delete_error=pyodbc.Error("42000", "identity changed (52016)")
        )
        self.assertIn("cleanup incomplete", str(error))
        self.assertEqual(len(deletions), 1)
        self.assert_owned_delete(deletions[0], name, b"owned")

    def test_matching_owned_sid_allows_one_cleanup_delete(self):
        error, name, deletions, _, _ = self._run_admin_failure()
        self.assertIn("late failure", str(error))
        self.assertEqual(len(deletions), 1)
        self.assert_owned_delete(deletions[0], name, b"owned")

    def test_post_create_validation_failure_preserves_returned_ownership(self):
        error, name, deletions, _, calls = self._run_admin_failure(fail_validation=True)
        self.assertIn("validation failed", str(error))
        self.assertEqual(len(deletions), 1)
        self.assert_owned_delete(deletions[0], name, b"owned")
        # The only simple SID observation is final cleanup, after validation failed.
        sid_reads = [call for call in calls if "SELECT sid" in call.args[1]]
        self.assertEqual(len(sid_reads), 1)
        self.assertLess(next(i for i, call in enumerate(calls) if "SELECT sp.sid" in call.args[1]),
                        calls.index(sid_reads[0]))

    def test_already_absent_owned_principal_requires_no_delete(self):
        error, name, deletions, absent, _ = self._run_admin_failure(precheck_sid=None)
        self.assertIn("late failure", str(error))
        self.assertEqual(deletions, [])
        self.assertTrue(any(call.args[1] == name for call in absent.call_args_list))

    def test_missing_or_invalid_create_token_never_authorizes_cleanup(self):
        for sid in (None, b"", "not-bytes"):
            with self.subTest(sid=sid):
                error, _, deletions, _, _ = self._run_admin_failure(created_sid=sid)
                self.assertIn("cleanup incomplete", str(error))
                self.assertEqual(deletions, [])

    def test_wrong_sid_contract_probe_preserves_owned_account(self):
        error, name, deletions, _, calls = self._run_admin_failure(run_probe=True)
        self.assertIn("late failure", str(error))
        self.assertEqual(len(deletions), 2)
        self.assertEqual(deletions[0].args[2], name)
        self.assertIn("@ExpectedSid=?", deletions[0].args[1])
        self.assertNotEqual(deletions[0].args[3], b"owned")
        self.assert_owned_delete(deletions[1], name, b"owned")
        probe_index = calls.index(deletions[0])
        self.assertTrue(any("SELECT sp.sid" in call.args[1] for call in calls[probe_index + 1:]))

    def test_student_uses_creation_token_even_if_metadata_shows_replacement(self):
        verifier = self.verifier
        control, active, repository, service = Mock(), Mock(), Mock(), Mock()
        service.create_account.return_value = b"admin-owned"
        service.create_student_account.return_value = b"student-owned"
        service.find_all_accounts.return_value = [ADMIN, User("SV00000001", "SinhVien", "SV00000001", None, True)]
        student = "SV00000002"

        def query(connection, sql, *parameters):
            if "OBJECT_ID" in sql:
                return [(None,)]
            if "SELECT sp.sid" in sql:
                return [(b"replacement", False, False)] if parameters[0] == student else [(b"admin-owned", False, True)]
            if "sys.database_role_members" in sql:
                return [("QLDSV_SINHVIEN" if parameters[0] == student else "QLDSV_ADMIN",)]
            if "sys.server_role_members" in sql:
                return [] if parameters[0] == student else [("QLDSV_ACCOUNT_ADMIN",), ("dbcreator",)]
            if "SELECT sid" in sql:
                return [(b"replacement",)] if parameters[0] == student else [(b"admin-owned",)]
            if "EXEC dbo.sp_XoaTaiKhoan" in sql and "@ExpectedSid" in sql:
                raise pyodbc.Error("42000", "identity changed (52016)")
            if "SELECT 1" in sql:
                return [(1,)]
            return []

        with (
            patch.dict(os.environ, {"QLDSV_ADMIN_LOGIN": "admin", "QLDSV_STUDENT_LOGIN": "SV00000001",
                                    "QLDSV_VERIFY_STUDENT": student}),
            patch.object(verifier, "login_admin", return_value=control),
            patch.object(verifier, "AccountService", return_value=service),
            patch.object(verifier, "AccountRepository", return_value=repository),
            patch.object(verifier.AuthService, "login", side_effect=RuntimeError("unexpected Student login")),
            patch.object(verifier, "query", side_effect=query) as sql,
            patch.object(verifier, "assert_absent"),
            patch.object(verifier, "expect_service_error"),
            patch.object(verifier, "expect_sql_error"),
            patch.object(verifier, "open_sql_connection", return_value=active),
            patch("builtins.print"),
        ):
            with self.assertRaisesRegex(RuntimeError, "cleanup incomplete"):
                verifier.main()
        service.create_student_account.assert_called_once_with(student)
        name = service.create_account.call_args.kwargs["magv"]
        repository.delete_account.assert_called_once_with(name, expected_sid=b"admin-owned")
        deletions = [call for call in sql.call_args_list if "EXEC dbo.sp_XoaTaiKhoan" in call.args[1]]
        self.assertEqual(len(deletions), 1)
        self.assert_owned_delete(deletions[0], student, b"student-owned")
        control.close.assert_called_once()

    def test_successful_all_three_deletes_supply_creation_sids(self):
        verifier = self.verifier
        control, active, repository, service = Mock(), Mock(), Mock(), Mock()
        student, lecturer, staff = "SV00000002", "GV00000002", "GV00000003"
        role = "Admin"
        sids = {staff: b"admin-owned", student: b"student-owned", lecturer: b"lecturer-owned"}

        def require_admin():
            if role != "Admin":
                raise PermissionError("Admin required")

        def list_accounts():
            require_admin()
            return [ADMIN, User("SV00000001", "SinhVien", "SV00000001", None, True)]

        def create_staff(requested_role, password=None, masv="", magv=""):
            require_admin()
            return sids[magv]

        def create_student(name):
            require_admin()
            return sids[name]

        def login_user(name, *args):
            nonlocal role
            role = "SinhVien" if name == student else "GiangVien"
            return User(name, role, name if role == "SinhVien" else None,
                        name if role == "GiangVien" else None, True)

        def login_admin(*args, **kwargs):
            nonlocal role
            role = "Admin"
            return control if kwargs.get("cleanup_connection") else None

        service.find_all_accounts.side_effect = list_accounts
        service.create_account.side_effect = create_staff
        service.create_student_account.side_effect = create_student
        service.delete_account.side_effect = lambda *args: require_admin()

        def query(connection, sql, *parameters):
            if "OBJECT_ID" in sql:
                return [(None,)]
            name = parameters[0] if parameters else None
            sql_role = {staff: "QLDSV_ADMIN", student: "QLDSV_SINHVIEN", lecturer: "QLDSV_GIANGVIEN"}.get(name)
            if "SELECT sp.sid" in sql:
                return [(sids[name], False, name != student)]
            if "sys.database_role_members" in sql:
                return [(sql_role,)]
            if "sys.server_role_members" in sql:
                return [("QLDSV_ACCOUNT_ADMIN",), ("dbcreator",)] if name == staff else []
            if "SELECT 1" in sql:
                return [(1,)]
            if "EXEC dbo.sp_XoaTaiKhoan" in sql:
                self.assertIn("@ExpectedSid=?", sql)
                self.assertNotEqual(parameters[1], sids[name])
                raise pyodbc.Error("42000", "identity changed (52016)")
            return []

        actual_expect_sql_error = verifier.expect_sql_error
        with (
            patch.dict(os.environ, {"QLDSV_ADMIN_LOGIN": "admin", "QLDSV_STUDENT_LOGIN": "SV00000001",
                                    "QLDSV_VERIFY_STUDENT": student, "QLDSV_VERIFY_ADMIN": staff,
                                    "QLDSV_VERIFY_LECTURER": lecturer}),
            patch.object(verifier, "login_admin", side_effect=login_admin),
            patch.object(verifier.AuthService, "login", side_effect=login_user),
            patch.object(verifier, "AccountService", return_value=service),
            patch.object(verifier, "AccountRepository", return_value=repository),
            patch.object(verifier, "query", side_effect=query),
            patch.object(verifier, "assert_absent"),
            patch.object(verifier, "expect_service_error"),
            patch.object(verifier, "expect_sql_error", side_effect=lambda operation, number:
                         actual_expect_sql_error(operation, number) if number == 52016 else None),
            patch.object(verifier, "open_sql_connection", return_value=active),
            patch("builtins.print"),
        ):
            verifier.main()
        self.assertEqual([(call.args, call.kwargs) for call in repository.delete_account.call_args_list], [
            ((staff,), {"expected_sid": b"admin-owned"}),
            ((student,), {"expected_sid": b"student-owned"}),
            ((lecturer,), {"expected_sid": b"lecturer-owned"}),
        ])


class SqlOwnershipContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (Path(__file__).resolve().parents[1] / "database" / "StoredProcedures_Security.sql").read_text(
            encoding="utf-8"
        )
        cls.create = re.search(r"CREATE PROCEDURE dbo.sp_TaoTaiKhoan\b(.*?)\nGO", source, re.S).group(1)
        cls.delete = re.search(r"CREATE PROCEDURE dbo.sp_XoaTaiKhoan\b(.*?)\nGO", source, re.S).group(1)

    def test_three_role_caller_and_target_membership_contracts(self):
        for body in (self.create, self.delete):
            guard = body[:body.index("DECLARE @Name")]
            for role, expected in (("ADMIN", 1), ("GIANGVIEN", 0), ("SINHVIEN", 0)):
                self.assertIn(f"ISNULL(IS_ROLEMEMBER(N'QLDSV_{role}'),-1)<>{expected}", guard)
        self.assertIn("(N'QLDSV_ADMIN',N'QLDSV_GIANGVIEN',N'QLDSV_SINHVIEN')", self.delete)
        self.assertIn("@BusinessRole<>N'QLDSV_ADMIN'", self.delete)

    def test_staff_entity_lock_default_password_and_policy(self):
        body = self.create
        locking = "FROM dbo.Giangvien WITH (UPDLOCK,HOLDLOCK) WHERE MAGV=@Name"
        self.assertIn(locking, body)
        self.assertLess(body.index("BEGIN TRANSACTION"), body.index(locking))
        self.assertLess(body.index(locking), body.index("CREATE LOGIN"))
        self.assertIn("THROW 52017", body)
        self.assertIn("SET @Password=N'Qldsv@123456'", body)
        self.assertIn("CASE WHEN @BusinessRole=N'QLDSV_SINHVIEN' THEN N'OFF;' ELSE N'ON;' END", body)
        self.assertIn("IF @BusinessRole=N'QLDSV_ADMIN'", body)

    def test_identity_and_own_score_reject_ambiguous_roles_and_validate_entity(self):
        source = (Path(__file__).resolve().parents[1] / "database" / "StoredProcedures_Security.sql").read_text(encoding="utf-8")
        identity = source.split("CREATE PROCEDURE dbo.sp_ThongTinDangNhap", 1)[1].split("\nGO", 1)[0]
        self.assertIn("@Admin+@Lecturer+@Student<>1", identity)
        self.assertIn("dbo.Giangvien WHERE MAGV=@User", identity)
        self.assertIn("dbo.Sinhvien WHERE MASV=@User", identity)
        own = source.split("CREATE PROCEDURE dbo.sp_SinhVien_XemDiem", 1)[1].split("\nGO", 1)[0]
        self.assertIn("ISNULL(IS_ROLEMEMBER(N'QLDSV_GIANGVIEN'),-1)<>0", own)
        self.assertNotRegex(source, r"GRANT EXECUTE ON SCHEMA")

    def test_identity_requires_one_direct_membership_matching_business_role(self):
        source = (Path(__file__).resolve().parents[1] / "database" / "StoredProcedures_Security.sql").read_text(encoding="utf-8")
        identity = source.split("CREATE PROCEDURE dbo.sp_ThongTinDangNhap", 1)[1].split("\nGO", 1)[0]
        self.assertRegex(identity, r"DECLARE\s+@BusinessRole\s+sysname\b")
        guard = re.search(
            r"IF\s*\(\s*SELECT\s+COUNT\s*\(\s*\*\s*\)\s+"
            r"FROM\s+sys\.database_role_members\s+"
            r"WHERE\s+member_principal_id\s*=\s*DATABASE_PRINCIPAL_ID\s*\(\s*@User\s*\)\s*"
            r"\)\s*<>\s*1\s+OR\s+NOT\s+EXISTS\s*\((.*?)\)\s*THROW\s+52021\b",
            identity, re.S | re.I,
        )
        self.assertIsNotNone(guard, "Runtime identity must reject any additional direct database role")
        self.assertRegex(guard.group(1), r"FROM\s+sys\.database_role_members\s+rm\b")
        self.assertRegex(guard.group(1), r"JOIN\s+sys\.database_principals\s+r\s+ON\s+r\.principal_id\s*=\s*rm\.role_principal_id")
        self.assertRegex(guard.group(1), r"rm\.member_principal_id\s*=\s*DATABASE_PRINCIPAL_ID\s*\(\s*@User\s*\)")
        self.assertRegex(guard.group(1), r"r\.name\s*=\s*@BusinessRole\b")
        self.assertLess(identity.index("@Admin+@Lecturer+@Student<>1"), guard.start())
        self.assertRegex(identity, r"@BusinessRole\s+AS\s+RoleName")

    def test_create_output_is_optional_and_captured_before_commit_without_resultset(self):
        header, body = re.split(r"\bAS\b", self.create, maxsplit=1)
        self.assertRegex(header, r"@CreatedSid\s+varbinary\(85\)\s*=\s*NULL\s+OUTPUT")
        assignment = re.search(r"SET\s+@CreatedSid\s*=\s*SUSER_SID\(@Name\)", body)
        self.assertIsNotNone(assignment)
        self.assertGreater(assignment.start(), body.index("ALTER SERVER ROLE"))
        self.assertLess(assignment.start(), body.index("COMMIT TRANSACTION"))
        self.assertRegex(body[assignment.end():body.index("COMMIT TRANSACTION")],
                         r"IF\s+@CreatedSid\s+IS\s+NULL\s+THROW")
        self.assertNotRegex(body, r"SELECT\s+@CreatedSid\s*;")

    def test_create_clears_output_at_entry_and_on_failure(self):
        _, body = re.split(r"\bAS\b", self.create, maxsplit=1)
        self.assertRegex(body[:body.index("IF ISNULL")], r"SET\s+@CreatedSid\s*=\s*NULL")
        catch = body.split("BEGIN CATCH", 1)[1]
        self.assertRegex(catch[:catch.index("THROW")], r"SET\s+@CreatedSid\s*=\s*NULL")
        self.assertIn("ROLLBACK TRANSACTION", catch)

    def test_delete_optional_guard_precedes_mutations_and_preserves_missing_error(self):
        header, body = re.split(r"\bAS\b", self.delete, maxsplit=1)
        self.assertRegex(header, r"@ExpectedSid\s+varbinary\(85\)\s*=\s*NULL")
        guard = re.search(r"IF\s+@ExpectedSid\s+IS\s+NOT\s+NULL\s+AND\s+@Sid\s*<>\s*@ExpectedSid\s+THROW\s+52016", body)
        self.assertIsNotNone(guard)
        self.assertGreater(guard.start(), body.index("BEGIN TRANSACTION"))
        self.assertGreater(guard.start(), body.index("THROW 52010"))
        self.assertLess(guard.start(), body.index("DROP MEMBER"))

    def test_delete_rechecks_sid_in_drop_batch_and_rethrows_52016_after_rollback(self):
        _, body = re.split(r"\bAS\b", self.delete, maxsplit=1)
        final_guard = body.rfind("SUSER_SID(@Name)")
        self.assertGreater(final_guard, body.index("DROP USER"))
        self.assertLess(final_guard, body.index("DROP LOGIN"))
        self.assertIn("THROW 52016", body[final_guard:body.index("DROP LOGIN")])
        self.assertIn("sp_executesql", body[body.index("DROP LOGIN"):body.index("COMMIT TRANSACTION")])
        self.assertRegex(body, r"@ExpectedSid\s*=\s*@ExpectedSid")
        catch = body.split("BEGIN CATCH", 1)[1]
        self.assertLess(catch.index("ROLLBACK TRANSACTION"), catch.index("IF @Error BETWEEN 52000 AND 52099 THROW"))
        self.assertLess(catch.index("IF @Error BETWEEN 52000 AND 52099 THROW"), catch.index("THROW 52015"))


if __name__ == "__main__":
    unittest.main()
