"""Admin-only business CRUD; SQL remains authoritative for constraints and locks."""

import re

import pyodbc

from app.models.lecturer import Lecturer
from app.repositories.lecturer_repository import LecturerRepository
from app.services.authorization import require_admin
from app.utils import session


class LecturerServiceError(Exception):
    """Safe validation/persistence message for Qt."""


class LecturerService:
    SQL_ERRORS = {
        53001: "Chỉ Admin hợp lệ được quản lý giảng viên.",
        53002: "MAGV phải gồm đúng 10 đơn vị UTF-16, không có khoảng trắng ở đầu hoặc cuối.",
        53003: "MAGV đã tồn tại trong danh sách giảng viên.",
        53004: "Không tìm thấy giảng viên. Hãy tải lại danh sách.",
        53005: "Họ tối đa 40, tên tối đa 10 đơn vị UTF-16; phái phải là Nam hoặc Nữ.",
        53006: "SQL Login/User của MAGV vẫn tồn tại. Hãy xóa tài khoản trong Quản lý tài khoản trước khi thao tác giảng viên.",
        53007: "Giảng viên còn phân công giảng dạy (PhanCong). Hãy xử lý phân công trước khi xóa.",
        53008: "Không thể lưu dữ liệu giảng viên; thao tác đã được rollback.",
        53009: "Thiếu thành phần hoặc quyền SQL của module giảng viên. Hãy kiểm tra bước triển khai SQL.",
    }

    def __init__(self, lecturer_repository: LecturerRepository | None = None) -> None:
        self._lecturers = lecturer_repository or LecturerRepository()

    def find_all_lecturers(self) -> list[Lecturer]:
        require_admin()
        return self._execute(self._lecturers.find_all)

    def create_lecturer(self, magv: str, ho: str | None = None, ten: str | None = None, phai: bool = True) -> None:
        require_admin()
        magv = self._normalize_magv(magv)
        self._validate_magv(magv)
        ho, ten, phai = self._validate_fields(ho, ten, phai)
        self._execute(self._lecturers.create, magv, ho, ten, phai)

    def update_lecturer(self, magv: str, ho: str | None = None, ten: str | None = None, phai: bool = True) -> None:
        require_admin()
        magv = self._normalize_magv(magv)
        self._validate_magv(magv)
        ho, ten, phai = self._validate_fields(ho, ten, phai)
        self._execute(self._lecturers.update, magv, ho, ten, phai)

    def delete_lecturer(self, magv: str) -> None:
        require_admin()
        magv = self._normalize_magv(magv)
        self._validate_magv(magv)
        self._execute(self._lecturers.delete, magv)

    @staticmethod
    def _normalize_magv(magv):
        return magv.upper() if isinstance(magv, str) else magv

    @staticmethod
    def _utf16_length(value: str) -> int:
        try:
            return len(value.encode("utf-16-le")) // 2
        except UnicodeEncodeError:
            raise LecturerServiceError("Dữ liệu chứa ký tự Unicode không hợp lệ.") from None

    @classmethod
    def _validate_magv(cls, magv: str) -> None:
        if not isinstance(magv, str) or magv != magv.strip() or cls._utf16_length(magv) != 10:
            raise LecturerServiceError(cls.SQL_ERRORS[53002])

    @classmethod
    def _validate_fields(cls, ho, ten, phai):
        for value, maximum in ((ho, 40), (ten, 10)):
            if value is not None and (not isinstance(value, str) or cls._utf16_length(value) > maximum):
                raise LecturerServiceError(cls.SQL_ERRORS[53005])
        if not isinstance(phai, (bool, int)) or phai not in (0, 1):
            raise LecturerServiceError(cls.SQL_ERRORS[53005])
        return (ho.strip() or None) if ho is not None else None, (ten.strip() or None) if ten is not None else None, bool(phai)

    @classmethod
    def _execute(cls, operation, *args):
        try:
            return operation(*args)
        except session.SessionRequiredError:
            raise LecturerServiceError("Phiên SQL không còn hiệu lực. Vui lòng đăng nhập lại.") from None
        except pyodbc.Error as error:
            numbers = re.findall(r"(?<!\d)530\d{2}(?!\d)", " ".join(map(str, error.args)))
            message = next((cls.SQL_ERRORS[int(n)] for n in numbers if int(n) in cls.SQL_ERRORS),
                           "Không thể truy cập dữ liệu giảng viên SQL Server.")
            raise LecturerServiceError(message) from None
