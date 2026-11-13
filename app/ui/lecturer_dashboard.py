"""Lecturer menu matching role matrix: profile, assigned classes/students, grading (no delete), password."""

from app.models.user import User
from app.services.diem_service import DiemService
from app.services.role_portal_service import RolePortalService
from app.ui.dashboard_common import DashboardWindow
from app.ui.diem_management import DiemManagementDialog
from app.ui.lecturer_portal import LecturerAssignmentsDialog, LecturerProfileDialog


class LecturerDashboard(DashboardWindow):
    def __init__(
        self,
        user: User,
        diem_service: DiemService | None = None,
        portal_service: RolePortalService | None = None,
    ) -> None:
        super().__init__(
            user,
            "Bảng điều khiển giảng viên",
            ("Hồ sơ cá nhân", "Phân công & Lớp dạy", "Nhập điểm", "Đổi mật khẩu"),
        )
        self._diem_service = diem_service or DiemService()
        self._portal_service = portal_service or RolePortalService()

    def _handle_action(self, action: str) -> None:
        if action == "Hồ sơ cá nhân":
            dialog = LecturerProfileDialog(portal_service=self._portal_service, parent=self)
            try:
                dialog.exec()
            finally:
                dialog.deleteLater()
            return
        if action == "Phân công & Lớp dạy":
            dialog = LecturerAssignmentsDialog(portal_service=self._portal_service, parent=self)
            try:
                dialog.exec()
            finally:
                dialog.deleteLater()
            return
        if action == "Nhập điểm":
            dialog = DiemManagementDialog(diem_service=self._diem_service, parent=self)
            try:
                dialog.exec()
            finally:
                dialog.deleteLater()
            return
        super()._handle_action(action)
