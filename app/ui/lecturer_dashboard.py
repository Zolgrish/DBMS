"""Lecturer menu; future grading SPs must enforce trusted MAGV/PhanCong scope."""

from app.models.user import User
from app.ui.dashboard_common import DashboardWindow


class LecturerDashboard(DashboardWindow):
    def __init__(self, user: User) -> None:
        super().__init__(user, "Bảng điều khiển giảng viên", ("Nhập điểm", "Đổi mật khẩu"))
