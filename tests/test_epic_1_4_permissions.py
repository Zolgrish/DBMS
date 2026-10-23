"""Original authorization/UI coverage, migrated to Epic 1.6 account contracts."""

import os
import unittest
from unittest.mock import patch

import pyodbc

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from app.models.user import User
from app.services.account_service import AccountService
from app.services.student_score_service import StudentScoreService
from app.ui.account_management import AccountFormDialog, AccountManagementDialog
from app.ui.admin_dashboard import AdminDashboard
from app.ui.student_dashboard import StudentDashboard
from app.ui.lecturer_dashboard import LecturerDashboard
from app.services.authorization import require_lecturer_magv
from app.utils import session


class FakeAccountRepository:
    def __init__(self) -> None:
        self.accounts = [
            User("admin", "Admin", None, None, True),
            User("SV00000003", "SinhVien", "SV00000003", None, True),
        ]
        self.calls: list[tuple] = []

    def find_all_accounts(self) -> list[User]:
        self.calls.append(("find_all_accounts",))
        return list(self.accounts)

    def lecturer_exists(self, magv: str) -> bool:
        self.calls.append(("lecturer_exists", magv))
        return magv == "GV00000001"

    def create_account(
        self, username: str, password: str | None, role: str
    ) -> None:
        self.calls.append(("create_account", username, password, role))
        if any(account.username == username for account in self.accounts):
            raise pyodbc.Error("42000", "Login exists (52004)")
        student = role == "QLDSV_SINHVIEN"
        self.accounts.append(User(username, "SinhVien" if student else "Admin", username if student else None, None, True))

    def delete_account(self, username: str) -> None:
        self.calls.append(("delete_account", username))
        self.accounts = [account for account in self.accounts if account.username != username]


