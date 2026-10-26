"""Epic 1.5: runtime SQL credentials, resource ownership and fail-closed routing."""

import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pyodbc
from PySide6.QtWidgets import QApplication, QMessageBox

from app.config import database
from app.models.user import User
from app.repositories.account_repository import AccountRepository
from app.repositories.backup_restore_repository import BackupRestoreRepository, RestoreCleanupError
from app.services.account_service import AccountService, AccountServiceError
from app.services.auth_service import AuthService, AuthenticationServiceError, InvalidCredentialsError
from app.utils import session


class Cursor:
    description = (("LoginName",), ("DatabaseUser",), ("RoleName",))

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

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        rows, self.rows = self.rows, []
        return rows

    def nextset(self):
        return False

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


ADMIN = User("canonical", "Admin", None, "canonical", True)


class Epic15Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def tearDown(self):
        session.clear_session()
        self.application.processEvents()

    def test_blank_credentials_never_connect(self):
        with patch("app.services.auth_service.open_sql_connection") as connect:
            for username, password in (("  ", "pw"), ("user", "")):
                with self.assertRaises(InvalidCredentialsError):
                    AuthService().login(username, password)
            connect.assert_not_called()

    def test_admin_uses_entered_credentials_and_verified_canonical_identity(self):
        qldsv = Connection([("canonical", "canonical", "QLDSV_ADMIN")])
        master = Connection([("canonical",)])
        with patch("app.services.auth_service.open_sql_connection", side_effect=[qldsv, master]) as connect:
            user = AuthService().login(" entered ", "runtime-secret")
        self.assertEqual(user, ADMIN)
        self.assertEqual(connect.call_args_list[0].args, ("entered", "runtime-secret"))
        self.assertEqual(connect.call_args_list[1].args, ("entered", "runtime-secret"))
        self.assertEqual(connect.call_args_list[1].kwargs, {"database_override": "master", "autocommit": True})
        self.assertEqual(qldsv.statement.calls[0][0], "EXEC dbo.sp_ThongTinDangNhap;")
        self.assertIs(session.require_qldsv_connection(), qldsv)
        self.assertIs(session.require_master_connection(), master)
        self.assertEqual(qldsv.statement.closed, 1)
        self.assertNotIn("runtime-secret", repr(session.current_user))
        self.assertNotIn("password", vars(user) if hasattr(user, "__dict__") else user.__slots__)
        self.assertFalse(any("password" in key.lower() for key in vars(session)))

    def test_student_masv_is_database_user_and_has_no_master_connection(self):
        connection = Connection([("SV00000002", "SV00000002", "QLDSV_SINHVIEN")])
        with patch("app.services.auth_service.open_sql_connection", return_value=connection) as connect:
            user = AuthService().login("SV00000002", "123456")
        self.assertEqual((user.role, user.masv, user.magv), ("SinhVien", "SV00000002", None))
        self.assertEqual(connect.call_count, 1)
        with self.assertRaises(session.SessionRequiredError):
            session.require_master_connection()

    def test_lecturer_magv_comes_from_database_user_and_never_opens_master(self):
        connection = Connection([("GV00000002", "GV00000002", "QLDSV_GIANGVIEN")])
        with patch("app.services.auth_service.open_sql_connection", return_value=connection) as connect:
            user = AuthService().login("GV00000002", "runtime-secret")
        self.assertEqual((user.role, user.magv, user.masv), ("GiangVien", "GV00000002", None))
        connect.assert_called_once_with("GV00000002", "runtime-secret", autocommit=True)
        with self.assertRaises(session.SessionRequiredError):
            session.require_master_connection()
        self.assertNotIn("runtime-secret", repr(session.current_user))
        session.clear_session()
        session.clear_session()
        self.assertEqual(connection.closed, 1)

    def test_sql_errors_are_classified_without_echoing_driver_diagnostics(self):
        for state, number, expected in (
            ("28000", "18456", InvalidCredentialsError),
            ("08001", "network", AuthenticationServiceError),
            ("IM002", "driver", AuthenticationServiceError),
            ("HYT00", "timeout", AuthenticationServiceError),
            ("HYT01", "timeout", AuthenticationServiceError),
            ("42000", "52020", AuthenticationServiceError),
            ("42000", "52021", AuthenticationServiceError),
            ("28000", "52020", AuthenticationServiceError),
            ("28000", "52021", AuthenticationServiceError),
        ):
            with self.subTest(state=state, number=number):
                candidate = Connection(error=pyodbc.Error(state, number + " secret"))
                with patch("app.services.auth_service.open_sql_connection", return_value=candidate):
                    with self.assertRaises(expected) as caught:
                        AuthService().login("user", "secret")
                self.assertNotIn("secret", str(caught.exception))
                self.assertIsNone(caught.exception.__context__)
                self.assertIsNone(session.current_user)
                self.assertEqual(candidate.closed, 1)

    def test_connect_rejection_does_not_publish_session(self):
        with patch("app.services.auth_service.open_sql_connection", side_effect=pyodbc.Error("28000", "18456")):
            with self.assertRaises(InvalidCredentialsError):
                AuthService().login("user", "wrong")
        self.assertIsNone(session.current_user)

    def test_missing_extra_or_unsupported_identity_is_rejected(self):
        for rows in ([], [("u", "u", "GiangVien")], [("u", "u", None)],
                     [("u", "u", "QLDSV_ADMIN")] * 2, [(None, "u", "QLDSV_ADMIN")],
                     [("u", "u", "QLDSV_ADMIN,QLDSV_GIANGVIEN")],
                     [("u", "u", "QLDSV_ADMIN,QLDSV_GIANGVIEN,QLDSV_SINHVIEN")]):
            candidate = Connection(rows)
            with patch("app.services.auth_service.open_sql_connection", return_value=candidate):
                with self.assertRaises(AuthenticationServiceError):
                    AuthService().login("u", "pw")
            self.assertIsNone(session.current_user)
            self.assertEqual(candidate.closed, 1)

    def test_master_identity_failure_closes_both_candidates(self):
        qldsv = Connection([("canonical", "canonical", "QLDSV_ADMIN")])
        master = Connection([("different",)])
        with patch("app.services.auth_service.open_sql_connection", side_effect=[qldsv, master]):
            with self.assertRaises(AuthenticationServiceError):
                AuthService().login("entered", "pw")
        self.assertIsNone(session.current_user)
        self.assertEqual((qldsv.closed, master.closed), (1, 1))

    def test_master_open_failure_closes_qldsv_candidate(self):
        qldsv = Connection([("canonical", "canonical", "QLDSV_ADMIN")])
        with patch("app.services.auth_service.open_sql_connection", side_effect=[qldsv, pyodbc.Error("08001", "lost")]):
            with self.assertRaises(AuthenticationServiceError):
                AuthService().login("entered", "pw")
        self.assertEqual(qldsv.closed, 1)
        self.assertIsNone(session.current_user)

    def test_odbc_braces_values_and_ignores_shared_credentials(self):
        with patch.dict(os.environ, {"DB_DRIVER": "driver", "DB_SERVER": "host};UID=sa", "DB_DATABASE": "QLDSV",
                                    "DB_USERNAME": "fixed", "DB_PASSWORD": "fixed", "DB_TRUSTED_CONNECTION": "yes"}):
            with patch.object(database.pyodbc, "connect") as connect:
                database.open_sql_connection("u};x", "p};PWD=bad")
        text = connect.call_args.args[0]
        self.assertIn("UID={u}};x};", text)
        self.assertIn("PWD={p}};PWD=bad};", text)
        self.assertNotIn("fixed", text)
        self.assertNotIn("Trusted_Connection", text)
        self.assertTrue(connect.call_args.kwargs["autocommit"])
        self.assertFalse(pyodbc.pooling)

    def test_env_loader_imports_target_settings_without_bootstrap_credentials(self):
        settings = {"DB_SERVER": "docker,14330", "DB_DATABASE": "QLDSV", "DB_DRIVER": "driver",
                    "QLDSV_BACKUP_DIR": "backup-target", "QLDSV_SQL_BACKUP_DIR": "/var/opt/mssql/backups",
                    "DB_USERNAME": "fixed", "DB_PASSWORD": "secret",
                    "QLDSV_ADMIN_PASSWORD": "bootstrap", "MSSQL_SA_PASSWORD": "bootstrap"}
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(database, "dotenv_values", return_value=settings):
                database._load_target_settings()
            self.assertEqual(set(os.environ), {"DB_SERVER", "DB_DATABASE", "DB_DRIVER", "QLDSV_BACKUP_DIR", "QLDSV_SQL_BACKUP_DIR"})

    def test_clear_and_replacement_close_each_owned_connection_once(self):
        old, master, new = Connection(), Connection(), Connection()
        session.set_authenticated(ADMIN, old, master)
        session.set_authenticated(ADMIN, new)
        self.assertEqual((old.closed, master.closed), (1, 1))
        session.clear_session()
        session.clear_session()
        self.assertEqual(new.closed, 1)
        self.assertIsNone(session.current_user)
        with self.assertRaises(session.SessionRequiredError):
            session.require_qldsv_connection()

    def test_cleanup_tolerates_already_closed_connections(self):
        closed = Mock()
        closed.close.side_effect = pyodbc.Error("closed")
        session.set_authenticated(ADMIN, closed, closed)
        session.clear_session()
        session.clear_session()
        closed.close.assert_called_once()

    def test_second_login_closes_old_physical_session(self):
        old = Connection([("old", "old", "QLDSV_SINHVIEN")])
        new = Connection([("new", "new", "QLDSV_SINHVIEN")])
        with patch("app.services.auth_service.open_sql_connection", side_effect=[old, new]):
            service = AuthService()
            service.login("old", "first")
            service.login("new", "second")
        self.assertEqual(old.closed, 1)
        self.assertEqual(new.closed, 0)
        self.assertIs(session.require_qldsv_connection(), new)

    def test_failed_replacement_leaves_no_previous_identity_or_connection(self):
        old = Connection()
        session.set_authenticated(ADMIN, old)
        with patch("app.services.auth_service.open_sql_connection", side_effect=pyodbc.Error("28000", "18456")):
            with self.assertRaises(InvalidCredentialsError):
                AuthService().login("bad", "wrong")
        self.assertIsNone(session.current_user)
        self.assertEqual(old.closed, 1)

    def test_connectivity_check_does_not_require_legacy_table(self):
        connection = Connection([("QLDSV",)])
        with patch.dict(os.environ, {"DB_DATABASE": "QLDSV"}):
            with patch.object(database, "open_sql_connection", return_value=connection):
                self.assertEqual(database.check_database_connection("u", "pw"), "QLDSV")
        self.assertNotIn("TaiKhoan", connection.statement.calls[0][0])
        self.assertEqual((connection.closed, connection.statement.closed), (1, 1))

    def test_user_full_name_joins_remain_available_with_sql_metadata(self):
        connection = Connection([("SV00000002", "QLDSV_SINHVIEN", "SV00000002", None, False, "Nguyen", "An", None, None)])
        session.set_authenticated(ADMIN, connection)
        accounts = AccountRepository().find_all_accounts()
        self.assertEqual(accounts[0].full_name, "Nguyen An")
        self.assertIn("LEFT JOIN dbo.Sinhvien", connection.statement.calls[0][0])
        self.assertIn("LEFT JOIN dbo.Giangvien", connection.statement.calls[0][0])
        self.assertEqual(connection.closed, 0)

    def test_repository_borrows_connection_and_closes_cursor_only(self):
        connection = Connection([(1,)])
        session.set_authenticated(ADMIN, connection)
        self.assertTrue(AccountRepository().student_exists("SV00000002"))
        self.assertEqual((connection.closed, connection.statement.closed), (0, 1))

    def test_guest_repository_access_fails_without_connect(self):
        with patch.object(database.pyodbc, "connect") as connect:
            with self.assertRaises(session.SessionRequiredError):
                AccountRepository().student_exists("SV00000002")
            with self.assertRaises(session.SessionRequiredError):
                BackupRestoreRepository().create_backup("/var/opt/mssql/backups/unused.bak")
            connect.assert_not_called()

    def test_backup_borrows_master_and_does_not_close_it(self):
        qldsv, master = Connection(), Connection()
        master.statement.description = None
        session.set_authenticated(ADMIN, qldsv, master)
        BackupRestoreRepository().create_backup("/var/opt/mssql/backups/unused.bak")
        self.assertIn("BACKUP DATABASE", master.statement.calls[0][0])
        self.assertEqual((master.closed, master.statement.closed, qldsv.closed), (0, 1, 0))

    def test_restore_invalidates_qldsv_before_single_user_and_requires_login(self):
        qldsv, master = Connection(), Connection()
        master.statement.description = None
        execute = master.statement.execute
        def check_closed(sql, *args):
            self.assertEqual(qldsv.closed, 1)
            return execute(sql, *args)
        master.statement.execute = check_closed
        session.set_authenticated(ADMIN, qldsv, master)
        BackupRestoreRepository().restore_backup("/var/opt/mssql/backups/unused.bak", 1)
        self.assertIsNone(session.current_user)
        self.assertEqual((qldsv.closed, master.closed), (1, 1))

    def test_unusable_restore_master_surfaces_cleanup_error_without_reconnect(self):
        qldsv, master = Connection(), Connection(error=pyodbc.Error("08S01", "lost"))
        session.set_authenticated(ADMIN, qldsv, master)
        with patch.object(database.pyodbc, "connect") as connect:
            with self.assertRaises(RestoreCleanupError):
                BackupRestoreRepository().restore_backup("/var/opt/mssql/backups/unused.bak", 1)
            connect.assert_not_called()
        self.assertIsNone(session.current_user)
        self.assertEqual((qldsv.closed, master.closed), (1, 1))

    def test_connection_loss_clears_resources_and_requires_reauthentication(self):
        qldsv, master = Connection(error=pyodbc.Error("08S01", "lost")), Connection()
        session.set_authenticated(ADMIN, qldsv, master)
        with self.assertRaises(session.SessionRequiredError):
            AccountRepository().student_exists("SV00000002")
        self.assertIsNone(session.current_user)
        self.assertEqual((qldsv.closed, master.closed), (1, 1))

    def test_account_service_translates_connection_loss_after_session_invalidation(self):
        qldsv, master = Connection(error=pyodbc.Error("08S01", "lost")), Connection()
        session.set_authenticated(ADMIN, qldsv, master)
        invalidated = Mock()
        session.events.invalidated.connect(invalidated)
        self.addCleanup(session.events.invalidated.disconnect, invalidated)
        with patch.object(database.pyodbc, "connect") as connect:
            with self.assertRaises(AccountServiceError) as caught:
                AccountService().find_all_accounts()
            connect.assert_not_called()
        self.assertEqual(str(caught.exception), "Phiên SQL không còn hiệu lực. Vui lòng đăng nhập lại.")
        self.assertIsNone(session.current_user)
        self.assertEqual((qldsv.closed, master.closed, qldsv.statement.closed), (1, 1, 1))
        invalidated.assert_called_once_with()

    def test_account_service_translates_session_loss_at_each_repository_path(self):
        cases = (
            ("create_account", ("Admin", "pw", "", "GV00000002")),
            ("create_account", ("SinhVien", None, "SV00000002")),
            ("create_student_account", ("SV00000002",)),
            ("create_account", ("GiangVien", "pw", "", "GV00000001")),
            ("delete_account", ("other",)),
        )
        for method, args in cases:
            with self.subTest(method=method, args=args):
                qldsv, master = Connection(error=pyodbc.Error("08S01", "lost")), Connection()
                session.set_authenticated(ADMIN, qldsv, master)
                repository = AccountRepository()
                with patch.object(database.pyodbc, "connect") as connect:
                    with self.assertRaisesRegex(AccountServiceError, "Vui lòng đăng nhập lại"):
                        getattr(AccountService(repository), method)(*args)
                    connect.assert_not_called()
                self.assertIsNone(session.current_user)
                self.assertEqual((qldsv.closed, master.closed), (1, 1))

    def test_account_service_does_not_translate_unrelated_value_errors(self):
        cases = (
            ("find_all_accounts", (), "find_all_accounts"),
            ("create_account", ("Admin", "pw", "", "GV00000002"), "create_account"),
            ("delete_account", ("other",), "delete_account"),
            ("create_account", ("GiangVien", "pw", "", "GV00000001"), "create_account"),
        )
        for method, args, repository_method in cases:
            with self.subTest(method=method, repository_method=repository_method):
                session.set_authenticated(ADMIN, Connection())
                repository = Mock(spec=AccountRepository)
                error = ValueError("unrelated programming error")
                getattr(repository, repository_method).side_effect = error
                with self.assertRaises(ValueError) as caught:
                    getattr(AccountService(repository), method)(*args)
                self.assertIs(caught.exception, error)
                self.assertIsNotNone(session.current_user)

    def test_account_management_constructor_handles_connection_loss(self):
        from app.ui.account_management import AccountManagementDialog
        qldsv, master = Connection(error=pyodbc.Error("08S01", "lost")), Connection()
        session.set_authenticated(ADMIN, qldsv, master)
        with patch.object(database.pyodbc, "connect") as connect:
            with patch.object(QMessageBox, "critical") as critical:
                dialog = AccountManagementDialog(AccountService())
            connect.assert_not_called()
        self.addCleanup(dialog.close)
        critical.assert_called_once_with(
            dialog, "Lỗi tải tài khoản", "Phiên SQL không còn hiệu lực. Vui lòng đăng nhập lại."
        )
        self.assertEqual(dialog._accounts, [])
        self.assertEqual(dialog.account_table.rowCount(), 0)
        self.assertIsNone(session.current_user)
        self.assertEqual((qldsv.closed, master.closed), (1, 1))

    def test_account_management_delete_callback_handles_connection_loss(self):
        from app.ui.account_management import AccountManagementDialog
        qldsv = Connection([("other", "QLDSV_ADMIN", None, None, False, None, None, None, None)])
        master = Connection()
        session.set_authenticated(ADMIN, qldsv, master)
        dialog = AccountManagementDialog(AccountService())
        self.addCleanup(dialog.close)
        dialog.account_table.selectRow(0)
        qldsv.statement.error = pyodbc.Error("08S01", "lost")
        with patch.object(database.pyodbc, "connect") as connect:
            with (
                patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes),
                patch.object(QMessageBox, "warning") as warning,
            ):
                dialog._delete_account()
            connect.assert_not_called()
        warning.assert_called_once_with(
            dialog, "Không thể xóa tài khoản", "Phiên SQL không còn hiệu lực. Vui lòng đăng nhập lại."
        )
        self.assertIsNone(session.current_user)
        self.assertEqual((qldsv.closed, master.closed), (1, 1))

    def test_permission_denial_does_not_invalidate_session(self):
        qldsv = Connection(error=pyodbc.Error("42000", "229"))
        session.set_authenticated(ADMIN, qldsv)
        with self.assertRaises(pyodbc.Error):
            AccountRepository().student_exists("SV00000002")
        self.assertIsNotNone(session.current_user)
        self.assertEqual(qldsv.closed, 0)

    def test_login_ui_clears_password_before_failure_message_and_success_signal(self):
        from app.ui.login import LoginWindow
        service = Mock()
        window = LoginWindow(service)
        window.password_input.setText("secret")
        service.login.side_effect = InvalidCredentialsError("Invalid")
        with patch.object(QMessageBox, "warning", side_effect=lambda *a: self.assertEqual(window.password_input.text(), "")):
            window._login()
        service.login.side_effect = None
        service.login.return_value = ADMIN
        window.password_input.setText("secret")
        seen = []
        window.authenticated.connect(lambda u: seen.append(window.password_input.text()))
        window._login()
        self.assertEqual(seen, [""])
        window.close()

    def test_router_accepts_three_roles_and_logout_is_idempotent(self):
        from app.main import ApplicationRouter
        router = ApplicationRouter(Mock())
        for role in ("Admin", "GiangVien", "SinhVien"):
            connection = Connection()
            user = User("u", role, "SV00000002" if role == "SinhVien" else None, None, True)
            session.set_authenticated(user, connection)
            router.open_dashboard(user)
            self.assertIsNotNone(router.dashboard)
            router.return_to_login()
            router.return_to_login()
            self.assertEqual(connection.closed, 1)
        with patch.object(QMessageBox, "information"):
            router.open_dashboard(User("u", "Unsupported", None, None, True))
        self.assertIsNone(router.dashboard)
        router.shutdown()
        router.deleteLater()

    def test_dashboard_close_and_shutdown_release_connections(self):
        from app.main import ApplicationRouter
        router = ApplicationRouter(Mock())
        qldsv, master = Connection(), Connection()
        session.set_authenticated(ADMIN, qldsv, master)
        router.open_dashboard(ADMIN)
        router.dashboard.close()
        self.assertIsNone(session.current_user)
        router.shutdown()
        router.shutdown()
        self.assertEqual((qldsv.closed, master.closed), (1, 1))
        router.deleteLater()

    def test_connection_loss_routes_back_to_login(self):
        from app.main import ApplicationRouter
        router = ApplicationRouter(Mock())
        qldsv = Connection(error=pyodbc.Error("08S01", "lost"))
        session.set_authenticated(ADMIN, qldsv)
        router.open_dashboard(ADMIN)
        with self.assertRaises(session.SessionRequiredError):
            AccountRepository().student_exists("SV00000002")
        self.application.processEvents()
        self.assertIsNone(router.dashboard)
        self.assertTrue(router.login_window.isVisible())
        self.assertEqual(router.login_window.password_input.text(), "")
        router.shutdown()
        router.deleteLater()

    def test_invalidation_keeps_failure_message_visible_before_login(self):
        from app.main import ApplicationRouter
        router = ApplicationRouter(Mock())
        session.set_authenticated(ADMIN, Connection())
        router.open_dashboard(ADMIN)
        message = QMessageBox(router.dashboard)
        message.setText("Manual recovery required")
        message.setModal(True)
        message.show()
        session.invalidate_session()
        self.application.processEvents()
        self.assertIsNotNone(router.dashboard)
        self.assertTrue(message.isVisible())
        message.accept()
        self.application.processEvents()
        self.assertIsNone(router.dashboard)
        self.assertTrue(router.login_window.isVisible())
        router.shutdown()
        router.deleteLater()


if __name__ == "__main__":
    unittest.main()
