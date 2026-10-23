"""SQL principal account management; password migration remains Epic 1.7."""

from app.utils import session
from app.models.user import User


class AccountRepository:
    def find_all_accounts(self) -> list[User]:
        with session.qldsv_cursor() as cursor:
            rows = cursor.execute(
                """
                SET NOCOUNT ON;
                IF ISNULL(IS_ROLEMEMBER(N'QLDSV_ADMIN'), -1) <> 1
                   OR ISNULL(IS_ROLEMEMBER(N'QLDSV_GIANGVIEN'), -1) <> 0
                   OR ISNULL(IS_ROLEMEMBER(N'QLDSV_SINHVIEN'), -1) <> 0
                   OR ORIGINAL_LOGIN() <> SUSER_SNAME()
                   OR USER_NAME() <> SUSER_SNAME()
                    THROW 52001, 'Only an unambiguous, mapped Admin may list accounts.', 1;
                SELECT
                    sp.name,
                    r.name,
                    CASE WHEN r.name = N'QLDSV_SINHVIEN' THEN dp.name END,
                    CASE WHEN r.name IN (N'QLDSV_ADMIN', N'QLDSV_GIANGVIEN') THEN dp.name END,
                    sl.is_disabled,
                    sv.HO,
                    sv.TEN,
                    gv.HO,
                    gv.TEN
                FROM sys.server_principals AS sp
                JOIN sys.sql_logins AS sl ON sl.principal_id = sp.principal_id
                JOIN sys.database_principals AS dp ON sp.sid = dp.sid AND sp.name = dp.name
                JOIN sys.database_role_members AS rm ON rm.member_principal_id = dp.principal_id
                JOIN sys.database_principals AS r ON r.principal_id = rm.role_principal_id
                LEFT JOIN dbo.Sinhvien AS sv ON sv.MASV = dp.name AND r.name = N'QLDSV_SINHVIEN'
                LEFT JOIN dbo.Giangvien AS gv ON gv.MAGV = dp.name AND r.name IN (N'QLDSV_ADMIN', N'QLDSV_GIANGVIEN')
                WHERE sp.type = 'S' AND sp.principal_id <> 1
                  AND dp.type = 'S' AND dp.authentication_type = 1 AND dp.principal_id > 4
                  AND r.name IN (N'QLDSV_ADMIN', N'QLDSV_GIANGVIEN', N'QLDSV_SINHVIEN')
                  AND (SELECT COUNT(*) FROM sys.database_role_members AS memberships
                       JOIN sys.database_principals AS roles ON roles.principal_id = memberships.role_principal_id
                       WHERE memberships.member_principal_id = dp.principal_id
                         AND roles.name IN (N'QLDSV_ADMIN', N'QLDSV_GIANGVIEN', N'QLDSV_SINHVIEN')) = 1
                ORDER BY sp.name
                """
            ).fetchall()

        accounts: list[User] = []
        for row in rows:
            role = {"QLDSV_ADMIN": "Admin", "QLDSV_GIANGVIEN": "GiangVien", "QLDSV_SINHVIEN": "SinhVien"}[str(row[1]).strip()]
            if role == "SinhVien":
                full_name = self._join_name(row[5], row[6])
            elif row[3] is not None:
                full_name = self._join_name(row[7], row[8])
            else:
                full_name = "Quản trị viên"

            accounts.append(
                User(
                    username=str(row[0]).strip(),
                    role=role,
                    masv=str(row[2]).strip() if row[2] is not None else None,
                    magv=str(row[3]).strip() if row[3] is not None else None,
                    active=not bool(row[4]),
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
        password: str | None,
        role: str,
    ) -> bytes:
        with session.qldsv_cursor() as cursor:
            row = cursor.execute(
                """
                SET NOCOUNT ON;
                DECLARE @CreatedSid varbinary(85);
                EXEC dbo.sp_TaoTaiKhoan @LoginName=?, @Role=?, @Password=?,
                    @CreatedSid=@CreatedSid OUTPUT;
                SELECT @CreatedSid;
                """,
                username,
                role,
                None if role == "QLDSV_SINHVIEN" else password,
            ).fetchone()
            return row[0]

    def delete_account(self, username: str, expected_sid: bytes | None = None) -> None:
        with session.qldsv_cursor() as cursor:
            cursor.execute("EXEC dbo.sp_XoaTaiKhoan @LoginName=?, @ExpectedSid=?;", username, expected_sid)

    def update_password(
        self,
        username: str,
        current_password: str,
        new_password: str,
    ) -> bool:
        """Isolated legacy Change Password path, pending Epic 1.7 migration."""
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
