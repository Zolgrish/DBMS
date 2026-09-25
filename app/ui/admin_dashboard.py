"""Admin dashboard and its role-specific menu."""

from app.models.user import User
from app.ui.dashboard_common import DashboardWindow


class AdminDashboard(DashboardWindow):
    def __init__(self, user: User) -> None:
        super().__init__(
            user,
            "Bảng điều khiển quản trị",
            ("Quản lý sinh viên", "Quản lý môn học", "Quản lý tài khoản", "Nhập điểm"),
        )
