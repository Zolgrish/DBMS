"""Admin backup sets mapped by filename between host and SQL filesystems."""

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path, PurePosixPath
import re
import uuid

import pyodbc

from app.repositories.backup_restore_repository import BackupRestoreRepository, InvalidBackupError, RestoreCleanupError
from app.services.authorization import require_admin
from app.utils import session


class BackupRestoreError(Exception):
    """Safe, actionable backup/restore error for the UI."""


class BackupSessionError(BackupRestoreError):
    """Listing must stop on session loss, rather than skip every remaining file."""


@dataclass(frozen=True)
class BackupFile:
    filename: str
    position: int
    user_name: str
    path: Path
    started_at: datetime
    finished_at: datetime

    @property
    def backup_at(self) -> datetime:
        return self.finished_at


class BackupRestoreService:
    def __init__(self, repository: BackupRestoreRepository | None = None,
                 backup_directory: str | Path | None = None, sql_backup_directory: str | None = None) -> None:
        self._repository = repository or BackupRestoreRepository()
        self._configured_path = str(backup_directory) if backup_directory is not None else os.getenv("QLDSV_BACKUP_DIR", "")
        self._sql_directory = sql_backup_directory if sql_backup_directory is not None else os.getenv("QLDSV_SQL_BACKUP_DIR", "")
        self.skipped_files = 0

    def configured_directory(self) -> str:
        require_admin()
        return self._configured_path

    @staticmethod
    def generate_filename(at: datetime | None = None) -> str:
        stamp = (at or datetime.now()).strftime("%Y%m%d_%H%M%S_%f")
        return f"QLDSV_{stamp}_{uuid.uuid4().hex}.bak"

    def list_backups(self) -> list[BackupFile]:
        require_admin()
        self.skipped_files = 0
        directory = self._directory()
        self._validate_sql_directory()
        try:
            paths = list(directory.iterdir())
        except OSError:
            raise BackupRestoreError("Không thể đọc thư mục backup trên máy ứng dụng. Kiểm tra quyền đọc.") from None
        backups = []
        for path in paths:
            if path.suffix.casefold() != ".bak":
                continue
            try:
                host = self._selected_file(directory, path.name)
                sets = self._run_sql(lambda: self._repository.read_backup_sets(self._sql_path(path.name)), "metadata")
                items = self._items(host, sets)
                backups.extend(items)
                if not items:
                    self.skipped_files += 1
            except BackupSessionError:
                raise
            except BackupRestoreError:
                # A corrupt/unreadable/unrelated file does not hide usable backups.
                self.skipped_files += 1
        return sorted(backups, key=lambda item: (item.backup_at, item.filename, item.position), reverse=True)

    def backup_database(self) -> BackupFile:
        require_admin()
        directory = self._directory()
        filename = self.generate_filename()
        sql_path = self._sql_path(filename)
        path = directory / filename
        try:
            if path.exists() or path.is_symlink():
                raise BackupRestoreError("Tên file backup đã tồn tại. Hãy thử lại; không ghi đè file có sẵn.")
        except OSError:
            raise BackupRestoreError("Không thể kiểm tra file backup trên máy ứng dụng. Kiểm tra quyền đọc thư mục.") from None
        self._run_sql(lambda: self._repository.create_backup(sql_path), "backup")
        try:
            host = self._selected_file(directory, filename)
        except BackupRestoreError:
            raise BackupRestoreError("SQL Server đã chạy backup nhưng ứng dụng không đọc được file. Kiểm tra hai đường dẫn cùng Docker bind mount.") from None
        items = self._items(host, self._run_sql(lambda: self._repository.read_backup_sets(sql_path), "metadata"))
        if len(items) != 1 or items[0].position != 1:
            raise BackupRestoreError("Không xác nhận được metadata full backup QLDSV vừa tạo.")
        return items[0]

    def verify_backup(self, filename: str, position: int) -> None:
        require_admin()
        _, sql_path = self._selection(filename, position)
        self._run_sql(lambda: self._repository.verify_backup(sql_path, position), "verify")

    def restore_database(self, filename: str, position: int) -> None:
        require_admin()
        self.verify_backup(filename, position)
        # Check host visibility again after verification, before closing QLDSV.
        _, sql_path = self._selection(filename, position)
        self._run_sql(lambda: self._repository.restore_backup(sql_path, position), "restore")

    def _selection(self, filename: str, position: int) -> tuple[Path, str]:
        try:
            BackupRestoreRepository.validate_position(position)
        except InvalidBackupError:
            raise BackupRestoreError("Position phải là số nguyên dương hợp lệ.") from None
        host = self._selected_file(self._directory(), filename)
        return host, self._sql_path(filename)

    @staticmethod
    def _items(path: Path, sets) -> list[BackupFile]:
        return [BackupFile(path.name, item.position, item.user_name, path, item.started_at, item.finished_at)
                for item in sets if item.database_name == "QLDSV" and item.backup_type == 1]

    def _directory(self) -> Path:
        if not self._configured_path:
            raise BackupRestoreError("Chưa cấu hình QLDSV_BACKUP_DIR cho máy ứng dụng.")
        directory = Path(self._configured_path).expanduser()
        if not directory.is_absolute():
            raise BackupRestoreError("QLDSV_BACKUP_DIR phải là đường dẫn tuyệt đối trên máy ứng dụng.")
        try:
            directory = directory.resolve(strict=True)
            if not directory.is_dir():
                raise BackupRestoreError("QLDSV_BACKUP_DIR không phải thư mục.")
            with os.scandir(directory):
                pass
            return directory
        except FileNotFoundError:
            raise BackupRestoreError("Thư mục backup trên máy ứng dụng không tồn tại.") from None
        except (OSError, ValueError, RuntimeError):
            raise BackupRestoreError("Không thể đọc thư mục backup trên máy ứng dụng. Kiểm tra đường dẫn và quyền đọc.") from None

    def _validate_sql_directory(self) -> None:
        value = self._sql_directory
        if not value:
            raise BackupRestoreError("Chưa cấu hình QLDSV_SQL_BACKUP_DIR cho SQL Server.")
        if (not isinstance(value, str) or not value.startswith("/") or value.startswith("//")
                or "\\" in value or ":" in value or value != value.strip()
                or any(ord(c) < 32 for c in value) or ".." in PurePosixPath(value).parts
                or str(PurePosixPath(value)) != value or value == "/"):
            raise BackupRestoreError("QLDSV_SQL_BACKUP_DIR phải là đường dẫn Linux tuyệt đối, không có traversal.")

    @staticmethod
    def _validate_filename(filename: str) -> None:
        if (not isinstance(filename, str) or not filename or filename != filename.strip()
                or re.search(r'[\\/:*?"<>|\x00-\x1f]', filename) or filename.endswith(".")
                or Path(filename).name != filename or Path(filename).suffix.casefold() != ".bak"
                or filename.split(".", 1)[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}):
            raise BackupRestoreError("Chỉ được chọn tên file .bak hợp lệ trong thư mục backup.")
        try:
            valid = len(filename.encode("utf-16-le")) <= 510
        except UnicodeError:
            valid = False
        if not valid:
            raise BackupRestoreError("Tên file backup không hợp lệ.")

    def _sql_path(self, filename: str) -> str:
        self._validate_filename(filename)
        self._validate_sql_directory()
        sql_path = str(PurePosixPath(self._sql_directory) / filename)
        try:
            BackupRestoreRepository._validate_sql_path(sql_path)
        except InvalidBackupError:
            raise BackupRestoreError("Đường dẫn file của SQL Server không hợp lệ hoặc quá dài.") from None
        return sql_path

    def _selected_file(self, directory: Path, filename: str) -> Path:
        self._validate_filename(filename)
        path = directory / filename
        try:
            if path.is_symlink():
                raise BackupRestoreError("Không sử dụng backup qua symlink.")
            resolved = path.resolve(strict=True)
            if resolved.parent != directory or not resolved.is_file():
                raise BackupRestoreError("File backup không hợp lệ hoặc nằm ngoài thư mục cấu hình.")
            with resolved.open("rb"):
                pass
            return resolved
        except FileNotFoundError:
            raise BackupRestoreError("Không tìm thấy file backup đã chọn trên máy ứng dụng.") from None
        except (OSError, ValueError, RuntimeError):
            raise BackupRestoreError("Không thể đọc file backup trên máy ứng dụng. Kiểm tra quyền đọc.") from None

    @staticmethod
    def _run_sql(action, operation: str):
        failure = None
        session_lost = False
        try:
            return action()
        except session.SessionRequiredError:
            session_lost = True
        except InvalidBackupError as error:
            failure = str(error)
        except RestoreCleanupError:
            failure = "Không thể đưa QLDSV về chế độ MULTI_USER. Hãy liên hệ Admin kiểm tra SQL Server trước khi đăng nhập lại."
        except pyodbc.Error as error:
            session_lost = session.is_connection_error(error)
        except (OSError, ValueError):
            pass
        messages = {
            "backup": "SQL Server không thể tạo backup. Kiểm tra quyền ghi thư mục container, quyền BACKUP và dung lượng đĩa.",
            "metadata": "Không đọc được metadata backup. Kiểm tra file và quyền đọc của SQL Server trên thư mục container.",
            "verify": "Không thể xác minh backup. File có thể hỏng hoặc SQL Server không có quyền đọc.",
            "restore": "Phục hồi thất bại. Kiểm tra backup, quyền RESTORE và các kết nối đang sử dụng QLDSV. Hãy đăng nhập lại.",
        }
        # Raise outside handlers: driver diagnostics are neither logged nor chained.
        if session_lost:
            raise BackupSessionError("Phiên SQL không còn hiệu lực. Vui lòng đăng nhập lại.") from None
        raise BackupRestoreError(failure or messages[operation]) from None
