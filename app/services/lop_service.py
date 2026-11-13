"""Business logic and validation for Class (Lop) management."""

import pyodbc

from app.models.lop import Lop
from app.repositories.lop_repository import LopRepository
from app.services.authorization import require_admin
from app.utils import session


class LopServiceError(Exception):
    """Validation or persistence error safe to display in the UI."""


class LopService:
    def __init__(self, lop_repository: LopRepository | None = None) -> None:
        self._lops = lop_repository or LopRepository()

    def find_all(self) -> list[Lop]:
        require_admin()
        return self._execute(self._lops.find_all)

    def create(self, malop: str, tenlop: str) -> None:
        require_admin()
        malop = self._validate_malop(malop)
        tenlop = self._validate_tenlop(tenlop)

        def _op() -> None:
            if self._lops.exists(malop):
                raise LopServiceError(f"Mã lớp '{malop}' đã tồn tại.")
            if self._lops.exists_tenlop(tenlop):
                raise LopServiceError(f"Tên lớp '{tenlop}' đã tồn tại.")
            self._lops.create(malop, tenlop)

        self._execute(_op)

    def update(self, malop: str, tenlop: str) -> None:
        require_admin()
        malop = self._validate_malop(malop)
        tenlop = self._validate_tenlop(tenlop)

        def _op() -> None:
            if not self._lops.exists(malop):
                raise LopServiceError(f"Không tìm thấy lớp '{malop}'. Hãy tải lại danh sách.")
            if self._lops.exists_tenlop(tenlop, exclude_malop=malop):
                raise LopServiceError(f"Tên lớp '{tenlop}' đã tồn tại.")
            self._lops.update(malop, tenlop)

        self._execute(_op)

    def delete(self, malop: str) -> None:
        require_admin()
        malop = self._validate_malop(malop)

        def _op() -> None:
            if not self._lops.exists(malop):
                raise LopServiceError(f"Không tìm thấy lớp '{malop}'. Hãy tải lại danh sách.")
            if self._lops.has_students(malop):
                raise LopServiceError(
                    f"Không thể xóa lớp '{malop}' vì đang có sinh viên thuộc lớp này."
                )
            if self._lops.has_assignments(malop):
                raise LopServiceError(
                    f"Không thể xóa lớp '{malop}' vì đang có phân công giảng dạy."
                )
            self._lops.delete(malop)

        self._execute(_op)

    @staticmethod
    def _utf16_length(value: str) -> int:
        try:
            return len(value.encode("utf-16-le")) // 2
        except UnicodeEncodeError:
            raise LopServiceError("Dữ liệu chứa ký tự Unicode không hợp lệ.") from None

    @classmethod
    def _validate_malop(cls, malop: str) -> str:
        if not isinstance(malop, str):
            raise LopServiceError("Mã lớp không hợp lệ.")
        normalized = malop.strip().upper()
        if not normalized:
            raise LopServiceError("Mã lớp không được để trống.")
        if " " in normalized:
            raise LopServiceError("Mã lớp không được chứa khoảng trắng.")
        if cls._utf16_length(normalized) > 8:
            raise LopServiceError("Mã lớp tối đa 8 ký tự.")
        return normalized

    @classmethod
    def _validate_tenlop(cls, tenlop: str) -> str:
        if not isinstance(tenlop, str):
            raise LopServiceError("Tên lớp không hợp lệ.")
        normalized = tenlop.strip()
        if not normalized:
            raise LopServiceError("Tên lớp không được để trống.")
        if cls._utf16_length(normalized) > 40:
            raise LopServiceError("Tên lớp tối đa 40 ký tự.")
        return normalized

    @staticmethod
    def _execute(operation, *args):
        try:
            return operation(*args)
        except LopServiceError:
            raise
        except session.SessionRequiredError:
            raise LopServiceError("Phiên SQL không còn hiệu lực. Vui lòng đăng nhập lại.") from None
        except pyodbc.Error as error:
            msg = " ".join(map(str, error.args))
            if "FK_" in msg or "REFERENCE" in msg.upper():
                raise LopServiceError("Không thể xóa lớp vì còn dữ liệu liên quan (Sinh viên hoặc Phân công).") from None
            if "UQ_" in msg or "UNIQUE" in msg.upper() or "PRIMARY KEY" in msg.upper() or "2627" in msg:
                raise LopServiceError("Mã lớp hoặc Tên lớp đã tồn tại.") from None
            raise LopServiceError(f"Lỗi truy cập dữ liệu lớp: {msg}") from None

