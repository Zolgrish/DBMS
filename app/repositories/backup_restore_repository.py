"""SQL Server backup/restore using the authenticated Admin's master session."""

from pathlib import Path

from app.utils import session


class InvalidBackupError(Exception):
    """The selected file is not a full QLDSV database backup."""


class RestoreCleanupError(Exception):
    """The database could not be returned to MULTI_USER after a restore attempt."""


class BackupRestoreRepository:
    DATABASE_NAME = "QLDSV"
    _MULTI_USER = "ALTER DATABASE [QLDSV] SET MULTI_USER"

    def create_backup(self, path: Path) -> None:
        with session.master_cursor() as cursor:
            cursor.execute(
                """
                DECLARE @backup_path NVARCHAR(4000) = ?;
                BACKUP DATABASE [QLDSV]
                TO DISK = @backup_path
                WITH INIT, CHECKSUM;
                """,
                str(path),
            )
            self._finish_statement(cursor)

    def verify_backup(self, path: Path) -> None:
        """Reject another database's backup and validate the selected backup set."""
        with session.master_cursor() as cursor:
            cursor.execute(
                """
                DECLARE @backup_path NVARCHAR(4000) = ?;
                RESTORE HEADERONLY FROM DISK = @backup_path;
                """,
                str(path),
            )
            while cursor.description is None:
                if not cursor.nextset():
                    raise InvalidBackupError("Không đọc được thông tin bản sao lưu.")
            columns = [column[0] for column in cursor.description]
            row = cursor.fetchone()
            if row is None:
                raise InvalidBackupError("File không chứa bản sao lưu cơ sở dữ liệu.")
            header = dict(zip(columns, row))
            if header.get("DatabaseName") != self.DATABASE_NAME or header.get("BackupType") != 1:
                raise InvalidBackupError("File không phải bản sao lưu đầy đủ của QLDSV.")

        with session.master_cursor() as cursor:
            cursor.execute(
                """
                DECLARE @backup_path NVARCHAR(4000) = ?;
                RESTORE VERIFYONLY FROM DISK = @backup_path;
                """,
                str(path),
            )
            self._finish_statement(cursor)

    def restore_backup(self, path: Path) -> None:
        """Release QLDSV first; use the existing master connection through cleanup."""
        connection = session.require_master_connection()
        session.invalidate_qldsv_connection()
        operation_error = cleanup_error = None
        try:
            try:
                self._execute(connection, "ALTER DATABASE [QLDSV] SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
                self._execute(
                    connection,
                    """
                    DECLARE @backup_path NVARCHAR(4000) = ?;
                    RESTORE DATABASE [QLDSV]
                    FROM DISK = @backup_path
                    WITH REPLACE, RECOVERY;
                    """,
                    str(path),
                )
            except Exception as error:
                operation_error = error
            finally:
                try:
                    self._execute(connection, self._MULTI_USER)
                except Exception as error:
                    # No password is retained to open another recovery connection.
                    cleanup_error = error
        finally:
            session.invalidate_session()

        if cleanup_error is not None:
            raise RestoreCleanupError("Không thể đưa QLDSV về chế độ MULTI_USER.") from cleanup_error
        if operation_error is not None:
            raise operation_error

    @classmethod
    def _execute(cls, connection, sql: str, *parameters) -> None:
        # Restore keeps master alive even on connection errors until MULTI_USER
        # has been attempted. The session closes it in the outer finally.
        cursor = connection.cursor()
        try:
            cursor.execute(sql, *parameters)
            cls._finish_statement(cursor)
        finally:
            try:
                cursor.close()
            except Exception:
                pass

    @staticmethod
    def _finish_statement(cursor) -> None:
        """Wait for every result set so ODBC finishes the SQL batch."""
        while True:
            if cursor.description is not None:
                cursor.fetchall()
            if not cursor.nextset():
                break