class Epic14PermissionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        session.clear_session()
        self.repository = FakeAccountRepository()
        self.service = AccountService(self.repository)

    def tearDown(self) -> None:
        session.clear_session()

    def test_student_and_guest_cannot_call_account_service(self) -> None:
        operations = (
            ("list", lambda: self.service.find_all_accounts()),
            ("create", lambda: self.service.create_account("Admin", "pw", magv="GV00000002")),
            ("auto-create", lambda: self.service.create_student_account("SV00000004")),
            ("delete", lambda: self.service.delete_account("other")),
        )
        for identity in (None, User("student", "SinhVien", "SV00000003", None, True),
                         User("GV00000002", "GiangVien", None, "GV00000002", True)):
            if identity is None:
                session.clear_session()
            else:
                session.set_current_user(identity)
            for name, operation in operations:
                with self.subTest(identity=identity, operation=name):
                    with self.assertRaises(PermissionError):
                        operation()
                    self.assertEqual(self.repository.calls, [])

    def test_admin_can_use_account_operations(self) -> None:
        session.set_current_user(User("admin", "Admin", None, None, True))
        self.assertEqual(len(self.service.find_all_accounts()), 2)
        self.service.create_account("Admin", "pw", magv="GV00000002")
        self.service.create_student_account("SV00000004")
        self.service.delete_account("SV00000003")

        self.assertIn(
            ("create_account", "SV00000004", None, "QLDSV_SINHVIEN"),
            self.repository.calls,
        )
        self.assertFalse(any(a.username == "SV00000003" for a in self.repository.accounts))

    def test_admin_menu_opens_account_list_and_refreshes_after_delete(self) -> None:
        admin = User("admin", "Admin", None, None, True)
        session.set_current_user(admin)
        dashboard = AdminDashboard(admin, self.service)
        buttons = [button.text() for button in dashboard.findChildren(QPushButton)]
        self.assertIn("Quản lý tài khoản", buttons)
        self.assertIn("Quản lý giảng viên", buttons)

        with patch("app.ui.admin_dashboard.AccountManagementDialog") as dialog_class:
            next(
                button
                for button in dashboard.findChildren(QPushButton)
                if button.text() == "Quản lý tài khoản"
            ).click()
            dialog_class.assert_called_once_with(account_service=self.service, parent=dashboard)
            dialog_class.return_value.exec.assert_called_once()

        dialog = AccountManagementDialog(self.service, parent=dashboard)
        self.assertEqual(dialog.account_table.rowCount(), 2)
        student_row = next(
            row
            for row in range(dialog.account_table.rowCount())
            if dialog.account_table.item(row, 0).text() == "SV00000003"
        )
        dialog.account_table.selectRow(student_row)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            dialog.delete_button.click()
        self.assertEqual(dialog.account_table.rowCount(), 1)
        self.assertEqual(dialog.account_table.item(0, 0).text(), "admin")
        dialog.close()
        dashboard.close()

    def test_account_form_switches_identity_fields_with_role(self) -> None:
        dialog = AccountFormDialog("Thêm tài khoản", lambda values: None)
        self.assertFalse(dialog.masv_input.isEnabled())
        self.assertTrue(dialog.magv_input.isEnabled())

        dialog.role_combo.setCurrentText("SinhVien")
        self.assertTrue(dialog.masv_input.isEnabled())
        self.assertFalse(dialog.magv_input.isEnabled())
        dialog.masv_input.setText("SV00000003")

        self.assertFalse(hasattr(dialog, "username_input"))
        dialog.role_combo.setCurrentText("Admin")
        self.assertFalse(dialog.masv_input.isEnabled())
        self.assertEqual(dialog.masv_input.text(), "")
        self.assertTrue(dialog.magv_input.isEnabled())
        dialog.close()

    def test_create_form_saves_account_and_reports_duplicate_username(self) -> None:
        session.set_current_user(User("admin", "Admin", None, None, True))
        list_dialog = AccountManagementDialog(self.service)
        form = AccountFormDialog(
            "Thêm tài khoản",
            lambda values: self.service.create_account(**values),
            parent=list_dialog,
        )
        form.role_combo.setCurrentText("SinhVien")
        form.masv_input.setText("SV00000004")
        form._save()
        self.assertEqual(form.result(), form.DialogCode.Accepted)
        list_dialog._load_accounts()
        self.assertEqual(list_dialog.account_table.rowCount(), 3)

        duplicate = AccountFormDialog(
            "Thêm tài khoản",
            lambda values: self.service.create_account(**values),
            parent=list_dialog,
        )
        duplicate.role_combo.setCurrentText("SinhVien")
        duplicate.masv_input.setText("SV00000004")
        duplicate.password_input.setText("123456")
        with patch.object(QMessageBox, "warning") as warning:
            duplicate._save()
            self.assertIn("Tên đăng nhập đã tồn tại", warning.call_args.args[2])
        self.assertNotEqual(duplicate.result(), duplicate.DialogCode.Accepted)
        duplicate.close()
        form.close()
        list_dialog.close()

    def test_lecturer_menu_and_trusted_magv_exclude_admin_capabilities(self) -> None:
        lecturer = User("GV00000002", "GiangVien", None, "GV00000002", True)
        session.set_current_user(lecturer)
        dashboard = LecturerDashboard(lecturer)
        self.addCleanup(dashboard.close)
        labels = [button.text() for button in dashboard.findChildren(QPushButton)]
        for expected in ("Nhập điểm", "Đổi mật khẩu"):
            self.assertIn(expected, labels)
        for forbidden in ("Quản lý tài khoản", "Quản lý sinh viên", "Quản lý giảng viên",
                          "Quản lý môn học", "Sao lưu / Phục hồi"):
            self.assertNotIn(forbidden, labels)
        self.assertEqual(require_lecturer_magv(), "GV00000002")
        session.set_current_user(User("drift", "GiangVien", None, None, True))
        with self.assertRaises(PermissionError):
            require_lecturer_magv()
        for role in ("Admin", "SinhVien"):
            session.set_current_user(User("x", role, None, "GV00000002", True))
            with self.assertRaises(PermissionError):
                require_lecturer_magv()
        session.clear_session()
        with self.assertRaises(PermissionError):
            require_lecturer_magv()

    def test_student_menu_and_score_identity_use_session_masv(self) -> None:
        session.set_current_user(User("student-login", "SinhVien", "SV00000003", None, True))
        score_service = StudentScoreService()
        dashboard = StudentDashboard(
            User("different-dashboard-user", "SinhVien", "SV99999999", None, True),
            score_service=score_service,
        )
        buttons = [button.text() for button in dashboard.findChildren(QPushButton)]
        self.assertIn("Xem điểm", buttons)
        self.assertNotIn("Quản lý tài khoản", buttons)
        self.assertNotIn("Quản lý giảng viên", buttons)
        self.assertEqual(score_service.own_masv(), "SV00000003")
        with self.assertRaises(TypeError):
            score_service.own_masv("SV99999999")

        with (
            patch.object(score_service, "own_masv", wraps=score_service.own_masv) as own_masv,
            patch.object(QMessageBox, "information") as information,
        ):
            next(
                button
                for button in dashboard.findChildren(QPushButton)
                if button.text() == "Xem điểm"
            ).click()
            own_masv.assert_called_once_with()
            information.assert_called_once()
        dashboard.close()


if __name__ == "__main__":
    unittest.main()
