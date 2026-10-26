"""Epic 1.8 offline tests: every SQL operation is fake; no live restore."""

from datetime import datetime, timedelta
import importlib.util
import os
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pyodbc
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from app.config import database
from app.models.user import User
from app.repositories.backup_restore_repository import BackupRestoreRepository, BackupSet, InvalidBackupError, RestoreCleanupError
from app.services.backup_restore_service import BackupRestoreError, BackupRestoreService
from app.ui.admin_dashboard import AdminDashboard
from app.ui.backup_restore import BackupRestoreDialog
from app.ui.student_dashboard import StudentDashboard
from app.ui.lecturer_dashboard import LecturerDashboard
from app.utils import session


ADMIN = User("GV00000001", "Admin", None, "GV00000001", True)
SQL_DIR = "/var/opt/mssql/backups"
SQL_FILE = SQL_DIR + "/example.bak"
STAMP = datetime(2026, 10, 26, 8, 0)
COLUMNS = ("DatabaseName", "BackupType", "Position", "UserName", "BackupStartDate", "BackupFinishDate")


def backup_set(position=1, database_name="QLDSV", backup_type=1, finish=STAMP, user="GV00000001"):
    return BackupSet(database_name, backup_type, position, user, finish - timedelta(minutes=1), finish)


def header_row(item):
    return (item.database_name, item.backup_type, item.position, item.user_name, item.started_at, item.finished_at)


class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.pages = []
        self.index = 0
        self.closed = 0
        self.next_calls = self.fetch_calls = 0

    @property
    def description(self):
        columns = self.pages[self.index][0] if self.index < len(self.pages) else None
        return [(column,) for column in columns] if columns is not None else None

    def execute(self, sql, *parameters):
        self.connection.calls.append((sql, parameters))
        if self.connection.on_execute:
            self.connection.on_execute(sql)
        for fragment, error in self.connection.errors.items():
            if fragment in sql:
                raise error
        self.pages = (self.connection.header_pages if "RESTORE HEADERONLY" in sql
                      else [(None, []), (("done",), [(1,)]), (None, [])])
        self.index = 0
        return self

    def fetchall(self):
        self.fetch_calls += 1
        return self.pages[self.index][1]

    def fetchone(self):
        raise AssertionError("HEADERONLY must read all rows")

    def nextset(self):
        self.next_calls += 1
        self.index += 1
        return self.index < len(self.pages)

    def close(self):
        self.closed += 1


class Connection:
    def __init__(self, headers=None, errors=None):
        self.header_pages = [(None, []), (COLUMNS, [header_row(item) for item in (headers or [backup_set()])])]
        self.errors = errors or {}
        self.calls = []
        self.cursors = []
        self.closed = 0
        self.on_execute = None

    def cursor(self):
        cursor = Cursor(self)
        self.cursors.append(cursor)
        return cursor

    def close(self):
        self.closed += 1


class FakeBackupRepository:
    def __init__(self, host):
        self.host = host
        self.calls = []
        self.sets = {}
        self.errors = {}
        self.publish_file = True

    def create_backup(self, sql_path):
        self.calls.append(("backup", sql_path))
        if "backup" in self.errors:
            raise self.errors["backup"]
        filename = PurePosixPath(sql_path).name
        if self.publish_file:
            (self.host / filename).write_bytes(b"fake backup")
        self.sets[filename] = [backup_set()]

    def read_backup_sets(self, sql_path):
        self.calls.append(("headers", sql_path))
        filename = PurePosixPath(sql_path).name
        if filename in self.errors:
            raise self.errors[filename]
        if filename not in self.sets:
            raise InvalidBackupError("Metadata backup không hợp lệ.")
        return self.sets[filename]

    def verify_backup(self, sql_path, position):
        self.calls.append(("verify", sql_path, position))
        if "verify" in self.errors:
            raise self.errors["verify"]

    def restore_backup(self, sql_path, position):
        self.calls.append(("restore", sql_path, position))
        session.invalidate_session()
        if "restore" in self.errors:
            raise self.errors["restore"]


class BackupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name).resolve()
        self.repository = FakeBackupRepository(self.directory)
        self.service = BackupRestoreService(self.repository, self.directory, SQL_DIR)
        session.set_authenticated(ADMIN, Connection(), Connection())

    def tearDown(self):
        session.clear_session()
        self.application.processEvents()

    def add_file(self, name="example.bak", sets=None):
        (self.directory / name).write_bytes(b"fake backup")
        self.repository.sets[name] = sets or [backup_set()]
        return name

    def test_dual_mapping_sends_only_linux_path_and_same_filename(self):
        item = self.service.backup_database()
        self.assertEqual(item.path.parent, self.directory)
        self.assertTrue(item.path.is_file())
        self.assertEqual(self.repository.calls, [("backup", SQL_DIR + "/" + item.filename),
                                                ("headers", SQL_DIR + "/" + item.filename)])
        self.assertNotIn(str(self.directory), repr(self.repository.calls))
        self.service.restore_database(item.filename, item.position)
        self.assertEqual(self.repository.calls[-2:], [("verify", SQL_DIR + "/" + item.filename, 1),
                                                     ("restore", SQL_DIR + "/" + item.filename, 1)])

    def test_missing_and_relative_host_directory(self):
        for value, message in (("", "QLDSV_BACKUP_DIR"), ("relative", "tuyệt đối"),
                               (self.directory / "missing", "không tồn tại")):
            with self.subTest(value=value), self.assertRaisesRegex(BackupRestoreError, message):
                BackupRestoreService(self.repository, value, SQL_DIR).list_backups()
        file = self.directory / "file"
        file.write_bytes(b"not a directory")
        with self.assertRaisesRegex(BackupRestoreError, "không phải thư mục"):
            BackupRestoreService(self.repository, file, SQL_DIR).list_backups()
        self.assertEqual(self.repository.calls, [])

    def test_sql_directory_must_be_explicit_canonical_linux_path(self):
        for value in ("", "relative", r"D:\DBMS\backups", "//server/share", "/a/../b", "/a//b", "/a/./b", "/a/", "/", "/a\\b", "/a\nb"):
            with self.subTest(value=value), self.assertRaisesRegex(BackupRestoreError, "QLDSV_SQL_BACKUP_DIR"):
                BackupRestoreService(self.repository, self.directory, value).backup_database()
        self.assertEqual(self.repository.calls, [])

    def test_filename_traversal_injection_and_disappeared_file(self):
        for name in ("../outside.bak", "..\\outside.bak", "x/y.bak", "x\\y.bak", "D:evil.bak",
                     "bad\x00.bak", "bad\n.bak", "CON.bak", "file.bak ", "other.txt", "missing.bak"):
            with self.subTest(name=name), self.assertRaises(BackupRestoreError):
                self.service.restore_database(name, 1)
        self.assertEqual(self.repository.calls, [])

    def test_symlink_cannot_be_selected_or_listed(self):
        name = self.add_file()
        with patch.object(Path, "is_symlink", return_value=True):
            with self.assertRaisesRegex(BackupRestoreError, "symlink"):
                self.service.restore_database(name, 1)
            self.assertEqual(self.service.list_backups(), [])
        self.assertEqual(self.repository.calls, [])
        self.assertEqual(self.service.skipped_files, 1)

    def test_history_is_all_full_qldsv_sets_sorted_by_header_finish_not_mtime(self):
        self.add_file("many.bak", [backup_set(1), backup_set(2, finish=STAMP + timedelta(days=2)),
                                   backup_set(3, database_name="Other"), backup_set(4, backup_type=5)])
        self.add_file("older.bak", [backup_set(1, finish=STAMP - timedelta(days=2), user="OtherAdmin")])
        os.utime(self.directory / "older.bak", (2000000000, 2000000000))
        items = self.service.list_backups()
        self.assertEqual([(item.filename, item.position) for item in items], [("many.bak", 2), ("many.bak", 1), ("older.bak", 1)])
        self.assertEqual(items[-1].user_name, "OtherAdmin")
        self.assertEqual(items[-1].backup_at, STAMP - timedelta(days=2))
        self.assertEqual(items[0].started_at, STAMP + timedelta(days=2) - timedelta(minutes=1))

    def test_corrupt_or_sql_unreadable_file_is_skipped_with_status(self):
        self.add_file("good.bak")
        self.add_file("corrupt.bak")
        self.repository.errors["corrupt.bak"] = pyodbc.Error("42000", "private path diagnostic")
        items = self.service.list_backups()
        self.assertEqual([item.filename for item in items], ["good.bak"])
        self.assertEqual(self.service.skipped_files, 1)

    def test_unrelated_database_or_differential_file_not_listed(self):
        self.add_file(sets=[backup_set(database_name="Other"), backup_set(2, backup_type=5)])
        self.assertEqual(self.service.list_backups(), [])
        self.assertEqual(self.service.skipped_files, 1)

    def test_invalid_positions_rejected_before_sql(self):
        name = self.add_file()
        for position in (0, -1, True, 1.0, "1", "1; DROP DATABASE QLDSV", None):
            with self.subTest(position=position), self.assertRaisesRegex(BackupRestoreError, "Position"):
                self.service.restore_database(name, position)
        self.assertEqual(self.repository.calls, [])

    def test_positions_one_and_later_pass_through_verify_and_restore(self):
        name = self.add_file(sets=[backup_set(), backup_set(7)])
        for position in (1, 7):
            session.set_current_user(ADMIN)
            self.service.restore_database(name, position)
            self.assertEqual(self.repository.calls[-2:], [("verify", SQL_FILE, position), ("restore", SQL_FILE, position)])

    def test_file_disappears_after_verify_so_restore_never_starts(self):
        name = self.add_file()
        with patch.object(self.repository, "verify_backup", side_effect=lambda *_: (self.directory / name).unlink()):
            with self.assertRaisesRegex(BackupRestoreError, "Không tìm thấy"):
                self.service.restore_database(name, 1)
        self.assertIsNotNone(session.current_user)
        self.assertFalse(any(call[0] == "restore" for call in self.repository.calls))

    def test_backup_write_denied_has_safe_error_without_logging_or_context(self):
        self.repository.errors["backup"] = pyodbc.Error("42000", "private server path and credentials")
        with patch("logging.exception") as log:
            try:
                self.service.backup_database()
            except BackupRestoreError as error:
                self.assertIn("quyền ghi", str(error))
                self.assertNotIn("private", str(error))
                self.assertIsNone(error.__context__)
            else:
                self.fail("SQL failure reported success")
            log.assert_not_called()

    def test_success_requires_host_visibility_and_real_full_backup_metadata(self):
        self.repository.publish_file = False
        with self.assertRaisesRegex(BackupRestoreError, "bind mount"):
            self.service.backup_database()
        self.repository.publish_file = True
        with patch.object(self.repository, "read_backup_sets", return_value=[backup_set(database_name="Other")]):
            with self.assertRaisesRegex(BackupRestoreError, "metadata full backup"):
                self.service.backup_database()

    def test_existing_filename_is_never_overwritten_by_init(self):
        name = self.add_file()
        with patch.object(self.service, "generate_filename", return_value=name):
            with self.assertRaisesRegex(BackupRestoreError, "không ghi đè"):
                self.service.backup_database()
        self.assertEqual((self.directory / name).read_bytes(), b"fake backup")
        self.assertEqual(self.repository.calls, [])

    def test_verification_failure_preserves_session_and_blocks_restore(self):
        name = self.add_file()
        for error in (pyodbc.Error("42000", "private unreadable file"), InvalidBackupError("Backup set không hợp lệ.")):
            self.repository.calls.clear()
            self.repository.errors["verify"] = error
            with self.assertRaises(BackupRestoreError) as caught:
                self.service.restore_database(name, 1)
            self.assertNotIn("private", str(caught.exception))
            self.assertEqual(self.repository.calls, [("verify", SQL_FILE, 1)])
            self.assertIsNotNone(session.current_user)

    def test_restore_and_cleanup_errors_are_safe(self):
        name = self.add_file()
        for error, text in ((pyodbc.Error("42000", "private database in use"), "Phục hồi thất bại"),
                            (RestoreCleanupError("private master diagnostics"), "MULTI_USER")):
            session.set_current_user(ADMIN)
            self.repository.errors["restore"] = error
            with self.assertRaisesRegex(BackupRestoreError, text) as caught:
                self.service.restore_database(name, 1)
            self.assertNotIn("private", str(caught.exception))

    def test_admin_menu_opens_backup_screen(self):
        dashboard = AdminDashboard(ADMIN, backup_service=self.service)
        observed = []

        def inspect():
            dialogs = [w for w in QApplication.topLevelWidgets() if isinstance(w, BackupRestoreDialog) and w.isVisible()]
            observed.append(len(dialogs) == 1 and dialogs[0].parent() is dashboard)
            for dialog in dialogs:
                dialog.reject()

        QTimer.singleShot(0, inspect)
        next(b for b in dashboard.findChildren(QPushButton) if b.text() == "Sao lưu / Phục hồi").click()
        self.assertEqual(observed, [True])
        dashboard.close()

    def test_nonadmins_have_no_menu_and_services_or_repository_cannot_use_master(self):
        for user, kind in ((User("SV00000001", "SinhVien", "SV00000001", None, True), StudentDashboard),
                           (User("GV00000002", "GiangVien", None, "GV00000002", True), LecturerDashboard)):
            with self.subTest(role=user.role):
                session.set_authenticated(user, Connection())
                dashboard = kind(user)
                self.assertNotIn("Sao lưu / Phục hồi", [b.text() for b in dashboard.findChildren(QPushButton)])
                for action in (self.service.configured_directory, self.service.list_backups, self.service.backup_database,
                               lambda: self.service.verify_backup("example.bak", 1), lambda: self.service.restore_database("example.bak", 1)):
                    with self.assertRaises(PermissionError):
                        action()
                with self.assertRaises(session.SessionRequiredError):
                    BackupRestoreRepository().create_backup(SQL_FILE)
                dashboard.close()
        self.assertEqual(self.repository.calls, [])

    def test_table_shows_header_metadata_and_stores_selection_in_item_data(self):
        self.add_file(sets=[backup_set(4, user="Creator")])
        dialog = BackupRestoreDialog(self.service)
        self.addCleanup(dialog.close)
        self.assertEqual([dialog.backup_table.horizontalHeaderItem(c).text() for c in range(4)],
                         ["Tên file", "Thời gian backup", "Position", "User"])
        self.assertEqual(dialog.backup_table.item(0, 1).text(), STAMP.strftime("%d/%m/%Y %H:%M:%S"))
        self.assertEqual(dialog.backup_table.item(0, 2).text(), "4")
        self.assertEqual(dialog.backup_table.item(0, 3).text(), "Creator")
        self.assertEqual(tuple(dialog.backup_table.item(0, 0).data(Qt.ItemDataRole.UserRole)), ("example.bak", 4))

    def test_confirmation_no_then_yes_passes_item_data_not_formatted_text(self):
        self.add_file(sets=[backup_set(7)])
        dialog = BackupRestoreDialog(self.service)
        self.addCleanup(dialog.close)
        dialog.backup_table.selectRow(0)
        self.repository.calls.clear()
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            dialog.restore_button.click()
        self.assertEqual(self.repository.calls, [])
        self.assertFalse(dialog.restore_performed)
        dialog.backup_table.item(0, 0).setText("tampered display")
        dialog.backup_table.item(0, 2).setText("99")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), patch.object(QMessageBox, "information"):
            dialog.restore_button.click()
        self.assertEqual(self.repository.calls, [("verify", SQL_FILE, 7), ("restore", SQL_FILE, 7)])
        self.assertTrue(dialog.restore_performed)

    def test_failed_pre_restore_verification_does_not_report_success(self):
        self.add_file()
        self.repository.errors["verify"] = InvalidBackupError("File backup không hợp lệ.")
        dialog = BackupRestoreDialog(self.service)
        self.addCleanup(dialog.close)
        dialog.backup_table.selectRow(0)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), \
                patch.object(QMessageBox, "warning") as warning, patch.object(QMessageBox, "information") as info:
            dialog.restore_button.click()
        warning.assert_called_once()
        info.assert_not_called()
        self.assertFalse(dialog.restore_performed)
        self.assertIsNotNone(session.current_user)

    def test_backup_button_refreshes_metadata_and_skip_status(self):
        self.add_file("corrupt.bak")
        self.repository.errors["corrupt.bak"] = InvalidBackupError("Invalid backup")
        dialog = BackupRestoreDialog(self.service)
        self.addCleanup(dialog.close)
        with patch.object(QMessageBox, "information") as info:
            dialog.backup_button.click()
        info.assert_called_once()
        self.assertEqual(dialog.backup_table.rowCount(), 1)
        self.assertIn("bỏ qua 1", dialog.status_label.text())

    def test_host_directory_and_file_permission_failures_are_safe(self):
        name = self.add_file()
        with patch("app.services.backup_restore_service.os.scandir", side_effect=PermissionError("private")):
            with self.assertRaisesRegex(BackupRestoreError, "quyền đọc") as caught:
                self.service.list_backups()
            self.assertNotIn("private", str(caught.exception))
        with patch.object(Path, "open", side_effect=PermissionError("private")):
            with self.assertRaisesRegex(BackupRestoreError, "quyền đọc"):
                self.service.verify_backup(name, 1)
        self.assertEqual(self.repository.calls, [])

    def test_history_connection_loss_stops_listing_and_invalidates_once(self):
        self.add_file()
        qldsv, master = Connection(), Connection(errors={"HEADERONLY": pyodbc.Error("08S01", "private detail")})
        session.set_authenticated(ADMIN, qldsv, master)
        invalidated = QSignalSpy(session.events.invalidated)
        service = BackupRestoreService(BackupRestoreRepository(), self.directory, SQL_DIR)
        with self.assertRaisesRegex(BackupRestoreError, "đăng nhập lại"):
            service.list_backups()
        self.assertEqual(invalidated.count(), 1)
        self.assertEqual((qldsv.closed, master.closed), (1, 1))

    def test_actual_restore_routes_back_to_login_once_without_dashboard_logout(self):
        from app.main import ApplicationRouter
        self.add_file()
        session.set_authenticated(ADMIN, Connection(), Connection())
        router = ApplicationRouter(Mock())
        router.open_dashboard(ADMIN)
        router.dashboard._backup_service = BackupRestoreService(BackupRestoreRepository(), self.directory, SQL_DIR)
        dashboard = router.dashboard
        logout = QSignalSpy(dashboard.logout_requested)

        def restore_dialog():
            for dialog in QApplication.topLevelWidgets():
                if isinstance(dialog, BackupRestoreDialog) and dialog.isVisible():
                    dialog.backup_table.selectRow(0)
                    dialog.restore_button.click()

        try:
            with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), \
                    patch.object(QMessageBox, "information"), \
                    patch.object(router, "return_to_login", wraps=router.return_to_login) as login:
                QTimer.singleShot(0, restore_dialog)
                next(b for b in dashboard.findChildren(QPushButton) if b.text() == "Sao lưu / Phục hồi").click()
                self.application.processEvents()
                self.assertIsNone(router.dashboard)
                self.assertTrue(router.login_window.isVisible())
                login.assert_called_once_with()
                self.assertEqual(logout.count(), 0)
        finally:
            session.events.invalidated.disconnect(router._session_invalidated)
            router.shutdown()


class BackupVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])
        path = Path(__file__).resolve().parents[1] / "docker/verify-backup-restore.py"
        spec = importlib.util.spec_from_file_location("verify_backup_restore", path)
        cls.verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.verifier)

    def tearDown(self):
        session.clear_session()

    def test_missing_admin_password_fails_before_authentication(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(self.verifier.sys.stdin, "isatty", return_value=False), \
                patch.object(self.verifier, "AuthService") as auth:
            with self.assertRaisesRegex(RuntimeError, "current application Admin password unavailable"):
                self.verifier.main()
        auth.assert_not_called()

    def test_direct_restore_requires_exact_opt_in_before_any_probe_or_sql(self):
        for value in ("", "yes", "YES ", "1"):
            with patch.dict(os.environ, {"QLDSV_ALLOW_LIVE_RESTORE": value}), patch.object(self.verifier, "query") as query:
                with self.assertRaisesRegex(RuntimeError, "requires exact"):
                    self.verifier.restore_acceptance(Mock(), Mock(), ADMIN.username, "unit-password")
                query.assert_not_called()

    def test_default_main_creates_lists_verifies_and_cleans_only_owned_backup(self):
        verifier = self.verifier
        with TemporaryDirectory() as directory:
            host = Path(directory).resolve()
            unrelated = host / "existing.bak"
            unrelated.write_bytes(b"keep")
            service = BackupRestoreService(FakeBackupRepository(host), host, SQL_DIR)
            session.set_current_user(ADMIN)
            with patch.dict(os.environ, {"QLDSV_ADMIN_PASSWORD": "unit-password", "QLDSV_ALLOW_LIVE_RESTORE": ""}), \
                    patch.object(verifier, "AuthService") as auth, patch.object(verifier, "BackupRestoreService", return_value=service), \
                    patch.object(verifier, "preflight", return_value=host), patch.object(verifier, "audit_nonadmin_permissions"), \
                    patch.object(verifier, "restore_acceptance") as restore, patch("builtins.print"):
                auth.return_value.login.return_value = ADMIN
                verifier.main()
            restore.assert_not_called()
            self.assertEqual(list(host.iterdir()), [unrelated])
            self.assertEqual(unrelated.read_bytes(), b"keep")

    def test_changed_backup_identity_prevents_cleanup(self):
        with TemporaryDirectory() as directory:
            host = Path(directory).resolve()
            path = host / "owned.bak"
            path.write_bytes(b"original")
            token = self.verifier.fingerprint(path)
            path.write_bytes(b"replacement is longer")
            with self.assertRaisesRegex(RuntimeError, "identity changed"):
                self.verifier.cleanup_backup(path, token, host)
            self.assertTrue(path.is_file())

    def test_failed_destructive_acceptance_retains_recovery_backup(self):
        verifier = self.verifier
        with TemporaryDirectory() as directory:
            host = Path(directory).resolve()
            service = BackupRestoreService(FakeBackupRepository(host), host, SQL_DIR)
            session.set_current_user(ADMIN)
            with patch.dict(os.environ, {"QLDSV_ADMIN_PASSWORD": "unit-password", "QLDSV_ALLOW_LIVE_RESTORE": "YES"}), \
                    patch.object(verifier, "AuthService") as auth, patch.object(verifier, "BackupRestoreService", return_value=service), \
                    patch.object(verifier, "preflight", return_value=host), patch.object(verifier, "audit_nonadmin_permissions"), \
                    patch.object(verifier, "restore_acceptance", side_effect=RuntimeError("test failure")), \
                    patch("builtins.print") as output:
                auth.return_value.login.return_value = ADMIN
                with self.assertRaisesRegex(RuntimeError, "test failure"):
                    verifier.main()
            self.assertEqual(len(list(host.glob("QLDSV_*.bak"))), 1)
            self.assertTrue(any("retain recovery backup" in str(call.args) for call in output.call_args_list))

    def test_destructive_acceptance_probes_after_backup_then_restores_and_reauthenticates(self):
        verifier = self.verifier
        token = "11111111-1111-1111-1111-111111111111"
        service = Mock()
        item = Mock(filename="owned.bak", position=3)
        operations = []

        def sql_query(connection, sql, *params):
            if "CREATE TABLE dbo." in sql:
                operations.append("probe")
                return [(123,)]
            if "SELECT Token" in sql:
                return [(token,)]
            if "SELECT OBJECT_ID" in sql:
                operations.append("absence")
                return [(None,)]
            return [(1, 1)]

        def restore(*args):
            operations.append("restore")
            session.invalidate_session()

        def login(*args):
            operations.append("reauthenticate")
            session.set_authenticated(ADMIN, Connection(), Connection())
            return ADMIN

        session.set_authenticated(ADMIN, Connection(), Connection())
        service.restore_database.side_effect = restore
        with patch.dict(os.environ, {"QLDSV_ALLOW_LIVE_RESTORE": "YES"}), \
                patch.object(verifier, "check_core_database") as core, patch.object(verifier, "query", side_effect=sql_query), \
                patch.object(verifier.uuid, "uuid4", return_value=token), patch.object(verifier, "AuthService") as auth, \
                patch.object(verifier, "cleanup_probe") as cleanup, patch("builtins.print"):
            auth.return_value.login.side_effect = login
            verifier.restore_acceptance(service, item, ADMIN.username, "unit-password")
        self.assertEqual(operations, ["probe", "restore", "reauthenticate", "absence"])
        service.verify_backup.assert_called_once_with("owned.bak", 3)
        service.restore_database.assert_called_once_with("owned.bak", 3)
        auth.return_value.login.assert_called_once_with(ADMIN.username, "unit-password")
        self.assertEqual(core.call_count, 2)
        cleanup.assert_not_called()

    def test_probe_prerequisite_failure_happens_before_create_or_restore(self):
        session.set_authenticated(ADMIN, Connection(), Connection())
        service = Mock()
        with patch.dict(os.environ, {"QLDSV_ALLOW_LIVE_RESTORE": "YES"}), \
                patch.object(self.verifier, "check_core_database"), \
                patch.object(self.verifier, "query", return_value=[(0, 0)]) as query:
            with self.assertRaisesRegex(RuntimeError, "Probe prerequisites missing"):
                self.verifier.restore_acceptance(service, Mock(), ADMIN.username, "unit-password")
        self.assertFalse(any("CREATE TABLE dbo." in call.args[1] for call in query.call_args_list))
        service.restore_database.assert_not_called()

    def test_uncertain_probe_creation_is_reported_without_guessed_cleanup(self):
        session.set_authenticated(ADMIN, Connection(), Connection())
        service = Mock()
        with patch.dict(os.environ, {"QLDSV_ALLOW_LIVE_RESTORE": "YES"}), \
                patch.object(self.verifier, "check_core_database"), \
                patch.object(self.verifier, "query", side_effect=[[(1, 1)], pyodbc.Error("08S01", "private diagnostic")]), \
                patch.object(self.verifier, "cleanup_probe") as cleanup, patch("builtins.print") as output:
            with self.assertRaisesRegex(RuntimeError, "cleanup is uncertain"):
                self.verifier.restore_acceptance(service, Mock(), ADMIN.username, "unit-password")
        cleanup.assert_not_called()
        service.restore_database.assert_not_called()
        self.assertTrue(any("ownership uncertain" in str(call.args) for call in output.call_args_list))
        self.assertFalse(any("private diagnostic" in str(call.args) for call in output.call_args_list))


class BackupRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.qldsv = Connection()
        self.master = Connection(headers=[backup_set(), backup_set(3)])
        session.set_authenticated(ADMIN, self.qldsv, self.master)
        self.repository = BackupRestoreRepository()

    def tearDown(self):
        session.clear_session()
        self.application.processEvents()

    def test_backup_uses_parameterized_linux_path_checksums_and_drains_all_sets(self):
        with patch.object(database.pyodbc, "connect") as connect:
            self.repository.create_backup(SQL_FILE)
            connect.assert_not_called()
        sql, params = self.master.calls[0]
        self.assertIn("BACKUP DATABASE [QLDSV]", sql)
        self.assertIn("WITH INIT, CHECKSUM", sql)
        self.assertEqual(params, (SQL_FILE,))
        self.assertEqual((self.master.cursors[0].next_calls, self.master.cursors[0].fetch_calls), (3, 1))
        self.assertEqual((self.master.closed, self.qldsv.closed, self.master.cursors[0].closed), (0, 0, 1))

    def test_windows_path_or_path_object_rejected_without_sql(self):
        for path in (r"D:\DBMS\backups\example.bak", Path("example.bak"), "/a/../b.bak"):
            with self.assertRaises(InvalidBackupError):
                self.repository.create_backup(path)
        self.assertEqual(self.master.calls, [])

    def test_quote_in_sql_path_remains_parameter_data_for_every_operation(self):
        sql_path = SQL_DIR + "/quote'file.bak"
        self.repository.create_backup(sql_path)
        self.repository.verify_backup(sql_path, 3)
        self.repository.restore_backup(sql_path, 3)
        disk_calls = [(sql, params) for sql, params in self.master.calls if "DISK =" in sql]
        self.assertEqual(len(disk_calls), 4)  # BACKUP, HEADERONLY, VERIFYONLY, RESTORE
        for sql, params in disk_calls:
            self.assertNotIn(sql_path, sql)
            self.assertEqual(params, (sql_path,))

    def test_headeronly_reads_all_rows_and_all_result_sets(self):
        self.master.header_pages.append((COLUMNS, [header_row(backup_set(9))]))
        sets = self.repository.read_backup_sets(SQL_FILE)
        self.assertEqual([item.position for item in sets], [1, 3, 9])
        self.assertEqual(sets[0].user_name, ADMIN.username)
        self.assertEqual(sets[0].finished_at, STAMP)
        self.assertEqual(self.master.cursors[0].next_calls, 3)
        self.assertEqual(self.master.closed, 0)

    def test_empty_malformed_duplicate_or_incomplete_headers_are_rejected(self):
        for pages in ([(COLUMNS, [])], [(("Position",), [(1,)])], [(COLUMNS, [("QLDSV", 1, 1, "user", None, None)])],
                      [(COLUMNS, [header_row(backup_set()), header_row(backup_set())])]):
            self.master.header_pages = pages
            with self.assertRaises(InvalidBackupError):
                self.repository.read_backup_sets(SQL_FILE)

    def test_verify_uses_selected_position_and_consumes_result_sets(self):
        for position in (1, 3):
            self.repository.verify_backup(SQL_FILE, position)
            sql, params = self.master.calls[-1]
            self.assertIn(f"RESTORE VERIFYONLY FROM DISK = @backup_path WITH FILE = {position};", sql)
            self.assertNotIn("CHECKSUM", sql.upper())
            self.assertNotIn(SQL_FILE, sql)
            self.assertEqual(params, (SQL_FILE,))
            self.assertEqual(self.master.cursors[-1].next_calls, 3)
        self.assertEqual(self.master.closed, 0)

    def test_verify_does_not_require_backup_checksum_for_valid_external_full_backup(self):
        sql_path = SQL_DIR + "/external-full.bak"
        self.master.header_pages = [(COLUMNS, [header_row(backup_set(3, user="ExternalAdmin"))])]
        self.repository.verify_backup(sql_path, 3)
        self.assertEqual(len(self.master.calls), 2)
        header_sql, header_params = self.master.calls[0]
        self.assertIn("RESTORE HEADERONLY", header_sql)
        self.assertEqual(header_params, (sql_path,))
        verify_sql, verify_params = self.master.calls[1]
        self.assertIn("RESTORE VERIFYONLY FROM DISK = @backup_path WITH FILE = 3;", verify_sql)
        self.assertNotIn("CHECKSUM", verify_sql.upper())
        self.assertNotIn(sql_path, verify_sql)
        self.assertEqual(verify_params, (sql_path,))
        self.assertEqual((self.master.closed, self.qldsv.closed), (0, 0))

    def test_verify_missing_wrong_database_or_nonfull_set_blocks_verifyonly(self):
        for headers, position in (([backup_set()], 9), ([backup_set(database_name="Other")], 1), ([backup_set(backup_type=5)], 1)):
            self.master.calls.clear()
            self.master.header_pages = [(COLUMNS, [header_row(item) for item in headers])]
            with self.assertRaises(InvalidBackupError):
                self.repository.verify_backup(SQL_FILE, position)
            self.assertFalse(any("RESTORE VERIFYONLY" in sql for sql, _ in self.master.calls))

    def test_invalid_position_never_reaches_restore_or_invalidates_session(self):
        invalidated = QSignalSpy(session.events.invalidated)
        for value in (0, -1, True, "1; SELECT 1", 1.0):
            for action in (self.repository.verify_backup, self.repository.restore_backup):
                with self.assertRaises(InvalidBackupError):
                    action(SQL_FILE, value)
        self.assertEqual(self.master.calls, [])
        self.assertEqual(invalidated.count(), 0)
        self.assertEqual(self.qldsv.closed, 0)

    def test_restore_closes_qldsv_first_uses_selected_file_and_invalidates_once(self):
        invalidated = QSignalSpy(session.events.invalidated)

        def check_connections(sql):
            self.assertEqual(self.qldsv.closed, 1)
            self.assertEqual(self.master.closed, 0)

        self.master.on_execute = check_connections
        with patch.object(database.pyodbc, "connect") as connect:
            self.repository.restore_backup(SQL_FILE, 3)
            connect.assert_not_called()
        self.assertIn("SINGLE_USER WITH ROLLBACK IMMEDIATE", self.master.calls[0][0])
        self.assertIn("WITH FILE = 3, REPLACE, RECOVERY", self.master.calls[1][0])
        self.assertEqual(self.master.calls[1][1], (SQL_FILE,))
        self.assertIn("MULTI_USER", self.master.calls[-1][0])
        self.assertEqual((self.qldsv.closed, self.master.closed), (1, 1))
        self.assertIsNone(session.current_user)
        self.assertEqual(invalidated.count(), 1)

    def test_single_user_or_restore_failure_still_attempts_multi_user_and_invalidates(self):
        for fragment in ("SINGLE_USER", "RESTORE DATABASE"):
            qldsv, master = Connection(), Connection(errors={fragment: pyodbc.Error("42000", "failure")})
            session.set_authenticated(ADMIN, qldsv, master)
            invalidated = QSignalSpy(session.events.invalidated)
            with self.assertRaises(pyodbc.Error):
                self.repository.restore_backup(SQL_FILE, 1)
            self.assertIn("MULTI_USER", master.calls[-1][0])
            self.assertEqual((qldsv.closed, master.closed), (1, 1))
            self.assertEqual(invalidated.count(), 1)

    def test_cleanup_failure_surfaces_safe_error_and_never_reconnects(self):
        self.master.errors = {"MULTI_USER": pyodbc.Error("08S01", "private diagnostics")}
        with patch.object(database.pyodbc, "connect") as connect:
            with self.assertRaises(RestoreCleanupError) as caught:
                self.repository.restore_backup(SQL_FILE, 1)
            connect.assert_not_called()
        self.assertNotIn("private", str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)
        self.assertIsNone(session.current_user)
        self.assertEqual((self.qldsv.closed, self.master.closed), (1, 1))

    def test_connection_loss_in_each_nondestructive_operation_invalidates_once(self):
        for fragment, action in (("BACKUP DATABASE", lambda: self.repository.create_backup(SQL_FILE)),
                                 ("HEADERONLY", lambda: self.repository.read_backup_sets(SQL_FILE)),
                                 ("VERIFYONLY", lambda: self.repository.verify_backup(SQL_FILE, 1))):
            qldsv, master = Connection(), Connection(errors={fragment: pyodbc.Error("08S01", "private detail")})
            session.set_authenticated(ADMIN, qldsv, master)
            invalidated = QSignalSpy(session.events.invalidated)
            with self.assertRaises(session.SessionRequiredError):
                action()
            self.assertEqual(invalidated.count(), 1)
            self.assertEqual((qldsv.closed, master.closed), (1, 1))


if __name__ == "__main__":
    unittest.main()
