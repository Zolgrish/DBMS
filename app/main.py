"""Application entry point and role-based window routing."""

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication, QMessageBox

from app.models.user import User
from app.services.auth_service import AuthService
from app.ui.admin_dashboard import AdminDashboard
from app.ui.dashboard_common import DashboardWindow
from app.ui.login import LoginWindow
from app.ui.student_dashboard import StudentDashboard
from app.utils import session


class ApplicationRouter:
    """Own the login window and switch dashboards based on authenticated role."""

    def __init__(self, auth_service: AuthService | None = None) -> None:
        self.login_window = LoginWindow(auth_service or AuthService())
        self.dashboard: DashboardWindow | None = None
        self.login_window.authenticated.connect(self.open_dashboard)

    def start(self) -> None:
        self.login_window.show()

    def open_dashboard(self, user: User) -> None:
        if user.role == "Admin":
            self.dashboard = AdminDashboard(user)
        elif user.role == "SinhVien":
            self.dashboard = StudentDashboard(user)
        else:
            session.clear_session()
            QMessageBox.information(
                self.login_window,
                "Chưa hỗ trợ vai trò",
                "Tài khoản giảng viên đã được xác thực, nhưng giao diện riêng chưa được triển khai.",
            )
            return

        self.dashboard.logout_requested.connect(self.return_to_login)
        self.login_window.hide()
        self.dashboard.show()

    def return_to_login(self) -> None:
        session.clear_session()
        if self.dashboard is not None:
            self.dashboard.close()
            self.dashboard = None
        self.login_window.prepare_for_logout()
        self.login_window.show()
        self.login_window.activateWindow()


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("Quản lý điểm sinh viên")
    router = ApplicationRouter()
    router.start()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
