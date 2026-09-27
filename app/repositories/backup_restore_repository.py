"""SQL Server backup and restore commands for the fixed QLDSV database."""

from pathlib import Path

from app.config.database import get_connection


class InvalidBackupError(Exception):
    """The selected file is not a full QLDSV database backup."""


class RestoreCleanupError(Exception):
    """The database could not be returned to MULTI_USER after a restore attempt."""


class BackupRestoreRepository:
    DATABASE_NAME = "QLDSV"
    _MASTER = "master"
    _MULTI_USER = "ALTER DATABASE [QLDSV] SET MULTI_USER"

    def create_backup(self, path: Path) -> None:
        connection = get_connection(self._MASTER, autocommit=True)
        try:
            cursor = connection.cursor()
            try:
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
            finally:
                cursor.close()
        finally:
            connection.close()

    def verify_backup(self, path: Path) -> None:
        """Reject another database's backup and validate the selected backup set."""
        connection = get_connection(self._MASTER, autocommit=True)
        try:
            cursor = connection.cursor()
            try:
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
            finally:
                cursor.close()

            verify_cursor = connection.cursor()
            try:
                verify_cursor.execute(
                    """
                    DECLARE @backup_path NVARCHAR(4000) = ?;
                    RESTORE VERIFYONLY FROM DISK = @backup_path;
                    """,
                    str(path),
                )
                self._finish_statement(verify_cursor)
            finally:
                verify_cursor.close()
        finally:
            connection.close()

    def restore_backup(self, path: Path) -> None:
        """Restore from master and attempt MULTI_USER even when any step fails."""
        connection = get_connection(self._MASTER, autocommit=True)
        operation_error: Exception | None = None
        cleanup_error: Exception | None = None
        try:
            try:
                connection.cursor().execute(
                    "ALTER DATABASE [QLDSV] SET SINGLE_USER WITH ROLLBACK IMMEDIATE"
                )
                restore_cursor = connection.cursor()
                try:
                    restore_cursor.execute(
                        """
                        DECLARE @backup_path NVARCHAR(4000) = ?;
                        RESTORE DATABASE [QLDSV]
                        FROM DISK = @backup_path
                        WITH REPLACE, RECOVERY;
                        """,
                        str(path),
                    )
                    self._finish_statement(restore_cursor)
                finally:
                    restore_cursor.close()
            except Exception as error:
                operation_error = error
            finally:
                try:
                    connection.cursor().execute(self._MULTI_USER)
                except Exception as error:
                    cleanup_error = error
                    # RESTORE may invalidate the original connection. Retry from master.
                    try:
                        recovery = get_connection(self._MASTER, autocommit=True)
                        try:
                            recovery.cursor().execute(self._MULTI_USER)
                            cleanup_error = None
                        finally:
                            recovery.close()
                    except Exception as retry_error:
                        cleanup_error = retry_error
        finally:
            connection.close()

        if cleanup_error is not None:
            raise RestoreCleanupError(
                "Không thể đưa QLDSV về chế độ MULTI_USER."
            ) from cleanup_error
        if operation_error is not None:
            raise operation_error

    @staticmethod
    def _finish_statement(cursor) -> None:
        """Wait for every result set so ODBC finishes the SQL batch."""
        while True:
            if cursor.description is not None:
                cursor.fetchall()
            if not cursor.nextset():
                break
