"""Business logic and validation for Student (Sinhvien) management."""

from datetime import date, datetime

import pyodbc

from app.models.sinhvien import Sinhvien
from app.repositories.lop_repository import LopRepository
from app.repositories.sinhvien_repository import SinhvienRepository
from app.services.account_service import AccountService, AccountServiceError
from app.services.authorization import require_admin
from app.utils import session


class SinhvienServiceError(Exception):
    """Validation or persistence error safe to display in the UI."""


class SinhvienService:
    def __init__(
        self,
        sinhvien_repository: SinhvienRepository | None = None,
        lop_repository: LopRepository | None = None,
        account_service: AccountService | None = None,
    ) -> None:
        self._sinhviens = sinhvien_repository or SinhvienRepository()
        self._lops = lop_repository or LopRepository()
        self._account_service = account_service or AccountService()

    def find_by_lop(self, malop: str, keyword: str = "") -> list[Sinhvien]:
        require_admin()
        students = self._execute(self._sinhviens.find_by_lop, malop.strip().upper())
        q = keyword.strip().lower()
        if not q:
            return students
        return [
            sv
            for sv in students
            if q in sv.masv.lower() or q in sv.ho_ten.lower()
        ]

    def create(
        self,
        masv: str,
        ho: str | None,
        ten: str | None,
        malop: str,
        phai: bool = True,
        ngaysinh: date | None = None,
        noisinh: str | None = None,
        diachi: str | None = None,
        ghichu: str | None = None,
        nghihoc: bool = False,
        hinh: str | None = None,
    ) -> str | None:
        """Create a student and auto-create their SQL account (SV-12).

        Returns an optional warning message if auto-account creation failed.
        """
        require_admin()
        masv = self._validate_masv(masv)
        malop = self._validate_malop(malop)
        ho, ten, noisinh, diachi, ghichu, hinh = self._validate_texts(
            ho, ten, noisinh, diachi, ghichu, hinh
        )
        ngaysinh = self._validate_ngaysinh(ngaysinh)

        def _op() -> None:
            if self._sinhviens.exists(masv):
                raise SinhvienServiceError(f"Mã sinh viên '{masv}' đã tồn tại.")
            if not self._lops.exists(malop):
                raise SinhvienServiceError(f"Mã lớp '{malop}' không tồn tại.")
            self._sinhviens.create(
                masv=masv,
                ho=ho,
                ten=ten,
                malop=malop,
                phai=bool(phai),
                ngaysinh=ngaysinh,
                noisinh=noisinh,
                diachi=diachi,
                ghichu=ghichu,
                nghihoc=bool(nghihoc),
                hinh=hinh,
            )

        self._execute(_op)

        # SV-12: Automatically create login account (username=MASV, default password=123456)
        try:
            self._account_service.create_student_account(masv)
            return None
        except (AccountServiceError, PermissionError) as error:
            return f"Đã lưu sinh viên '{masv}', nhưng tạo tài khoản tự động gặp lỗi: {error}"

    def update(
        self,
        masv: str,
        ho: str | None,
        ten: str | None,
        malop: str,
        phai: bool = True,
        ngaysinh: date | None = None,
        noisinh: str | None = None,
        diachi: str | None = None,
        ghichu: str | None = None,
        nghihoc: bool = False,
        hinh: str | None = None,
    ) -> None:
        require_admin()
        masv = self._validate_masv(masv)
        malop = self._validate_malop(malop)
        ho, ten, noisinh, diachi, ghichu, hinh = self._validate_texts(
            ho, ten, noisinh, diachi, ghichu, hinh
        )
        ngaysinh = self._validate_ngaysinh(ngaysinh)

        def _op() -> None:
            if not self._sinhviens.exists(masv):
                raise SinhvienServiceError(f"Không tìm thấy sinh viên '{masv}'. Hãy tải lại danh sách.")
            if not self._lops.exists(malop):
                raise SinhvienServiceError(f"Mã lớp '{malop}' không tồn tại.")
            self._sinhviens.update(
                masv=masv,
                ho=ho,
                ten=ten,
                malop=malop,
                phai=bool(phai),
                ngaysinh=ngaysinh,
                noisinh=noisinh,
                diachi=diachi,
                ghichu=ghichu,
                nghihoc=bool(nghihoc),
                hinh=hinh,
            )

        self._execute(_op)

    def delete(self, masv: str) -> None:
        require_admin()
        masv = self._validate_masv(masv)

        def _op() -> None:
            if not self._sinhviens.exists(masv):
                raise SinhvienServiceError(f"Không tìm thấy sinh viên '{masv}'. Hãy tải lại danh sách.")
            if self._sinhviens.has_grades(masv):
                raise SinhvienServiceError(
                    f"Không thể xóa sinh viên '{masv}' vì đã có dữ liệu điểm."
                )
            self._sinhviens.delete(masv)

        self._execute(_op)

    @staticmethod
    def _utf16_length(value: str) -> int:
        try:
            return len(value.encode("utf-16-le")) // 2
        except UnicodeEncodeError:
            raise SinhvienServiceError("Dữ liệu chứa ký tự Unicode không hợp lệ.") from None

    @classmethod
    def _validate_masv(cls, masv: str) -> str:
        if not isinstance(masv, str):
            raise SinhvienServiceError("Mã sinh viên không hợp lệ.")
        normalized = masv.strip().upper()
        if not normalized:
            raise SinhvienServiceError("Mã sinh viên không được để trống.")
        if " " in normalized:
            raise SinhvienServiceError("Mã sinh viên không được chứa khoảng trắng.")
        if cls._utf16_length(normalized) > 10:
            raise SinhvienServiceError("Mã sinh viên tối đa 10 ký tự.")
        return normalized

    @classmethod
    def _validate_malop(cls, malop: str) -> str:
        if not isinstance(malop, str) or not malop.strip():
            raise SinhvienServiceError("Vui lòng chọn lớp cho sinh viên.")
        return malop.strip().upper()

    @classmethod
    def _validate_texts(cls, ho, ten, noisinh, diachi, ghichu, hinh):
        def _clean(val: str | None, limit: int | None, field: str) -> str | None:
            if val is None:
                return None
            if not isinstance(val, str):
                raise SinhvienServiceError(f"{field} không hợp lệ.")
            s = val.strip()
            if not s:
                return None
            if limit is not None and cls._utf16_length(s) > limit:
                raise SinhvienServiceError(f"{field} tối đa {limit} ký tự.")
            return s

        ho_c = _clean(ho, 40, "Họ")
        ten_c = _clean(ten, 10, "Tên")
        if not ho_c or not ten_c:
            raise SinhvienServiceError("Họ và Tên sinh viên không được để trống.")
        noisinh_c = _clean(noisinh, 40, "Nơi sinh")
        diachi_c = _clean(diachi, 80, "Địa chỉ")
        ghichu_c = _clean(ghichu, None, "Ghi chú")
        hinh_c = _clean(hinh, 1000, "Đường dẫn hình")
        return ho_c, ten_c, noisinh_c, diachi_c, ghichu_c, hinh_c

    @staticmethod
    def _validate_ngaysinh(ngaysinh: date | datetime | None) -> date | None:
        if ngaysinh is None:
            return None
        if isinstance(ngaysinh, datetime):
            ngaysinh = ngaysinh.date()
        if not isinstance(ngaysinh, date):
            raise SinhvienServiceError("Ngày sinh không hợp lệ.")
        if ngaysinh > date.today():
            raise SinhvienServiceError("Ngày sinh không được lớn hơn ngày hiện tại.")
        if ngaysinh.year < 1900:
            raise SinhvienServiceError("Năm sinh phải từ 1900 trở lên.")
        return ngaysinh

    @staticmethod
    def _execute(operation, *args):
        try:
            return operation(*args)
        except SinhvienServiceError:
            raise
        except session.SessionRequiredError:
            raise SinhvienServiceError("Phiên SQL không còn hiệu lực. Vui lòng đăng nhập lại.") from None
        except pyodbc.Error as error:
            msg = " ".join(map(str, error.args))
            if "FK_" in msg or "REFERENCE" in msg.upper():
                raise SinhvienServiceError("Không thể xóa sinh viên vì còn dữ liệu liên quan (Điểm).") from None
            if "PRIMARY KEY" in msg.upper() or "2627" in msg:
                raise SinhvienServiceError("Mã sinh viên đã tồn tại.") from None
            raise SinhvienServiceError(f"Lỗi truy cập dữ liệu sinh viên: {msg}") from None

