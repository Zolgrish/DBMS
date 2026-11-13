"""Lecturer menu; grading SPs enforce trusted MAGV/PhanCong scope."""

from app.models.user import User
from app.services.diem_service import DiemService
from app.ui.dashboard_common import DashboardWindow
from app.ui.diem_management import DiemManagementDialog


class LecturerDashboard(DashboardWindow):
    def __init__(self, user: User, diem_service: DiemService | None = None) -> None:
        super().__init__(user, "Bảng điều khiển giảng viên", ("Nhập điểm", "Đổi mật khẩu"))
        self._diem_service = diem_service or DiemService()

    def _handle_action(self, action: str) -> None:
        if action == "Nhập điểm":
            dialog = DiemManagementDialog(diem_service=self._diem_service, parent=self)
            try:
                dialog.exec()
            finally:
                dialog.deleteLater()
            return
        super()._handle_action(action)
