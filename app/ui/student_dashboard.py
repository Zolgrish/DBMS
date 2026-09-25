"""Student dashboard with access limited to the student score function."""

from app.models.user import User
from app.ui.dashboard_common import DashboardWindow


class StudentDashboard(DashboardWindow):
    def __init__(self, user: User) -> None:
        super().__init__(user, "Bảng điều khiển sinh viên", ("Xem điểm",))
