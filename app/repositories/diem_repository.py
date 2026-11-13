"""SQL Server data access for Grading (Diem) using Stored Procedures."""

from app.models.diem import DiemSinhvienRow
from app.models.lop import Lop
from app.models.monhoc import Monhoc
from app.utils import session


class DiemRepository:
    def get_lops_for_grading(self) -> list[Lop]:
        with session.qldsv_cursor() as cursor:
            rows = cursor.execute("EXEC dbo.sp_Diem_GetLopChoNhapDiem;").fetchall()
        return [Lop(malop=str(row[0]).strip(), tenlop=str(row[1]).strip()) for row in rows]

    def get_monhocs_for_grading(self, malop: str) -> list[Monhoc]:
        with session.qldsv_cursor() as cursor:
            rows = cursor.execute(
                "EXEC dbo.sp_Diem_GetMonHocChoNhapDiem @MALOP=?;",
                malop,
            ).fetchall()
        return [
            Monhoc(
                mamh=str(row[0]).strip(),
                tenmh=str(row[1]).strip(),
                sotclt=int(row[2]),
                sotcth=int(row[3]),
            )
            for row in rows
        ]

    def get_grading_list(self, malop: str, mamh: str, lan: int) -> list[DiemSinhvienRow]:
        with session.qldsv_cursor() as cursor:
            rows = cursor.execute(
                "EXEC dbo.sp_Diem_LayDanhSachNhapDiem @MALOP=?, @MAMH=?, @LAN=?;",
                malop,
                mamh,
                lan,
            ).fetchall()
        return [
            DiemSinhvienRow(
                masv=str(row[0]).strip(),
                ho=row[1].strip() if isinstance(row[1], str) else row[1],
                ten=row[2].strip() if isinstance(row[2], str) else row[2],
                diem=float(row[3]) if row[3] is not None else None,
            )
            for row in rows
        ]

    def save_grades(self, mamh: str, lan: int, items: list[tuple[str, float | None]]) -> None:
        with session.qldsv_cursor() as cursor:
            for masv, diem in items:
                cursor.execute(
                    "EXEC dbo.sp_Diem_LuuDiem @MASV=?, @MAMH=?, @LAN=?, @DIEM=?;",
                    masv,
                    mamh,
                    lan,
                    diem,
                )

    def delete_grade(self, masv: str, mamh: str, lan: int) -> None:
        with session.qldsv_cursor() as cursor:
            cursor.execute(
                "EXEC dbo.sp_Diem_XoaDiem @MASV=?, @MAMH=?, @LAN=?;",
                masv,
                mamh,
                lan,
            )

