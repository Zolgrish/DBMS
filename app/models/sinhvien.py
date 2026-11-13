"""Student (Sinhvien) business entity."""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class Sinhvien:
    masv: str
    ho: str | None
    ten: str | None
    malop: str
    phai: bool
    ngaysinh: date | datetime | None
    noisinh: str | None
    diachi: str | None
    ghichu: str | None
    nghihoc: bool
    hinh: str | None

    @property
    def ho_ten(self) -> str:
        return " ".join(part for part in (self.ho or "", self.ten or "") if part).strip()

