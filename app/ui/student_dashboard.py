"""Student dashboard with access limited to the student score function."""

from PySide6.QtWidgets import QMessageBox

from app.models.user import User
from app.services.student_score_service import StudentScoreService
from app.ui.dashboard_common import DashboardWindow


class StudentDashboard(DashboardWindow):
    def __init__(
        self,
        user: User,
        score_service: StudentScoreService | None = None,
    ) -> None:
        super().__init__(
            user,
            "Bảng điều khiển sinh viên",
            ("Xem điểm", "Đổi mật khẩu"),
        )
        self._score_service = score_service or StudentScoreService()

    def _handle_action(self, action: str) -> None:
        if action == "Xem điểm":
            try:
                masv = self._score_service.own_masv()
            except PermissionError as error:
                QMessageBox.warning(self, "Không thể xem điểm", str(error))
                return
            QMessageBox.information(
                self,
                "Xem điểm",
                f"Chức năng xem điểm cho sinh viên sẽ được bổ sung sau.",
            )
            return
        super()._handle_action(action)
