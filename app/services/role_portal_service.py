"""Role-enforced service for Admin PhanCong and Lecturer/Student portals."""

import re

import pyodbc

from app.repositories.role_portal_repository import RolePortalRepository
from app.services.authorization import require_admin, require_lecturer_magv, require_student_masv
from app.utils import session


class RolePortalServiceError(Exception):
    """Safe error message for UI."""


class RolePortalService:
    SQL_ERRORS = {
        55001: "Chỉ Admin mới có quyền quản lý phân công.",
        55002: "Vui lòng chọn đầy đủ Giảng viên, Lớp và Môn học.",
        55003: "Giảng viên không tồn tại.",
        55004: "Lớp không tồn tại.",
        55005: "Môn học không tồn tại.",
        55006: "Phân công này đã tồn tại.",
        55010: "Chỉ Giảng viên hoặc Admin mới có quyền truy cập.",
        55011: "Bạn không được phân công giảng dạy lớp này.",
        55020: "Chỉ Sinh viên mới có quyền truy cập hồ sơ sinh viên.",
    }

    def __init__(self, repository: RolePortalRepository | None = None) -> None:
        self._repo = repository or RolePortalRepository()

    # --- Admin: PhanCong ---
    def find_all_phancong(self) -> list[dict]:
        require_admin()
        rows = self._execute(self._repo.find_all_phancong)
        return [
            {
                "magv": str(r[0]).strip(),
                "hoten_gv": str(r[1]).strip(),
                "malop": str(r[2]).strip(),
                "tenlop": str(r[3]).strip(),
                "mamh": str(r[4]).strip(),
                "tenmh": str(r[5]).strip(),
            }
            for r in rows
        ]

    def add_phancong(self, magv: str, malop: str, mamh: str) -> None:
        require_admin()
        magv = magv.strip().upper()
        malop = malop.strip().upper()
        mamh = mamh.strip().upper()
        if not magv or not malop or not mamh:
            raise RolePortalServiceError(self.SQL_ERRORS[55002])
        self._execute(self._repo.add_phancong, magv, malop, mamh)

    def delete_phancong(self, magv: str, malop: str, mamh: str) -> None:
        require_admin()
        self._execute(
            self._repo.delete_phancong,
            magv.strip().upper(),
            malop.strip().upper(),
            mamh.strip().upper(),
        )

    # --- Lecturer ---
    def get_lecturer_profile(self) -> dict | None:
        require_lecturer_magv()
        row = self._execute(self._repo.get_lecturer_profile)
        if not row:
            return None
        return {
            "magv": str(row[0]).strip(),
            "ho": row[1].strip() if isinstance(row[1], str) else (row[1] or ""),
            "ten": row[2].strip() if isinstance(row[2], str) else (row[2] or ""),
            "phai": "Nam" if row[3] else "Nữ",
        }

    def get_lecturer_assignments(self) -> list[dict]:
        require_lecturer_magv()
        rows = self._execute(self._repo.get_lecturer_assignments)
        return [
            {
                "malop": str(r[0]).strip(),
                "tenlop": str(r[1]).strip(),
                "mamh": str(r[2]).strip(),
                "tenmh": str(r[3]).strip(),
                "sotclt": int(r[4]),
                "sotcth": int(r[5]),
            }
            for r in rows
        ]

    def get_lecturer_class_students(self, malop: str) -> list[dict]:
        require_lecturer_magv()
        rows = self._execute(self._repo.get_lecturer_class_students, malop.strip().upper())
        return [
            {
                "masv": str(r[0]).strip(),
                "ho": r[1].strip() if isinstance(r[1], str) else (r[1] or ""),
                "ten": r[2].strip() if isinstance(r[2], str) else (r[2] or ""),
                "malop": str(r[3]).strip(),
                "phai": "Nam" if r[4] else "Nữ",
                "ngaysinh": r[5],
                "noisinh": r[6].strip() if isinstance(r[6], str) else (r[6] or ""),
                "diachi": r[7].strip() if isinstance(r[7], str) else (r[7] or ""),
                "ghichu": r[8] or "",
            }
            for r in rows
        ]

    # --- Student ---
    def get_student_profile_and_class(self) -> dict | None:
        require_student_masv()
        row = self._execute(self._repo.get_student_profile_and_class)
        if not row:
            return None
        return {
            "masv": str(row[0]).strip(),
            "ho": row[1].strip() if isinstance(row[1], str) else (row[1] or ""),
            "ten": row[2].strip() if isinstance(row[2], str) else (row[2] or ""),
            "malop": str(row[3]).strip(),
            "tenlop": str(row[4]).strip(),
            "phai": "Nam" if row[5] else "Nữ",
            "ngaysinh": row[6],
            "noisinh": row[7].strip() if isinstance(row[7], str) else (row[7] or ""),
            "diachi": row[8].strip() if isinstance(row[8], str) else (row[8] or ""),
            "ghichu": row[9] or "",
            "nghihoc": bool(row[10]),
        }

    def get_student_subjects(self) -> list[dict]:
        require_student_masv()
        rows = self._execute(self._repo.get_student_subjects)
        return [
            {
                "mamh": str(r[0]).strip(),
                "tenmh": str(r[1]).strip(),
                "sotclt": int(r[2]),
                "sotcth": int(r[3]),
            }
            for r in rows
        ]

    def get_student_own_grades(self) -> list[dict]:
        require_student_masv()
        rows = self._execute(self._repo.get_student_own_grades)
        return [
            {
                "mamh": str(r[0]).strip(),
                "tenmh": str(r[1]).strip(),
                "lan": int(r[2]),
                "diem": float(r[3]) if r[3] is not None else None,
            }
            for r in rows
        ]

    @classmethod
    def _execute(cls, operation, *args):
        try:
            return operation(*args)
        except RolePortalServiceError:
            raise
        except session.SessionRequiredError:
            raise RolePortalServiceError("Phiên SQL không còn hiệu lực. Vui lòng đăng nhập lại.") from None
        except pyodbc.Error as error:
            msg = " ".join(map(str, error.args))
            numbers = re.findall(r"(?<!\d)550\d{2}(?!\d)", msg)
            mapped = next((cls.SQL_ERRORS[int(n)] for n in numbers if int(n) in cls.SQL_ERRORS), None)
            if mapped:
                raise RolePortalServiceError(mapped) from None
            raise RolePortalServiceError(f"Lỗi truy cập dữ liệu: {msg}") from None

