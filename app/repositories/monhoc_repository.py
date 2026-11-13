"""SQL Server data access for dbo.Monhoc using the authenticated QLDSV session."""

from app.models.monhoc import Monhoc
from app.utils import session


class MonhocRepository:
    def find_all(self) -> list[Monhoc]:
        with session.qldsv_cursor() as cursor:
            rows = cursor.execute("EXEC dbo.sp_GetMonHoc;").fetchall()
        return [
            Monhoc(
                mamh=str(row[0]).strip(),
                tenmh=str(row[1]).strip(),
                sotclt=int(row[2]),
                sotcth=int(row[3]),
            )
            for row in rows
        ]

    def exists(self, mamh: str) -> bool:
        with session.qldsv_cursor() as cursor:
            row = cursor.execute("EXEC dbo.sp_CheckMaMH @MAMH=?;", mamh).fetchone()
        return bool(row and row[0])

    def exists_tenmh(self, tenmh: str, exclude_mamh: str | None = None) -> bool:
        with session.qldsv_cursor() as cursor:
            if exclude_mamh:
                row = cursor.execute(
                    "SELECT TOP 1 1 FROM dbo.Monhoc WHERE TENMH = ? AND MAMH <> ?;",
                    tenmh,
                    exclude_mamh,
                ).fetchone()
            else:
                row = cursor.execute(
                    "SELECT TOP 1 1 FROM dbo.Monhoc WHERE TENMH = ?;",
                    tenmh,
                ).fetchone()
        return row is not None

    def has_grades(self, mamh: str) -> bool:
        with session.qldsv_cursor() as cursor:
            row = cursor.execute(
                "SELECT TOP 1 1 FROM dbo.Diem WHERE MAMH = ?;",
                mamh,
            ).fetchone()
        return row is not None

    def has_assignments(self, mamh: str) -> bool:
        with session.qldsv_cursor() as cursor:
            row = cursor.execute(
                "SELECT TOP 1 1 FROM dbo.PhanCong WHERE MAMH = ?;",
                mamh,
            ).fetchone()
        return row is not None

    def create(self, mamh: str, tenmh: str, sotclt: int, sotcth: int) -> None:
        with session.qldsv_cursor() as cursor:
            cursor.execute(
                "INSERT INTO dbo.Monhoc (MAMH, TENMH, SoTCLT, SoTCTH) VALUES (?, ?, ?, ?);",
                mamh,
                tenmh,
                sotclt,
                sotcth,
            )

    def update(self, mamh: str, tenmh: str, sotclt: int, sotcth: int) -> None:
        with session.qldsv_cursor() as cursor:
            cursor.execute(
                "UPDATE dbo.Monhoc SET TENMH = ?, SoTCLT = ?, SoTCTH = ? WHERE MAMH = ?;",
                tenmh,
                sotclt,
                sotcth,
                mamh,
            )

    def delete(self, mamh: str) -> None:
        with session.qldsv_cursor() as cursor:
            cursor.execute(
                "DELETE FROM dbo.Monhoc WHERE MAMH = ?;",
                mamh,
            )

