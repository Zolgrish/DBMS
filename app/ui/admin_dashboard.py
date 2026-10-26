"""Admin dashboard and its role-specific menu."""

from app.models.user import User
from app.services.account_service import AccountService
from app.services.backup_restore_service import BackupRestoreService
from app.services.lecturer_service import LecturerService
from app.ui.account_management import AccountManagementDialog
from app.ui.backup_restore import BackupRestoreDialog
from app.ui.dashboard_common import DashboardWindow
from app.ui.lecturer_management import LecturerManagementDialog


class AdminDashboard(DashboardWindow):
    def __init__(
        self,
        user: User,
        account_service: AccountService | None = None,
        backup_service: BackupRestoreService | None = None,
        lecturer_service: LecturerService | None = None,
    ) -> None:
        super().__init__(
            user,
            "Bảng điều khiển quản trị",
            (
                "Quản lý sinh viên",
                "Quản lý giảng viên",
                "Quản lý môn học",
                "Quản lý tài khoản",
                "Nhập điểm",
                "Đổi mật khẩu",
                "Sao lưu / Phục hồi",
            ),
        )
        self._account_service = account_service or AccountService()
        self._backup_service = backup_service or BackupRestoreService()
        self._lecturer_service = lecturer_service or LecturerService()

    def _handle_action(self, action: str) -> None:
        if action == "Quản lý giảng viên":
            dialog = LecturerManagementDialog(lecturer_service=self._lecturer_service, parent=self)
            try:
                dialog.exec()
            finally:
                dialog.deleteLater()
            return
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
        if action == "Sao lưu / Phục hồi":
            dialog = BackupRestoreDialog(backup_service=self._backup_service, parent=self)
            try:
                dialog.exec()
            finally:
                dialog.deleteLater()
            # Repository invalidation routes both successful and failed restore
            # attempts back to Login. Do not emit a second logout transition.
            return
        super()._handle_action(action)
