"""Student dashboard with access limited to own profile, class, subjects, scores, and password."""

from PySide6.QtWidgets import QMessageBox

from app.models.user import User
from app.services.role_portal_service import RolePortalService
from app.services.student_score_service import StudentScoreService
from app.ui.dashboard_common import DashboardWindow
from app.ui.student_portal import StudentGradesDialog, StudentProfileDialog


class StudentDashboard(DashboardWindow):
    def __init__(
        self,
        user: User,
        score_service: StudentScoreService | None = None,
        portal_service: RolePortalService | None = None,
    ) -> None:
        super().__init__(
            user,
            "Bảng điều khiển sinh viên",
            ("Hồ sơ & Lớp học", "Bảng điểm cá nhân", "Xem điểm", "Đổi mật khẩu"),
        )
        self._score_service = score_service or StudentScoreService()
        self._portal_service = portal_service or RolePortalService()

    def _handle_action(self, action: str) -> None:
        if action == "Hồ sơ & Lớp học":
            dialog = StudentProfileDialog(portal_service=self._portal_service, parent=self)
            try:
                dialog.exec()
            finally:
                dialog.deleteLater()
            return
        if action == "Bảng điểm cá nhân":
            dialog = StudentGradesDialog(portal_service=self._portal_service, parent=self)
            try:
                dialog.exec()
            finally:
                dialog.deleteLater()
            return
        if action == "Xem điểm":
            try:
                masv = self._score_service.own_masv()
            except PermissionError as error:
                QMessageBox.warning(self, "Không thể xem điểm", str(error))
                return
            QMessageBox.information(
                self,
                "Xem điểm",
                f"Sinh viên {masv}: Vui lòng dùng mục 'Bảng điểm cá nhân' để xem chi tiết điểm.",
            )
            return
        super()._handle_action(action)
