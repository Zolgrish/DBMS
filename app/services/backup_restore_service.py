"""Admin-only backup workflow, directory validation, and friendly errors."""

from dataclasses import dataclass
from datetime import datetime
import logging
import os
from pathlib import Path

import pyodbc

from app.repositories.backup_restore_repository import (
    BackupRestoreRepository,
    InvalidBackupError,
    RestoreCleanupError,
)
from app.services.authorization import require_admin


class BackupRestoreError(Exception):
    """An expected backup/restore failure safe to display in the UI."""


@dataclass(frozen=True)
class BackupFile:
    filename: str
    modified_at: datetime
    path: Path


class BackupRestoreService:
    def __init__(
        self,
        repository: BackupRestoreRepository | None = None,
        backup_directory: str | Path | None = None,
    ) -> None:
        self._repository = repository or BackupRestoreRepository()
        self._configured_path = (
            str(backup_directory)
            if backup_directory is not None
            else os.getenv("QLDSV_BACKUP_DIR", "").strip()
        )

    def configured_directory(self) -> str:
        require_admin()
        return self._configured_path

    @staticmethod
    def generate_filename(at: datetime | None = None) -> str:
        timestamp = (at or datetime.now()).strftime("%Y%m%d_%H%M%S_%f")
        return f"QLDSV_{timestamp}.bak"

    def list_backups(self) -> list[BackupFile]:
        require_admin()
        directory = self._directory()
        try:
            backups = []
            for path in directory.iterdir():
                if path.is_symlink() or path.suffix.casefold() != ".bak" or not path.is_file():
                    continue
                backups.append(
                    BackupFile(
                        filename=path.name,
                        modified_at=datetime.fromtimestamp(path.stat().st_mtime).astimezone(),
                        path=path,
                    )
                )
        except PermissionError:
            raise BackupRestoreError("Ứng dụng không có quyền đọc thư mục sao lưu.") from None
        except OSError:
            logging.exception("Không thể đọc thư mục sao lưu.")
            raise BackupRestoreError("Không thể đọc danh sách file sao lưu.") from None
        return sorted(backups, key=lambda backup: backup.modified_at, reverse=True)

    def backup_database(self) -> BackupFile:
        require_admin()
        directory = self._directory()
        path = directory / self.generate_filename()
        try:
            self._repository.create_backup(path)
        except (pyodbc.Error, ValueError) as error:
            logging.exception("Không thể sao lưu QLDSV.")
            if self._is_connection_error(error):
                raise BackupRestoreError("Không thể kết nối SQL Server để sao lưu.") from None
            raise BackupRestoreError(
                "SQL Server không thể tạo file sao lưu. Kiểm tra đường dẫn, quyền tài khoản "
                "dịch vụ SQL Server và dung lượng đĩa."
            ) from None
        return self._file_info(path)

    def restore_database(self, filename: str) -> None:
        require_admin()
        directory = self._directory()
        path = self._selected_file(directory, filename)
        try:
            self._repository.verify_backup(path)
        except InvalidBackupError as error:
            raise BackupRestoreError(str(error)) from None
        except (pyodbc.Error, ValueError) as error:
            logging.exception("Không thể xác minh bản sao lưu.")
            if self._is_connection_error(error):
                raise BackupRestoreError("Không thể kết nối SQL Server để kiểm tra bản sao lưu.") from None
            raise BackupRestoreError(
                "Không thể xác minh bản sao lưu. File có thể hỏng hoặc SQL Server "
                "không có quyền đọc đường dẫn này."
            ) from None

        try:
            self._repository.restore_backup(path)
        except RestoreCleanupError:
            logging.exception("Không thể khôi phục chế độ MULTI_USER sau restore.")
            raise BackupRestoreError(
                "Phục hồi thất bại và không thể đưa QLDSV về chế độ MULTI_USER. "
                "Hãy kiểm tra SQL Server trước khi tiếp tục sử dụng."
            ) from None
        except (pyodbc.Error, ValueError):
            logging.exception("Phục hồi QLDSV thất bại.")
            raise BackupRestoreError(
                "Phục hồi thất bại. Kiểm tra quyền SQL Server, file sao lưu và các kết nối đang mở."
            ) from None

    def _directory(self) -> Path:
        if not self._configured_path:
            raise BackupRestoreError("Chưa cấu hình QLDSV_BACKUP_DIR trong file .env.")
        directory = Path(self._configured_path).expanduser()
        if not directory.is_absolute():
            raise BackupRestoreError("QLDSV_BACKUP_DIR phải là đường dẫn tuyệt đối.")
        try:
            if not directory.exists():
                raise BackupRestoreError("Thư mục sao lưu không tồn tại.")
            if not directory.is_dir():
                raise BackupRestoreError("Đường dẫn sao lưu không phải thư mục.")
            return directory.resolve()
        except PermissionError:
            raise BackupRestoreError("Ứng dụng không có quyền truy cập thư mục sao lưu.") from None
        except OSError:
            logging.exception("Không thể truy cập thư mục sao lưu.")
            raise BackupRestoreError("Không thể truy cập thư mục sao lưu.") from None

    def _selected_file(self, directory: Path, filename: str) -> Path:
        if (
            not isinstance(filename, str)
            or not filename
            or "/" in filename
            or "\\" in filename
            or Path(filename).name != filename
            or Path(filename).suffix.casefold() != ".bak"
        ):
            raise BackupRestoreError("Chỉ được chọn file .bak trong thư mục sao lưu.")
        path = directory / filename
        try:
            if path.is_symlink():
                raise BackupRestoreError("Không thể phục hồi từ liên kết tới file bên ngoài.")
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(directory) or not resolved.is_file():
                raise BackupRestoreError("File sao lưu không hợp lệ.")
            return resolved
        except FileNotFoundError:
            raise BackupRestoreError("Không tìm thấy file sao lưu đã chọn.") from None
        except PermissionError:
            raise BackupRestoreError("Ứng dụng không có quyền đọc file sao lưu.") from None
        except OSError:
            logging.exception("Không thể mở file sao lưu đã chọn.")
            raise BackupRestoreError("Không thể đọc file sao lưu đã chọn.") from None

    def _file_info(self, path: Path) -> BackupFile:
        try:
            return BackupFile(
                filename=path.name,
                modified_at=datetime.fromtimestamp(path.stat().st_mtime).astimezone(),
                path=path,
            )
        except FileNotFoundError:
            raise BackupRestoreError(
                "SQL Server đã chạy lệnh sao lưu nhưng ứng dụng không thấy file. "
                "Hãy dùng thư mục chung mà cả ứng dụng và SQL Server đều truy cập được."
            ) from None
        except PermissionError:
            raise BackupRestoreError("Ứng dụng không có quyền đọc file sao lưu vừa tạo.") from None
        except OSError:
            logging.exception("Không thể xác nhận file sao lưu vừa tạo.")
            raise BackupRestoreError("Không thể xác nhận file sao lưu vừa tạo.") from None

    @staticmethod
    def _is_connection_error(error: Exception) -> bool:
        if isinstance(error, ValueError):
            return True
        state = str(error.args[0]) if error.args else ""
        return state.startswith("08") or state in {"IM002", "HYT00", "HYT01"}
