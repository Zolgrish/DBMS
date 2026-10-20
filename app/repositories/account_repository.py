"""Database access for dbo.TaiKhoan."""

from app.utils import session
from app.models.user import User


class AccountRepository:
    def find_all_accounts(self) -> list[User]:
        with session.qldsv_cursor() as cursor:
            rows = cursor.execute(
                """
                SELECT
                    tk.TENDANGNHAP,
                    tk.VAITRO,
                    tk.MASV,
                    tk.MAGV,
                    tk.TRANGTHAI,
                    sv.HO,
                    sv.TEN,
                    gv.HO,
                    gv.TEN
                FROM dbo.TaiKhoan AS tk
                LEFT JOIN dbo.Sinhvien AS sv ON sv.MASV = tk.MASV
                LEFT JOIN dbo.Giangvien AS gv ON gv.MAGV = tk.MAGV
                ORDER BY tk.TENDANGNHAP
                """
            ).fetchall()

        accounts: list[User] = []
        for row in rows:
            role = str(row[1]).strip()
            if role == "SinhVien":
                full_name = self._join_name(row[5], row[6])
            elif role == "GiangVien":
                full_name = self._join_name(row[7], row[8])
            else:
                full_name = "Quản trị viên"

            accounts.append(
                User(
                    username=str(row[0]).strip(),
                    role=role,
                    masv=str(row[2]).strip() if row[2] is not None else None,
                    magv=str(row[3]).strip() if row[3] is not None else None,
                    active=bool(row[4]),
                    full_name=full_name,
                )
            )
        return accounts

    @staticmethod
    def _join_name(last_name, first_name) -> str:
        return " ".join(
            str(part).strip()
            for part in (last_name, first_name)
            if part is not None and str(part).strip()
        )

    def exists_username(self, username: str) -> bool:
        with session.qldsv_cursor() as cursor:
            row = cursor.execute(
                "SELECT 1 FROM dbo.TaiKhoan WHERE TENDANGNHAP = ?",
                username,
            ).fetchone()
            return row is not None

    def student_exists(self, masv: str) -> bool:
        with session.qldsv_cursor() as cursor:
            row = cursor.execute(
                "SELECT 1 FROM dbo.Sinhvien WHERE MASV = ?",
                masv,
            ).fetchone()
            return row is not None

    def lecturer_exists(self, magv: str) -> bool:
        with session.qldsv_cursor() as cursor:
            row = cursor.execute(
                "SELECT 1 FROM dbo.Giangvien WHERE MAGV = ?",
                magv,
            ).fetchone()
            return row is not None

    def create_account(
        self,
        username: str,
        password: str,
        role: str,
        masv: str | None = None,
        magv: str | None = None,
    ) -> None:
        with session.qldsv_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO dbo.TaiKhoan (TENDANGNHAP, MATKHAU, VAITRO, MASV, MAGV)
                VALUES (?, ?, ?, ?, ?)
                """,
                username,
                password,
                role,
                masv,
                magv,
            )

    def update_account(
        self,
        username: str,
        role: str,
        masv: str | None,
        magv: str | None,
    ) -> bool:
        with session.qldsv_cursor() as cursor:
            cursor = cursor.execute(
                """
                UPDATE dbo.TaiKhoan
                SET VAITRO = ?, MASV = ?, MAGV = ?
                WHERE TENDANGNHAP = ?
                """,
                role,
                masv,
                magv,
                username,
            )
            return cursor.rowcount > 0

    def update_account_status(self, username: str, status: bool) -> bool:
        with session.qldsv_cursor() as cursor:
            cursor = cursor.execute(
                "UPDATE dbo.TaiKhoan SET TRANGTHAI = ? WHERE TENDANGNHAP = ?",
                1 if status else 0,
                username,
            )
            return cursor.rowcount > 0

    def update_password(
        self,
        username: str,
        current_password: str,
        new_password: str,
    ) -> bool:
        """Change the password only when the supplied current password matches."""
        with session.qldsv_cursor() as cursor:
            cursor = cursor.execute(
                """
                UPDATE dbo.TaiKhoan
                SET MATKHAU = ?
                WHERE TENDANGNHAP = ? AND MATKHAU = ?
                """,
                new_password,
                username,
                current_password,
            )
            return cursor.rowcount > 0
