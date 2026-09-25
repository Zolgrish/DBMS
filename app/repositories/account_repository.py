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
