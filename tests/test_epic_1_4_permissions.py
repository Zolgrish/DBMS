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
            User(
                "GV00000001",
                "Admin",
                None,
                "GV00000001",
                True,
                login_name="admin-login",
            ),
            User(
                "SV00000003",
                "SinhVien",
                "SV00000003",
                None,
                True,
                login_name="student-login-03",
            ),
        ]
        self.calls: list[tuple] = []

    def find_all_accounts(self) -> list[User]:
        self.calls.append(("find_all_accounts",))
        return list(self.accounts)

    def lecturer_exists(self, magv: str) -> bool:
        self.calls.append(("lecturer_exists", magv))
        return magv == "GV00000001"

    def create_account(
        self,
        login_name: str,
        password: str | None,
        role: str,
        database_user: str,
    ) -> bytes:
        self.calls.append(
            ("create_account", login_name, password, role, database_user)
        )
        if any(account.login_name == login_name for account in self.accounts):
            raise pyodbc.Error("42000", "Login exists (52004)")
        ui_role = {
            "QLDSV_ADMIN": "Admin",
            "QLDSV_GIANGVIEN": "GiangVien",
            "QLDSV_SINHVIEN": "SinhVien",
        }[role]
        student = ui_role == "SinhVien"
        self.accounts.append(
            User(
                database_user,
                ui_role,
                database_user if student else None,
                None if student else database_user,
                True,
                login_name=login_name,
            )
        )
        return b"fake-sid"

    def delete_account(self, login_name: str) -> None:
        self.calls.append(("delete_account", login_name))
        self.accounts = [
            account for account in self.accounts if account.login_name != login_name
        ]


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
        for identity in (
            None,
            User(
                "SV00000003",
                "SinhVien",
                "SV00000003",
                None,
                True,
                login_name="student-login-03",
            ),
            User(
                "GV00000002",
                "GiangVien",
                None,
                "GV00000002",
                True,
                login_name="lecturer-login-02",
            ),
        ):
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
        session.set_current_user(
            User(
                "GV00000001",
                "Admin",
                None,
                "GV00000001",
                True,
                login_name="admin-login",
            )
        )
        self.assertEqual(len(self.service.find_all_accounts()), 2)
        self.service.create_account(
            "Admin",
            "pw",
            magv="GV00000002",
            login_name="admin-login-02",
        )
        self.service.create_student_account("SV00000004")
        self.service.delete_account("student-login-03")

        self.assertIn(
            (
                "create_account",
                "SV00000004",
                None,
                "QLDSV_SINHVIEN",
                "SV00000004",
            ),
            self.repository.calls,
        )
        self.assertIn(
            (
                "create_account",
                "admin-login-02",
                "pw",
                "QLDSV_ADMIN",
                "GV00000002",
            ),
            self.repository.calls,
        )
        self.assertIn(("delete_account", "student-login-03"), self.repository.calls)
        self.assertFalse(any(a.username == "SV00000003" for a in self.repository.accounts))

    def test_admin_menu_opens_account_list_and_refreshes_after_delete(self) -> None:
        admin = User(
            "GV00000001",
            "Admin",
            None,
            "GV00000001",
            True,
            login_name="admin-login",
        )
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
        self.assertEqual(dialog.account_table.item(0, 0).text(), "GV00000001")
        self.assertEqual(dialog.account_table.item(0, 1).text(), "admin-login")
        dialog.close()
        dashboard.close()

    def test_account_form_switches_identity_fields_with_role(self) -> None:
        dialog = AccountFormDialog("Thêm tài khoản", lambda values: None)
        self.assertTrue(dialog.login_name_input.isEnabled())
        self.assertFalse(dialog.masv_input.isEnabled())
        self.assertTrue(dialog.magv_input.isEnabled())

        dialog.role_combo.setCurrentText("SinhVien")
        self.assertTrue(dialog.masv_input.isEnabled())
        self.assertFalse(dialog.magv_input.isEnabled())
        dialog.masv_input.setText("SV00000003")

        self.assertFalse(hasattr(dialog, "username_input"))
        self.assertTrue(hasattr(dialog, "login_name_input"))
        dialog.role_combo.setCurrentText("Admin")
        self.assertFalse(dialog.masv_input.isEnabled())
        self.assertEqual(dialog.masv_input.text(), "")
        self.assertTrue(dialog.magv_input.isEnabled())
        dialog.close()

    def test_create_form_saves_account_and_reports_duplicate_login_name(self) -> None:
        session.set_current_user(
            User(
                "GV00000001",
                "Admin",
                None,
                "GV00000001",
                True,
                login_name="admin-login",
            )
        )
        list_dialog = AccountManagementDialog(self.service)
        form = AccountFormDialog(
            "Thêm tài khoản",
            lambda values: self.service.create_account(**values),
            parent=list_dialog,
        )
        form.role_combo.setCurrentText("SinhVien")
        form.masv_input.setText("SV00000004")
        form.login_name_input.setText("student-login-04")
        form._save()
        self.assertEqual(form.result(), form.DialogCode.Accepted)
        list_dialog._load_accounts()
        self.assertEqual(list_dialog.account_table.rowCount(), 3)
        created_row = next(
            row
            for row in range(list_dialog.account_table.rowCount())
            if list_dialog.account_table.item(row, 0).text() == "SV00000004"
        )
        self.assertEqual(
            list_dialog.account_table.item(created_row, 1).text(),
            "student-login-04",
        )

        duplicate = AccountFormDialog(
            "Thêm tài khoản",
            lambda values: self.service.create_account(**values),
            parent=list_dialog,
        )
        duplicate.role_combo.setCurrentText("SinhVien")
        duplicate.masv_input.setText("SV00000005")
        duplicate.login_name_input.setText("student-login-04")
        with patch.object(QMessageBox, "warning") as warning:
            duplicate._save()
            self.assertIn("Tên đăng nhập đã tồn tại", warning.call_args.args[2])
        self.assertNotEqual(duplicate.result(), duplicate.DialogCode.Accepted)
        duplicate.close()
        form.close()
        list_dialog.close()

    def test_lecturer_menu_and_trusted_magv_exclude_admin_capabilities(self) -> None:
        lecturer = User(
            "GV00000002",
            "GiangVien",
            None,
            "GV00000002",
            True,
            login_name="lecturer-login-02",
        )
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
        session.set_current_user(
            User(
                "GV00000002",
                "GiangVien",
                None,
                None,
                True,
                login_name="lecturer-login-02",
            )
        )
        with self.assertRaises(PermissionError):
            require_lecturer_magv()
        for identity in (
            User(
                "GV00000001",
                "Admin",
                None,
                "GV00000001",
                True,
                login_name="admin-login",
            ),
            User(
                "SV00000003",
                "SinhVien",
                "SV00000003",
                None,
                True,
                login_name="student-login-03",
            ),
        ):
            session.set_current_user(identity)
            with self.assertRaises(PermissionError):
                require_lecturer_magv()
        session.clear_session()
        with self.assertRaises(PermissionError):
            require_lecturer_magv()

    def test_student_menu_and_score_identity_use_session_masv(self) -> None:
        session.set_current_user(
            User(
                "SV00000003",
                "SinhVien",
                "SV00000003",
                None,
                True,
                login_name="student-login",
            )
        )
        score_service = StudentScoreService()
        dashboard = StudentDashboard(
            User(
                "SV99999999",
                "SinhVien",
                "SV99999999",
                None,
                True,
                login_name="different-dashboard-user",
            ),
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
