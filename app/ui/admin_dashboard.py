"""Admin dashboard and its role-specific menu."""

from app.models.user import User
from app.services.account_service import AccountService
from app.ui.account_management import AccountManagementDialog
from app.ui.dashboard_common import DashboardWindow


class AdminDashboard(DashboardWindow):
    def __init__(
        self,
        user: User,
        account_service: AccountService | None = None,
    ) -> None:
        super().__init__(
            user,
            "Bảng điều khiển quản trị",
            (
                "Quản lý sinh viên",
                "Quản lý môn học",
                "Quản lý tài khoản",
                "Nhập điểm",
                "Đổi mật khẩu",
            ),
        )
        self._account_service = account_service or AccountService()

    def _handle_action(self, action: str) -> None:
        if action == "Quản lý tài khoản":
            dialog = AccountManagementDialog(
                account_service=self._account_service,
                parent=self,
            )
            try:
                dialog.exec()
            finally:
                dialog.deleteLater()
            return
        super()._handle_action(action)
