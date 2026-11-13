"""SQL Server data access for dbo.Sinhvien using the authenticated QLDSV session."""

from datetime import date

from app.models.sinhvien import Sinhvien
from app.utils import session


class SinhvienRepository:
    def find_by_lop(self, malop: str) -> list[Sinhvien]:
        with session.qldsv_cursor() as cursor:
            rows = cursor.execute("EXEC dbo.sp_GetSinhVienByLop @MALOP=?;", malop).fetchall()
        return [self._map_row(row) for row in rows]

    def find_by_ma(self, masv: str) -> Sinhvien | None:
        with session.qldsv_cursor() as cursor:
            row = cursor.execute("EXEC dbo.sp_GetSinhVienByMa @MASV=?;", masv).fetchone()
        return self._map_row(row) if row else None

    def exists(self, masv: str) -> bool:
        with session.qldsv_cursor() as cursor:
            row = cursor.execute("EXEC dbo.sp_CheckMaSV @MASV=?;", masv).fetchone()
        return bool(row and row[0])

    def has_grades(self, masv: str) -> bool:
        with session.qldsv_cursor() as cursor:
            row = cursor.execute("SELECT TOP 1 1 FROM dbo.Diem WHERE MASV = ?;", masv).fetchone()
        return row is not None

    def create(
        self,
        masv: str,
        ho: str | None,
        ten: str | None,
        malop: str,
        phai: bool,
        ngaysinh: date | None,
        noisinh: str | None,
        diachi: str | None,
        ghichu: str | None,
        nghihoc: bool,
        hinh: str | None,
    ) -> None:
        with session.qldsv_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO dbo.Sinhvien
                    (MASV, HO, TEN, MALOP, PHAI, NGAYSINH, NOISINH, DIACHI, GHICHU, NGHIHOC, HINH)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                masv,
                ho,
                ten,
                malop,
                1 if phai else 0,
                ngaysinh,
                noisinh,
                diachi,
                ghichu,
                1 if nghihoc else 0,
                hinh,
            )

    def update(
        self,
        masv: str,
        ho: str | None,
        ten: str | None,
        malop: str,
        phai: bool,
        ngaysinh: date | None,
        noisinh: str | None,
        diachi: str | None,
        ghichu: str | None,
        nghihoc: bool,
        hinh: str | None,
    ) -> None:
        with session.qldsv_cursor() as cursor:
            cursor.execute(
                """
                UPDATE dbo.Sinhvien
                SET HO = ?, TEN = ?, MALOP = ?, PHAI = ?, NGAYSINH = ?,
                    NOISINH = ?, DIACHI = ?, GHICHU = ?, NGHIHOC = ?, HINH = ?
                WHERE MASV = ?;
                """,
                ho,
                ten,
                malop,
                1 if phai else 0,
                ngaysinh,
                noisinh,
                diachi,
                ghichu,
                1 if nghihoc else 0,
                hinh,
                masv,
            )

    def delete(self, masv: str) -> None:
        with session.qldsv_cursor() as cursor:
            cursor.execute("DELETE FROM dbo.Sinhvien WHERE MASV = ?;", masv)

    @staticmethod
    def _map_row(row) -> Sinhvien:
        return Sinhvien(
            masv=str(row[0]).strip(),
            ho=row[1].strip() if isinstance(row[1], str) else row[1],
            ten=row[2].strip() if isinstance(row[2], str) else row[2],
            malop=str(row[3]).strip(),
            phai=bool(row[4]),
            ngaysinh=row[5],
            noisinh=row[6].strip() if isinstance(row[6], str) else row[6],
            diachi=row[7].strip() if isinstance(row[7], str) else row[7],
            ghichu=row[8],
            nghihoc=bool(row[9]),
            hinh=row[10].strip() if isinstance(row[10], str) else row[10],
        )

