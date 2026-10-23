"""Admin-only SQL Login/User account operations and safe UI errors."""

import re

import pyodbc

from app.models.user import User
from app.repositories.account_repository import AccountRepository
from app.services.authorization import require_admin
from app.utils import session


class AccountServiceError(Exception):
    """Validation or persistence error safe to display in the UI."""


class AccountService:
    ROLES = {"Admin", "GiangVien", "SinhVien"}
    SQL_ROLES = {"Admin": "QLDSV_ADMIN", "GiangVien": "QLDSV_GIANGVIEN", "SinhVien": "QLDSV_SINHVIEN"}
    SQL_ERRORS = {
        52001: "Phiên SQL không có quyền quản lý tài khoản. Vui lòng đăng nhập bằng Admin hợp lệ.",
        52002: "Tên đăng nhập không hợp lệ hoặc là tên dành riêng của SQL Server.",
        52003: "Vai trò không hợp lệ. Chỉ hỗ trợ Admin, GiangVien và SinhVien.",
        52004: "Tên đăng nhập đã tồn tại.",
        52005: "Database User hoặc SID đã tồn tại; cần kiểm tra mapping SQL Login/User.",
        52006: "Mật khẩu không hợp lệ. Admin/GiangVien dùng mật khẩu mặc định khi để trống hoặc mật khẩu theo CHECK_POLICY; sinh viên dùng mặc định do SQL Server cấp.",
        52007: "Không tìm thấy MASV hợp lệ gồm 10 ký tự trong danh sách sinh viên.",
        52008: "Thiếu database role bắt buộc. Hãy kiểm tra cấu hình bảo mật SQL Server.",
        52009: "Không thể tạo tài khoản. Kiểm tra chính sách mật khẩu Admin/GiangVien và quyền tạo SQL Login/User.",
        52010: "Tài khoản SQL không tồn tại.",
        52011: "SQL Login/User có mapping không hợp lệ. Hãy kiểm tra trước khi xóa.",
        52012: "Tài khoản có role hoặc membership không nhất quán; không thể xóa.",
        52013: "Tài khoản đang sở hữu database, schema, object hoặc role; cần xử lý quyền sở hữu trước.",
        52014: "Không thể xóa tài khoản đang đăng nhập.",
        52015: "Không thể xóa tài khoản. Nếu có phiên SQL đang hoạt động, hãy đăng xuất trước khi xóa; "
               "nếu vẫn lỗi, kiểm tra quyền sở hữu và quyền xóa tài khoản.",
        52016: "Danh tính SQL của tài khoản đã thay đổi; thao tác xóa bị từ chối.",
        52017: "Không tìm thấy MAGV hợp lệ gồm 10 ký tự trong danh sách giảng viên.",
    }

    def __init__(self, account_repository: AccountRepository | None = None) -> None:
        self._accounts = account_repository or AccountRepository()

    def find_all_accounts(self) -> list[User]:
        require_admin()
        try:
            return self._accounts.find_all_accounts()
        except session.SessionRequiredError:
            self._raise_session_error()
        except pyodbc.Error as error:
            self._raise_database_error(error)

    def create_account(
        self,
        role: str,
        password: str | None = None,
        masv: str = "",
        magv: str = "",
    ) -> bytes:
        require_admin()
        role, masv, magv = role.strip(), masv.strip().upper(), magv.strip().upper()
        if role not in self.ROLES:
            raise AccountServiceError("Vai trò không hợp lệ.")
        if role == "SinhVien":
            if not masv:
                raise AccountServiceError("Tài khoản sinh viên yêu cầu MASV.")
            if password:
                raise AccountServiceError("Sinh viên dùng mật khẩu mặc định do SQL Server cấp; không được ghi đè.")
            if magv:
                raise AccountServiceError("Tài khoản sinh viên không sử dụng MAGV.")
            password = None
            login_name = masv
        else:
            if not magv:
                raise AccountServiceError("Tài khoản Admin/GiangVien yêu cầu MAGV.")
            if masv:
                raise AccountServiceError("Tài khoản Admin/GiangVien không sử dụng MASV.")
            login_name = magv
            password = password or None
        self._validate_username(login_name)

        try:
            # SQL validates the existing entity with locks, collisions and password policy atomically.
            return self._accounts.create_account(login_name, password, self.SQL_ROLES[role])
        except session.SessionRequiredError:
            self._raise_session_error()
        except pyodbc.Error as error:
            self._raise_database_error(error)
        finally:
            password = None

    def create_student_account(self, masv: str) -> bytes:
        require_admin()
        masv = masv.strip().upper()
        return self.create_account(role="SinhVien", masv=masv)

    def create_lecturer_account(self, magv: str, role: str = "GiangVien", password: str | None = None) -> bytes:
        require_admin()
        if role not in {"Admin", "GiangVien"}:
            raise AccountServiceError("Tài khoản giảng viên chỉ hỗ trợ Admin hoặc GiangVien.")
        return self.create_account(role=role, password=password, magv=magv)

    def delete_account(self, username: str) -> None:
        require_admin()
        username = username.strip()
        self._validate_username(username)
        if username.casefold() == session.current_user["username"].casefold():
            raise AccountServiceError(self.SQL_ERRORS[52014])
        try:
            self._accounts.delete_account(username)
        except session.SessionRequiredError:
            self._raise_session_error()
        except pyodbc.Error as error:
            self._raise_database_error(error)

    @staticmethod
    def _validate_username(username: str) -> None:
        if not username:
            raise AccountServiceError("Tên đăng nhập không được để trống.")
        if len(username.encode("utf-16-le")) > 256:
            raise AccountServiceError("Tên đăng nhập không được vượt quá 128 đơn vị UTF-16.")

    @staticmethod
    def _raise_session_error() -> None:
        raise AccountServiceError("Phiên SQL không còn hiệu lực. Vui lòng đăng nhập lại.") from None

    @classmethod
    def _raise_database_error(cls, error: pyodbc.Error) -> None:
        # Read only known SQL error numbers; never display or log driver diagnostics.
        numbers = re.findall(r"(?<!\d)520\d{2}(?!\d)", " ".join(str(part) for part in error.args))
        message = next((cls.SQL_ERRORS[int(number)] for number in numbers if int(number) in cls.SQL_ERRORS),
                       "Không thể truy cập dữ liệu tài khoản SQL Server.")
        raise AccountServiceError(message) from None
