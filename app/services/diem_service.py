"""Business logic and validation for Grading (Diem) - Lan 1 & Lan 2."""

import re

import pyodbc

from app.models.diem import DiemSinhvienRow
from app.models.lop import Lop
from app.models.monhoc import Monhoc
from app.repositories.diem_repository import DiemRepository
from app.services.authorization import require_admin
from app.utils import session


class DiemServiceError(Exception):
    """Validation or persistence error safe to display in the UI."""


class DiemService:
    SQL_ERRORS = {
        54001: "Chỉ Admin hoặc Giảng viên mới có quyền truy cập chức năng nhập điểm.",
        54002: "Tham số Lớp, Môn học hoặc Lần thi không hợp lệ.",
        54003: "Chưa nhập điểm lần thi 1 cho lớp và môn học này. Không thể nhập điểm lần 2.",
        54004: "Bạn không được phân công giảng dạy lớp và môn học này.",
        54005: "Điểm phải nằm trong khoảng từ 0 đến 10.",
        54006: "Không tìm thấy sinh viên.",
        54007: "Sinh viên đã nghỉ học; không thể nhập điểm.",
        54008: "Chỉ Admin mới có quyền xóa điểm.",
    }

    def __init__(self, diem_repository: DiemRepository | None = None) -> None:
        self._diems = diem_repository or DiemRepository()

    @staticmethod
    def _require_admin_or_lecturer() -> None:
        current = session.current_user
        if current is None or current.get("role") not in ("Admin", "GiangVien"):
            raise PermissionError("Chỉ Admin hoặc Giảng viên mới được phép nhập điểm.")

    def get_lops_for_grading(self) -> list[Lop]:
        self._require_admin_or_lecturer()
        return self._execute(self._diems.get_lops_for_grading)

    def get_monhocs_for_grading(self, malop: str) -> list[Monhoc]:
        self._require_admin_or_lecturer()
        return self._execute(self._diems.get_monhocs_for_grading, malop.strip().upper())

    def get_grading_list(self, malop: str, mamh: str, lan: int) -> list[DiemSinhvienRow]:
        self._require_admin_or_lecturer()
        malop = malop.strip().upper()
        mamh = mamh.strip().upper()
        if not malop or not mamh:
            raise DiemServiceError("Vui lòng chọn đầy đủ Lớp và Môn học.")
        if lan not in (1, 2):
            raise DiemServiceError("Lần thi chỉ được chọn 1 hoặc 2.")
        return self._execute(self._diems.get_grading_list, malop, mamh, lan)

    def save_grades(self, mamh: str, lan: int, items: list[tuple[str, str]]) -> None:
        """Validate all rows first, then persist in batch."""
        self._require_admin_or_lecturer()
        mamh = mamh.strip().upper()
        if not mamh or lan not in (1, 2):
            raise DiemServiceError("Môn học hoặc Lần thi không hợp lệ.")

        parsed: list[tuple[str, float | None]] = []
        for masv, raw_diem in items:
            diem_val = self.parse_grade(raw_diem, masv)
            parsed.append((masv.strip().upper(), diem_val))

        if not parsed:
            raise DiemServiceError("Không có sinh viên nào để lưu điểm.")

        self._execute(self._diems.save_grades, mamh, lan, parsed)

    def delete_grade(self, masv: str, mamh: str, lan: int) -> None:
        """Admin-only grade deletion; lecturers and students are blocked."""
        require_admin()
        masv = masv.strip().upper()
        mamh = mamh.strip().upper()
        if not masv or not mamh or lan not in (1, 2):
            raise DiemServiceError("Thông tin sinh viên, môn học hoặc lần thi không hợp lệ.")
        self._execute(self._diems.delete_grade, masv, mamh, lan)

    @staticmethod
    def parse_grade(raw: str, masv: str = "") -> float | None:
        text = raw.strip() if isinstance(raw, str) else ("" if raw is None else str(raw).strip())
        if text == "":
            # Empty cell = vắng thi (NULL)
            return None
        # Support comma decimal separator as well
        normalized = text.replace(",", ".")
        try:
            value = float(normalized)
        except ValueError:
            prefix = f"Sinh viên {masv}: " if masv else ""
            raise DiemServiceError(f"{prefix}Điểm '{text}' không phải là số hợp lệ.") from None
        if value < 0 or value > 10:
            prefix = f"Sinh viên {masv}: " if masv else ""
            raise DiemServiceError(f"{prefix}Điểm phải nằm trong khoảng từ 0 đến 10.")
        return round(value, 2)

    @classmethod
    def _execute(cls, operation, *args):
        try:
            return operation(*args)
        except DiemServiceError:
            raise
        except session.SessionRequiredError:
            raise DiemServiceError("Phiên SQL không còn hiệu lực. Vui lòng đăng nhập lại.") from None
        except pyodbc.Error as error:
            msg = " ".join(map(str, error.args))
            numbers = re.findall(r"(?<!\d)540\d{2}(?!\d)", msg)
            mapped = next((cls.SQL_ERRORS[int(n)] for n in numbers if int(n) in cls.SQL_ERRORS), None)
            if mapped:
                raise DiemServiceError(mapped) from None
            raise DiemServiceError(f"Lỗi truy cập dữ liệu điểm: {msg}") from None

