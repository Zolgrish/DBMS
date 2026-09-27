"""Database access for dbo.TaiKhoan."""

from app.config.database import get_connection
from app.models.user import User


class AccountRepository:
    def find_by_credentials(self, username: str, password: str) -> User | None:
        """Return a matching account, or None when credentials do not match."""
        connection = get_connection()
        try:
            row = connection.cursor().execute(
                """
                SELECT TENDANGNHAP, VAITRO, MASV, MAGV, TRANGTHAI
                FROM dbo.TaiKhoan
                WHERE TENDANGNHAP = ? AND MATKHAU = ?
                """,
                username,
                password,
            ).fetchone()
        finally:
            connection.close()

        if row is None:
            return None

        return User(
            username=str(row[0]).strip(),
            role=str(row[1]).strip(),
            masv=str(row[2]).strip() if row[2] is not None else None,
            magv=str(row[3]).strip() if row[3] is not None else None,
            active=bool(row[4]),
        )

    def find_all_accounts(self) -> list[User]:
        connection = get_connection()
        try:
            rows = connection.cursor().execute(
                """
                SELECT TENDANGNHAP, VAITRO, MASV, MAGV, TRANGTHAI
                FROM dbo.TaiKhoan
                ORDER BY TENDANGNHAP
                """
            ).fetchall()
        finally:
            connection.close()

        return [
            User(
                username=str(row[0]).strip(),
                role=str(row[1]).strip(),
                masv=str(row[2]).strip() if row[2] is not None else None,
                magv=str(row[3]).strip() if row[3] is not None else None,
                active=bool(row[4]),
            )
            for row in rows
        ]

    def exists_username(self, username: str) -> bool:
        connection = get_connection()
        try:
            row = connection.cursor().execute(
                "SELECT 1 FROM dbo.TaiKhoan WHERE TENDANGNHAP = ?",
                username,
            ).fetchone()
            return row is not None
        finally:
            connection.close()

    def student_exists(self, masv: str) -> bool:
        connection = get_connection()
        try:
            row = connection.cursor().execute(
                "SELECT 1 FROM dbo.Sinhvien WHERE MASV = ?",
                masv,
            ).fetchone()
            return row is not None
        finally:
            connection.close()

    def lecturer_exists(self, magv: str) -> bool:
        connection = get_connection()
        try:
            row = connection.cursor().execute(
                "SELECT 1 FROM dbo.Giangvien WHERE MAGV = ?",
                magv,
            ).fetchone()
            return row is not None
        finally:
            connection.close()

    def create_account(
        self,
        username: str,
        password: str,
        role: str,
        masv: str | None = None,
        magv: str | None = None,
    ) -> None:
        connection = get_connection()
        try:
            connection.cursor().execute(
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
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def update_account(
        self,
        username: str,
        role: str,
        masv: str | None,
        magv: str | None,
    ) -> bool:
        connection = get_connection()
        try:
            cursor = connection.cursor().execute(
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
            connection.commit()
            return cursor.rowcount > 0
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def update_account_status(self, username: str, status: bool) -> bool:
        connection = get_connection()
        try:
            cursor = connection.cursor().execute(
                "UPDATE dbo.TaiKhoan SET TRANGTHAI = ? WHERE TENDANGNHAP = ?",
                1 if status else 0,
                username,
            )
            connection.commit()
            return cursor.rowcount > 0
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def update_password(
        self,
        username: str,
        current_password: str,
        new_password: str,
    ) -> bool:
        """Change the password only when the supplied current password matches."""
        connection = get_connection()
        try:
            cursor = connection.cursor().execute(
                """
                UPDATE dbo.TaiKhoan
                SET MATKHAU = ?
                WHERE TENDANGNHAP = ? AND MATKHAU = ?
                """,
                new_password,
                username,
                current_password,
            )
            connection.commit()
            return cursor.rowcount > 0
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
