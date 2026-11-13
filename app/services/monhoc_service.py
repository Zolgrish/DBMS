"""Business logic and validation for Subject (Monhoc) management."""

import pyodbc

from app.models.monhoc import Monhoc
from app.repositories.monhoc_repository import MonhocRepository
from app.services.authorization import require_admin
from app.utils import session


class MonhocServiceError(Exception):
    """Validation or persistence error safe to display in the UI."""


class MonhocService:
    def __init__(self, monhoc_repository: MonhocRepository | None = None) -> None:
        self._monhocs = monhoc_repository or MonhocRepository()

    def find_all(self) -> list[Monhoc]:
        require_admin()
        return self._execute(self._monhocs.find_all)

    def create(self, mamh: str, tenmh: str, sotclt: int, sotcth: int) -> None:
        require_admin()
        mamh = self._validate_mamh(mamh)
        tenmh = self._validate_tenmh(tenmh)
        sotclt, sotcth = self._validate_credits(sotclt, sotcth)

        def _op() -> None:
            if self._monhocs.exists(mamh):
                raise MonhocServiceError(f"Mã môn học '{mamh}' đã tồn tại.")
            if self._monhocs.exists_tenmh(tenmh):
                raise MonhocServiceError(f"Tên môn học '{tenmh}' đã tồn tại.")
            self._monhocs.create(mamh, tenmh, sotclt, sotcth)

        self._execute(_op)

    def update(self, mamh: str, tenmh: str, sotclt: int, sotcth: int) -> None:
        require_admin()
        mamh = self._validate_mamh(mamh)
        tenmh = self._validate_tenmh(tenmh)
        sotclt, sotcth = self._validate_credits(sotclt, sotcth)

        def _op() -> None:
            if not self._monhocs.exists(mamh):
                raise MonhocServiceError(f"Không tìm thấy môn học '{mamh}'. Hãy tải lại danh sách.")
            if self._monhocs.exists_tenmh(tenmh, exclude_mamh=mamh):
                raise MonhocServiceError(f"Tên môn học '{tenmh}' đã tồn tại.")
            self._monhocs.update(mamh, tenmh, sotclt, sotcth)

        self._execute(_op)

    def delete(self, mamh: str) -> None:
        require_admin()
        mamh = self._validate_mamh(mamh)

        def _op() -> None:
            if not self._monhocs.exists(mamh):
                raise MonhocServiceError(f"Không tìm thấy môn học '{mamh}'. Hãy tải lại danh sách.")
            if self._monhocs.has_grades(mamh):
                raise MonhocServiceError(
                    f"Không thể xóa môn học '{mamh}' vì đã có dữ liệu điểm sinh viên."
                )
            if self._monhocs.has_assignments(mamh):
                raise MonhocServiceError(
                    f"Không thể xóa môn học '{mamh}' vì đã có phân công giảng dạy."
                )
            self._monhocs.delete(mamh)

        self._execute(_op)

    @staticmethod
    def _utf16_length(value: str) -> int:
        try:
            return len(value.encode("utf-16-le")) // 2
        except UnicodeEncodeError:
            raise MonhocServiceError("Dữ liệu chứa ký tự Unicode không hợp lệ.") from None

    @classmethod
    def _validate_mamh(cls, mamh: str) -> str:
        if not isinstance(mamh, str):
            raise MonhocServiceError("Mã môn học không hợp lệ.")
        normalized = mamh.strip().upper()
        if not normalized:
            raise MonhocServiceError("Mã môn học không được để trống.")
        if " " in normalized:
            raise MonhocServiceError("Mã môn học không được chứa khoảng trắng.")
        if cls._utf16_length(normalized) > 5:
            raise MonhocServiceError("Mã môn học tối đa 5 ký tự.")
        return normalized

    @classmethod
    def _validate_tenmh(cls, tenmh: str) -> str:
        if not isinstance(tenmh, str):
            raise MonhocServiceError("Tên môn học không hợp lệ.")
        normalized = tenmh.strip()
        if not normalized:
            raise MonhocServiceError("Tên môn học không được để trống.")
        if cls._utf16_length(normalized) > 40:
            raise MonhocServiceError("Tên môn học tối đa 40 ký tự.")
        return normalized

    @staticmethod
    def _validate_credits(sotclt: int, sotcth: int) -> tuple[int, int]:
        if isinstance(sotclt, bool) or not isinstance(sotclt, int) or sotclt < 0:
            raise MonhocServiceError("Số tín chỉ lý thuyết phải là số nguyên >= 0.")
        if isinstance(sotcth, bool) or not isinstance(sotcth, int) or sotcth < 0:
            raise MonhocServiceError("Số tín chỉ thực hành phải là số nguyên >= 0.")
        return sotclt, sotcth

    @staticmethod
    def _execute(operation, *args):
        try:
            return operation(*args)
        except MonhocServiceError:
            raise
        except session.SessionRequiredError:
            raise MonhocServiceError("Phiên SQL không còn hiệu lực. Vui lòng đăng nhập lại.") from None
        except pyodbc.Error as error:
            msg = " ".join(map(str, error.args))
            if "FK_" in msg or "REFERENCE" in msg.upper():
                raise MonhocServiceError("Không thể xóa môn học vì còn dữ liệu liên quan (Điểm hoặc Phân công).") from None
            if "UQ_" in msg or "UNIQUE" in msg.upper() or "PRIMARY KEY" in msg.upper() or "2627" in msg:
                raise MonhocServiceError("Mã môn học hoặc Tên môn học đã tồn tại.") from None
            raise MonhocServiceError(f"Lỗi truy cập dữ liệu môn học: {msg}") from None

