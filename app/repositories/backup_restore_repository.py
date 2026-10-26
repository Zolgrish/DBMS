"""SQL-visible backup paths and sets, using the authenticated Admin's master."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath

from app.utils import session


class InvalidBackupError(Exception):
    """A safe path, position or backup-header validation failure."""


class RestoreCleanupError(Exception):
    """QLDSV could not be returned to MULTI_USER after a restore attempt."""


@dataclass(frozen=True)
class BackupSet:
    database_name: str
    backup_type: int
    position: int
    user_name: str
    started_at: datetime
    finished_at: datetime


class BackupRestoreRepository:
    DATABASE_NAME = "QLDSV"
    _MULTI_USER = "ALTER DATABASE [QLDSV] SET MULTI_USER"
    _HEADER_COLUMNS = {"DatabaseName", "BackupType", "Position", "UserName", "BackupStartDate", "BackupFinishDate"}

    @staticmethod
    def validate_position(position: int) -> int:
        if type(position) is not int or not 1 <= position <= 2147483647:
            raise InvalidBackupError("Position phải là số nguyên dương hợp lệ.")
        return position

    @staticmethod
    def _validate_sql_path(sql_path: str) -> None:
        if (not isinstance(sql_path, str) or not sql_path.startswith("/") or sql_path.startswith("//")
                or "\\" in sql_path or any(ord(c) < 32 for c in sql_path)
                or ".." in PurePosixPath(sql_path).parts or str(PurePosixPath(sql_path)) != sql_path
                or PurePosixPath(sql_path).suffix.lower() != ".bak"):
            raise InvalidBackupError("Đường dẫn backup của SQL Server không hợp lệ.")
        try:
            valid_length = len(sql_path.encode("utf-16-le")) <= 8000
        except UnicodeError:
            valid_length = False
        if not valid_length:
            raise InvalidBackupError("Đường dẫn backup của SQL Server không hợp lệ.")

    def create_backup(self, sql_path: str) -> None:
        self._validate_sql_path(sql_path)
        with session.master_cursor() as cursor:
            cursor.execute(
                """
                DECLARE @backup_path NVARCHAR(4000) = ?;
                BACKUP DATABASE [QLDSV] TO DISK = @backup_path WITH INIT, CHECKSUM;
                """, sql_path,
            )
            self._finish_statement(cursor)

    def read_backup_sets(self, sql_path: str) -> list[BackupSet]:
        self._validate_sql_path(sql_path)
        headers = []
        malformed = False
        with session.master_cursor() as cursor:
            cursor.execute("DECLARE @backup_path NVARCHAR(4000) = ?; RESTORE HEADERONLY FROM DISK = @backup_path;", sql_path)
            while True:
                if cursor.description is not None:
                    columns = [column[0] for column in cursor.description]
                    rows = cursor.fetchall()
                    if not self._HEADER_COLUMNS.issubset(columns):
                        malformed = True
                    else:
                        headers.extend(dict(zip(columns, row)) for row in rows)
                if not cursor.nextset():
                    break
        sets = []
        positions = set()
        for header in headers:
            position = header.get("Position")
            start, finish = header.get("BackupStartDate"), header.get("BackupFinishDate")
            if (type(position) is not int or position < 1 or position in positions
                    or not isinstance(header.get("DatabaseName"), str) or not header["DatabaseName"]
                    or type(header.get("BackupType")) is not int or header["BackupType"] < 1
                    or header.get("UserName") is not None and not isinstance(header["UserName"], str)
                    or not isinstance(start, datetime) or not isinstance(finish, datetime)
                    or start.tzinfo is not None or finish.tzinfo is not None or finish < start):
                malformed = True
                continue
            positions.add(position)
            sets.append(BackupSet(header["DatabaseName"], header["BackupType"], position,
                                  header["UserName"] or "", start, finish))
        if malformed or not sets:
            raise InvalidBackupError("Không đọc được metadata hợp lệ từ file backup.")
        return sets

    def verify_backup(self, sql_path: str, position: int) -> None:
        position = self.validate_position(position)
        selected = next((item for item in self.read_backup_sets(sql_path) if item.position == position), None)
        if selected is None:
            raise InvalidBackupError("Không tìm thấy Position đã chọn trong file backup.")
        if selected.database_name != self.DATABASE_NAME or selected.backup_type != 1:
            raise InvalidBackupError("Backup set đã chọn không phải bản sao lưu đầy đủ của QLDSV.")
        with session.master_cursor() as cursor:
            # Only a validated numeric literal is formatted; the path stays data.
            cursor.execute(
                "DECLARE @backup_path NVARCHAR(4000) = ?; "
                f"RESTORE VERIFYONLY FROM DISK = @backup_path WITH FILE = {position};", sql_path,
            )
            self._finish_statement(cursor)

    def restore_backup(self, sql_path: str, position: int) -> None:
        self._validate_sql_path(sql_path)
        position = self.validate_position(position)
        connection = session.require_master_connection()
        session.invalidate_qldsv_connection()
        operation_error = cleanup_failed = None
        try:
            try:
                self._execute(connection, "ALTER DATABASE [QLDSV] SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
                self._execute(
                    connection, "DECLARE @backup_path NVARCHAR(4000) = ?; "
                    f"RESTORE DATABASE [QLDSV] FROM DISK = @backup_path WITH FILE = {position}, REPLACE, RECOVERY;",
                    sql_path,
                )
            except Exception as error:
                operation_error = error
            finally:
                try:
                    self._execute(connection, self._MULTI_USER)
                except Exception:
                    cleanup_failed = True
        finally:
            # _execute deliberately does not borrow a session cursor: even a broken
            # master must remain available until MULTI_USER cleanup was attempted.
            session.invalidate_session()
        if cleanup_failed:
            raise RestoreCleanupError("Không thể đưa QLDSV về chế độ MULTI_USER.") from None
        if operation_error is not None:
            raise operation_error

    @classmethod
    def _execute(cls, connection, sql: str, *parameters) -> None:
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
