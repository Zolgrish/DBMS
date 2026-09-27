"""Account-management rules for administrators and student-account creation."""

import logging

import pyodbc

from app.models.user import User
from app.repositories.account_repository import AccountRepository
from app.services.authorization import require_admin
from app.utils import session


class AccountServiceError(Exception):
    """Validation or persistence error safe to display in the UI."""


class AccountService:
    DEFAULT_STUDENT_PASSWORD = "123456"
    ROLES = {"Admin", "SinhVien", "GiangVien"}

    def __init__(self, account_repository: AccountRepository | None = None) -> None:
        self._accounts = account_repository or AccountRepository()

    def find_all_accounts(self) -> list[User]:
        require_admin()
        try:
            return self._accounts.find_all_accounts()
        except pyodbc.Error:
            self._raise_database_error()

    def create_account(
        self,
        username: str,
        password: str,
        role: str,
        masv: str = "",
        magv: str = "",
    ) -> None:
        require_admin()
        username = username.strip()
        if not username:
            raise AccountServiceError("Username không được để trống.")
        if not password:
            raise AccountServiceError("Mật khẩu không được để trống.")
        if len(username) > 50:
            raise AccountServiceError("Username không được vượt quá 50 ký tự.")
        if len(password) > 255:
            raise AccountServiceError("Mật khẩu không được vượt quá 255 ký tự.")

        try:
            if self._accounts.exists_username(username):
                raise AccountServiceError("Username đã tồn tại")
            role, masv, magv = self._validate_role_links(role, masv, magv)
            self._accounts.create_account(username, password, role, masv, magv)
        except AccountServiceError:
            raise
        except pyodbc.IntegrityError as error:
            self._raise_integrity_error(error, username_duplicate=True)
        except pyodbc.Error:
            self._raise_database_error()

    def create_student_account(self, masv: str) -> None:
        require_admin()
        masv = masv.strip()
        if not masv:
            raise AccountServiceError("MASV không được để trống.")
        self.create_account(
            username=masv,
            password=self.DEFAULT_STUDENT_PASSWORD,
            role="SinhVien",
            masv=masv,
        )

    def update_account(
        self,
        username: str,
        role: str,
        masv: str = "",
        magv: str = "",
    ) -> None:
        require_admin()
        username = username.strip()
        if not username:
            raise AccountServiceError("Username không được để trống.")

        role, masv, magv = self._validate_role_links(role, masv, magv)
        try:
            if not self._accounts.exists_username(username):
                raise AccountServiceError("Không tìm thấy username.")
            if not self._accounts.update_account(username, role, masv, magv):
                raise AccountServiceError("Không tìm thấy username.")
        except AccountServiceError:
            raise
        except pyodbc.IntegrityError as error:
            self._raise_integrity_error(error, username_duplicate=False)
        except pyodbc.Error:
            self._raise_database_error()

    def update_account_status(self, username: str, status: bool) -> None:
        require_admin()
        username = username.strip()
        if not username:
            raise AccountServiceError("Username không được để trống.")

        current_user = session.current_user
        if (
            not status
            and current_user is not None
            and current_user.get("username", "").casefold() == username.casefold()
        ):
            raise AccountServiceError("Không thể khóa tài khoản đang đăng nhập.")

        try:
            if not self._accounts.update_account_status(username, status):
                raise AccountServiceError("Không tìm thấy username.")
        except AccountServiceError:
            raise
        except pyodbc.Error:
            self._raise_database_error()

    def _validate_role_links(
        self,
        role: str,
        masv: str,
        magv: str,
    ) -> tuple[str, str | None, str | None]:
        role = role.strip()
        masv = masv.strip()
        magv = magv.strip()
        if role not in self.ROLES:
            raise AccountServiceError("Vai trò không hợp lệ.")

        if role == "Admin":
            return role, None, None

        try:
            if role == "SinhVien":
                if not masv:
                    raise AccountServiceError("Sinh viên cần có MASV.")
                if not self._accounts.student_exists(masv):
                    raise AccountServiceError("Không tìm thấy MASV trong dbo.Sinhvien.")
                return role, masv, None

            if not magv:
                raise AccountServiceError("Giảng viên cần có MAGV.")
            if not self._accounts.lecturer_exists(magv):
                raise AccountServiceError("Không tìm thấy MAGV trong dbo.Giangvien.")
            return role, None, magv
        except AccountServiceError:
            raise
        except pyodbc.Error:
            self._raise_database_error()

    @staticmethod
    def _raise_integrity_error(error: pyodbc.IntegrityError, username_duplicate: bool) -> None:
        details = " ".join(str(part) for part in error.args)
        if username_duplicate and (
            "PK_TaiKhoan" in details
            or (
                any(marker in details for marker in ("2627", "2601"))
                and "UX_TaiKhoan_" not in details
            )
        ):
            raise AccountServiceError("Username đã tồn tại") from None
        raise AccountServiceError(
            "Mã sinh viên hoặc giảng viên đã được liên kết với tài khoản khác."
        ) from None

    @staticmethod
    def _raise_database_error() -> None:
        logging.exception("Không thể truy cập dữ liệu tài khoản trong SQL Server.")
        raise AccountServiceError("Không thể truy cập cơ sở dữ liệu.") from None
