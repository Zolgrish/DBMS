"""Grade (Diem) entry item for grading grid."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DiemSinhvienRow:
    masv: str
    ho: str | None
    ten: str | None
    diem: float | None

    @property
    def ho_ten(self) -> str:
        return " ".join(part for part in (self.ho or "", self.ten or "") if part).strip()

