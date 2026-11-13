"""SQL Server data access for dbo.Lop using the authenticated QLDSV session."""

from app.models.lop import Lop
from app.utils import session


class LopRepository:
    def find_all(self) -> list[Lop]:
        with session.qldsv_cursor() as cursor:
            rows = cursor.execute("EXEC dbo.sp_GetLop;").fetchall()
        return [Lop(malop=str(row[0]).strip(), tenlop=str(row[1]).strip()) for row in rows]

    def exists(self, malop: str) -> bool:
        with session.qldsv_cursor() as cursor:
            row = cursor.execute("EXEC dbo.sp_CheckMaLop @MALOP=?;", malop).fetchone()
        return bool(row and row[0])

    def exists_tenlop(self, tenlop: str, exclude_malop: str | None = None) -> bool:
        with session.qldsv_cursor() as cursor:
            if exclude_malop:
                row = cursor.execute(
                    "SELECT TOP 1 1 FROM dbo.Lop WHERE TENLOP = ? AND MALOP <> ?;",
                    tenlop,
                    exclude_malop,
                ).fetchone()
            else:
                row = cursor.execute(
                    "SELECT TOP 1 1 FROM dbo.Lop WHERE TENLOP = ?;",
                    tenlop,
                ).fetchone()
        return row is not None

    def has_students(self, malop: str) -> bool:
        with session.qldsv_cursor() as cursor:
            row = cursor.execute(
                "SELECT TOP 1 1 FROM dbo.Sinhvien WHERE MALOP = ?;",
                malop,
            ).fetchone()
        return row is not None

    def has_assignments(self, malop: str) -> bool:
        with session.qldsv_cursor() as cursor:
            row = cursor.execute(
                "SELECT TOP 1 1 FROM dbo.PhanCong WHERE MALOP = ?;",
                malop,
            ).fetchone()
        return row is not None

    def create(self, malop: str, tenlop: str) -> None:
        with session.qldsv_cursor() as cursor:
            cursor.execute(
                "INSERT INTO dbo.Lop (MALOP, TENLOP) VALUES (?, ?);",
                malop,
                tenlop,
            )

    def update(self, malop: str, tenlop: str) -> None:
        with session.qldsv_cursor() as cursor:
            cursor.execute(
                "UPDATE dbo.Lop SET TENLOP = ? WHERE MALOP = ?;",
                tenlop,
                malop,
            )

    def delete(self, malop: str) -> None:
        with session.qldsv_cursor() as cursor:
            cursor.execute(
                "DELETE FROM dbo.Lop WHERE MALOP = ?;",
                malop,
            )

