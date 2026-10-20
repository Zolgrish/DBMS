"""Epic 1.6 checks; no test restores the real QLDSV database."""

from datetime import datetime
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pyodbc
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from app.models.user import User
from app.repositories.backup_restore_repository import BackupRestoreRepository
from app.services.backup_restore_service import BackupRestoreError, BackupRestoreService
from app.ui.admin_dashboard import AdminDashboard
from app.ui.backup_restore import BackupRestoreDialog
from app.ui.student_dashboard import StudentDashboard
from app.utils import session


class FakeBackupRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Path]] = []
        self.backup_error: Exception | None = None
        self.verify_error: Exception | None = None
        self.restore_error: Exception | None = None

    def create_backup(self, path: Path) -> None:
        self.calls.append(("backup", path))
        if self.backup_error:
            raise self.backup_error
        path.write_bytes(b"unit-test backup placeholder")

    def verify_backup(self, path: Path) -> None:
        self.calls.append(("verify", path))
        if self.verify_error:
            raise self.verify_error

    def restore_backup(self, path: Path) -> None:
        self.calls.append(("restore", path))
        if self.restore_error:
            raise self.restore_error


class BackupRestoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.repository = FakeBackupRepository()
        self.service = BackupRestoreService(self.repository, self.directory)
        session.set_current_user(User("admin", "Admin", None, None, True))

    def tearDown(self) -> None:
        session.clear_session()
        self.temporary_directory.cleanup()

    def test_admin_menu_opens_backup_restore_screen(self) -> None:
        user = User("admin", "Admin", None, None, True)
        dashboard = AdminDashboard(user, backup_service=self.service)
        observed = []

        def inspect_dialog() -> None:
            dialogs = [
                widget for widget in QApplication.topLevelWidgets()
                if isinstance(widget, BackupRestoreDialog) and widget.isVisible()
            ]
            observed.append(len(dialogs) == 1 and dialogs[0].parent() is dashboard)
            if dialogs:
                dialogs[0].reject()

        QTimer.singleShot(0, inspect_dialog)
        next(
            button for button in dashboard.findChildren(QPushButton)
            if button.text() == "Sao lưu / Phục hồi"
        ).click()
        self.assertEqual(observed, [True])
        dashboard.close()

    def test_student_menu_hides_backup_restore(self) -> None:
        user = User("SV00000001", "SinhVien", "SV00000001", None, True)
        session.set_current_user(user)
        dashboard = StudentDashboard(user)
        labels = [button.text() for button in dashboard.findChildren(QPushButton)]
        self.assertNotIn("Sao lưu / Phục hồi", labels)
        dashboard.close()

    def test_student_direct_service_calls_are_rejected_before_repository_access(self) -> None:
        session.set_current_user(User("SV00000001", "SinhVien", "SV00000001", None, True))
        operations = (
            self.service.configured_directory,
            self.service.list_backups,
            self.service.backup_database,
            lambda: self.service.restore_database("missing.bak"),
        )
        for operation in operations:
            with self.subTest(operation=operation):
                with self.assertRaises(PermissionError):
                    operation()
        self.assertEqual(self.repository.calls, [])

    def test_generated_backup_filename_has_timestamp_and_bak_extension(self) -> None:
        name = self.service.generate_filename(datetime(2026, 9, 27, 14, 3, 5, 123456))
        self.assertEqual(name, "QLDSV_20260927_140305_123456.bak")

    def test_missing_backup_directory_has_friendly_error(self) -> None:
        service = BackupRestoreService(self.repository, self.directory / "missing")
        with self.assertRaisesRegex(BackupRestoreError, "Thư mục sao lưu không tồn tại"):
            service.list_backups()
        self.assertEqual(self.repository.calls, [])

    def test_backup_database_exception_is_translated(self) -> None:
        self.repository.backup_error = pyodbc.Error("42000", "access denied")
        with self.assertRaisesRegex(BackupRestoreError, "SQL Server không thể tạo file sao lưu"):
            self.service.backup_database()

    def test_backup_creation_and_list_include_file_time(self) -> None:
        backup = self.service.backup_database()
        self.assertRegex(backup.filename, r"^QLDSV_\d{8}_\d{6}_\d{6}\.bak$")
        self.assertTrue(backup.path.is_file())
        listed = self.service.list_backups()
        self.assertEqual([item.filename for item in listed], [backup.filename])
        self.assertIsInstance(listed[0].modified_at, datetime)

    def test_backup_button_refreshes_the_visible_list(self) -> None:
        dialog = BackupRestoreDialog(self.service)
        self.assertEqual(dialog.backup_table.rowCount(), 0)
        with patch.object(QMessageBox, "information") as information:
            dialog.backup_button.click()
        information.assert_called_once()
        self.assertEqual(dialog.backup_table.rowCount(), 1)
        dialog.close()

    def test_restore_requires_confirmation_in_ui(self) -> None:
        (self.directory / "QLDSV_existing.bak").write_bytes(b"unit-test backup placeholder")
        dialog = BackupRestoreDialog(self.service)
        dialog.backup_table.selectRow(0)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            dialog.restore_button.click()
        self.assertEqual(self.repository.calls, [])
        self.assertFalse(dialog.restore_performed)
        self.assertEqual(dialog.status_label.text(), "Đã hủy phục hồi.")

        with (
            patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes),
            patch.object(QMessageBox, "information"),
        ):
            dialog.restore_button.click()
        self.assertEqual([call[0] for call in self.repository.calls], ["verify", "restore"])
        self.assertTrue(dialog.restore_performed)
        dialog.close()

    def test_invalid_or_missing_backup_file_is_rejected(self) -> None:
        for filename in ("missing.bak", "../outside.bak", "not-a-backup.txt"):
            with self.subTest(filename=filename):
                with self.assertRaises(BackupRestoreError):
                    self.service.restore_database(filename)
        self.assertEqual(self.repository.calls, [])

        (self.directory / "corrupt.bak").write_bytes(b"not a SQL backup")
        self.repository.verify_error = pyodbc.Error("42000", "invalid backup")
        with self.assertRaisesRegex(BackupRestoreError, "File có thể hỏng"):
            self.service.restore_database("corrupt.bak")
        self.assertEqual([call[0] for call in self.repository.calls], ["verify"])

    def test_restore_failure_still_attempts_multi_user(self) -> None:
        sql_calls = []

        class FailingCursor:
            description = None

            def nextset(self):
                return False

            def execute(self, sql, *parameters):
                sql_calls.append(sql)
                if "RESTORE DATABASE" in sql:
                    raise pyodbc.Error("42000", "restore failed")
                return self

            def close(self):
                pass

        class FakeConnection:
            def __init__(self):
                self.closed = False

            def cursor(self):
                return FailingCursor()

            def close(self):
                self.closed = True

        connection = FakeConnection()
        session.set_authenticated(User("admin", "Admin", None, None, True), None, connection)
        with self.assertRaises(pyodbc.Error):
            BackupRestoreRepository().restore_backup(self.directory / "existing.bak")
        self.assertTrue(connection.closed)
        self.assertTrue(any("SET SINGLE_USER" in sql for sql in sql_calls))
        self.assertTrue(any("SET MULTI_USER" in sql for sql in sql_calls))

    def test_sql_backup_waits_for_all_odbc_result_sets(self) -> None:
        class FakeCursor:
            description = None

            def __init__(self):
                self.nextset_calls = 0
                self.closed = False

            def execute(self, sql, *parameters):
                self.sql = sql
                self.parameters = parameters
                return self

            def nextset(self):
                self.nextset_calls += 1
                return self.nextset_calls == 1

            def close(self):
                self.closed = True

        class FakeConnection:
            def __init__(self):
                self.statement = FakeCursor()
                self.closed = False

            def cursor(self):
                return self.statement

            def close(self):
                self.closed = True

        connection = FakeConnection()
        session.set_authenticated(User("admin", "Admin", None, None, True), None, connection)
        BackupRestoreRepository().create_backup(self.directory / "QLDSV_test.bak")
        self.assertIn("BACKUP DATABASE [QLDSV]", connection.statement.sql)
        self.assertEqual(connection.statement.nextset_calls, 2)
        self.assertTrue(connection.statement.closed)
        self.assertFalse(connection.closed)


if __name__ == "__main__":
    unittest.main()
