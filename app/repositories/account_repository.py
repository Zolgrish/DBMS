"""SQL principal account management and self password changes."""

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
                   OR NOT EXISTS (SELECT 1 FROM sys.database_principals AS actor
                                  WHERE actor.name=USER_NAME() AND actor.sid=SUSER_SID()
                                    AND actor.type='S' AND actor.authentication_type=1)
                   OR (SELECT COUNT(*) FROM sys.database_role_members
                       WHERE member_principal_id=DATABASE_PRINCIPAL_ID(USER_NAME())) <> 1
                   OR NOT EXISTS (
                       SELECT 1 FROM sys.database_role_members AS actor_membership
                       JOIN sys.database_principals AS actor_role
                         ON actor_role.principal_id=actor_membership.role_principal_id
                       WHERE actor_membership.member_principal_id=DATABASE_PRINCIPAL_ID(USER_NAME())
                         AND actor_role.name=N'QLDSV_ADMIN' AND actor_role.type='R'
                         AND actor_role.owning_principal_id=DATABASE_PRINCIPAL_ID(N'dbo'))
                    THROW 52001, 'Only an unambiguous, mapped Admin may list accounts.', 1;
                SELECT
                    sp.name,
                    dp.name,
                    r.name,
                    CASE WHEN r.name = N'QLDSV_SINHVIEN' THEN dp.name END,
                    CASE WHEN r.name IN (N'QLDSV_ADMIN', N'QLDSV_GIANGVIEN') THEN dp.name END,
                    sl.is_disabled,
                    sv.HO,
                    sv.TEN,
                    gv.HO,
                    gv.TEN,
                    sp.sid
                FROM sys.server_principals AS sp
                JOIN sys.sql_logins AS sl ON sl.principal_id = sp.principal_id
                JOIN sys.database_principals AS dp ON sp.sid = dp.sid
                JOIN sys.database_role_members AS rm ON rm.member_principal_id = dp.principal_id
                JOIN sys.database_principals AS r ON r.principal_id = rm.role_principal_id
                LEFT JOIN dbo.Sinhvien AS sv ON sv.MASV = dp.name AND r.name = N'QLDSV_SINHVIEN'
                LEFT JOIN dbo.Giangvien AS gv ON gv.MAGV = dp.name AND r.name IN (N'QLDSV_ADMIN', N'QLDSV_GIANGVIEN')
                WHERE sp.type = 'S' AND sp.principal_id <> 1
                  AND dp.type = 'S' AND dp.authentication_type = 1 AND dp.principal_id > 4
                  AND r.name IN (N'QLDSV_ADMIN', N'QLDSV_GIANGVIEN', N'QLDSV_SINHVIEN')
                  AND r.type='R' AND r.owning_principal_id=DATABASE_PRINCIPAL_ID(N'dbo')
                  AND (SELECT COUNT(*) FROM sys.database_role_members AS memberships
                       WHERE memberships.member_principal_id = dp.principal_id) = 1
                ORDER BY sp.name
                """
            ).fetchall()

        accounts: list[User] = []
        for row in rows:
            role = {"QLDSV_ADMIN": "Admin", "QLDSV_GIANGVIEN": "GiangVien", "QLDSV_SINHVIEN": "SinhVien"}[str(row[2]).strip()]
            if role == "SinhVien":
                full_name = self._join_name(row[6], row[7])
            elif row[4] is not None:
                full_name = self._join_name(row[8], row[9])
            else:
                full_name = "Quản trị viên"

            accounts.append(
                User(
                    username=str(row[1]).strip(),
                    role=role,
                    masv=str(row[3]).strip() if row[3] is not None else None,
                    magv=str(row[4]).strip() if row[4] is not None else None,
                    active=not bool(row[5]),
                    full_name=full_name,
                    login_name=str(row[0]).strip(),
                    principal_sid=bytes(row[10]) if row[10] is not None else None,
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
        login_name: str,
        password: str | None,
        role: str,
        database_user: str | None = None,
    ) -> bytes:
        with session.qldsv_cursor() as cursor:
            row = cursor.execute(
                """
                SET NOCOUNT ON;
                DECLARE @CreatedSid varbinary(85);
                EXEC dbo.sp_TaoTaiKhoan @LoginName=?, @DatabaseUser=?, @Role=?, @Password=?,
                    @CreatedSid=@CreatedSid OUTPUT;
                SELECT @CreatedSid;
                """,
                login_name,
                database_user or login_name,
                role,
                None if role == "QLDSV_SINHVIEN" else password,
            ).fetchone()
            return row[0]

    def delete_account(self, login_name: str, expected_sid: bytes | None = None) -> None:
        with session.qldsv_cursor() as cursor:
            cursor.execute("EXEC dbo.sp_XoaTaiKhoan @LoginName=?, @ExpectedSid=?;", login_name, expected_sid)

    def set_account_disabled(
        self,
        login_name: str,
        disabled: bool,
        expected_sid: bytes | None = None,
    ) -> None:
        with session.qldsv_cursor() as cursor:
            cursor.execute(
                "EXEC dbo.sp_KhoaMoTaiKhoan @LoginName=?, @Disable=?, @ExpectedSid=?;",
                login_name,
                bool(disabled),
                expected_sid,
            )

    def update_password(
        self,
        current_password: str,
        new_password: str,
    ) -> None:
        """SQL derives the target Login from the borrowed authenticated session."""
        try:
            with session.qldsv_cursor() as cursor:
                cursor.execute(
                    "EXEC dbo.sp_DoiMatKhau @OldPassword=?, @NewPassword=?;",
                    current_password,
                    new_password,
                )
        finally:
            current_password = new_password = ""
