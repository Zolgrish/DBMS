"""Stored-procedure access using only the authenticated QLDSV session."""

from app.models.lecturer import Lecturer
from app.utils import session


class LecturerRepository:
    def find_all(self) -> list[Lecturer]:
        with session.qldsv_cursor() as cursor:
            rows = cursor.execute("EXEC dbo.sp_GetGiangVien;").fetchall()
        return [Lecturer(str(row[0]).strip(), row[1], row[2], bool(row[3])) for row in rows]

    def create(self, magv: str, ho: str | None, ten: str | None, phai: bool) -> None:
        with session.qldsv_cursor() as cursor:
            cursor.execute("EXEC dbo.sp_ThemGiangVien @MAGV=?, @HO=?, @TEN=?, @PHAI=?;", magv, ho, ten, phai)

    def update(self, magv: str, ho: str | None, ten: str | None, phai: bool) -> None:
        with session.qldsv_cursor() as cursor:
            cursor.execute("EXEC dbo.sp_CapNhatGiangVien @MAGV=?, @HO=?, @TEN=?, @PHAI=?;", magv, ho, ten, phai)

    def delete(self, magv: str) -> None:
        with session.qldsv_cursor() as cursor:
            cursor.execute("EXEC dbo.sp_XoaGiangVien @MAGV=?;", magv)
