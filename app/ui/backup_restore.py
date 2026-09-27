"""Admin backup list, backup creation, and confirmed restore dialog."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.services.backup_restore_service import BackupRestoreError, BackupRestoreService
from app.ui.styles import DIALOG_STYLE


class BackupRestoreDialog(QDialog):
    def __init__(
        self,
        backup_service: BackupRestoreService | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._service = backup_service or BackupRestoreService()
        self.restore_performed = False
        self.setWindowTitle("Sao lưu / Phục hồi QLDSV")
        self.resize(850, 570)
        self.setMinimumSize(700, 470)
        self.setStyleSheet(DIALOG_STYLE)
        self._build_ui()
        self._load_backups(show_error=False)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        heading = QLabel("Sao lưu và phục hồi cơ sở dữ liệu")
        heading.setStyleSheet("font-size: 19px; font-weight: 700; color: #19324d;")
        description = QLabel("File sao lưu được lưu trong thư mục dùng chung với SQL Server.")
        layout.addWidget(heading)
        layout.addWidget(description)

        directory_row = QHBoxLayout()
        directory_label = QLabel("Thư mục sao lưu")
        self.directory_input = QLineEdit()
        self.directory_input.setObjectName("backupDirectoryInput")
        self.directory_input.setReadOnly(True)
        try:
            directory = self._service.configured_directory()
        except PermissionError:
            directory = "Không có quyền xem cấu hình sao lưu"
        self.directory_input.setText(directory or "Chưa cấu hình QLDSV_BACKUP_DIR")
        directory_row.addWidget(directory_label)
        directory_row.addWidget(self.directory_input, 1)
        layout.addLayout(directory_row)

        filename_hint = QLabel("Tên file tự tạo: QLDSV_YYYYMMDD_HHMMSS_ffffff.bak")
        filename_hint.setObjectName("backupFilenameHint")
        layout.addWidget(filename_hint)

        backup_row = QHBoxLayout()
        self.backup_button = QPushButton("Sao lưu")
        self.backup_button.setObjectName("backupButton")
        self.backup_button.clicked.connect(self._create_backup)
        backup_row.addWidget(self.backup_button)
        backup_row.addStretch()
        layout.addLayout(backup_row)

        list_heading = QLabel("Các bản sao lưu hiện có")
        list_heading.setStyleSheet("font-size: 16px; font-weight: 700; color: #19324d;")
        layout.addWidget(list_heading)

        self.backup_table = QTableWidget(0, 3)
        self.backup_table.setObjectName("backupTable")
        self.backup_table.setHorizontalHeaderLabels(
            ("Tên file", "Thời gian", "Đường dẫn đầy đủ")
        )
        self.backup_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.backup_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.backup_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.backup_table.setAlternatingRowColors(True)
        self.backup_table.verticalHeader().setVisible(False)
        self.backup_table.horizontalHeader().setStretchLastSection(True)
        self.backup_table.itemSelectionChanged.connect(self._update_restore_button)
        layout.addWidget(self.backup_table, 1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("backupStatusLabel")
        layout.addWidget(self.status_label)

        buttons = QHBoxLayout()
        self.refresh_button = QPushButton("Làm mới")
        self.refresh_button.clicked.connect(lambda: self._load_backups(show_error=True))
        self.restore_button = QPushButton("Phục hồi")
        self.restore_button.setObjectName("restoreButton")
        self.restore_button.setEnabled(False)
        self.restore_button.clicked.connect(self._restore_selected)
        close_button = QPushButton("Đóng")
        close_button.clicked.connect(self.reject)
        buttons.addWidget(self.refresh_button)
        buttons.addStretch()
        buttons.addWidget(self.restore_button)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

    def _load_backups(self, show_error: bool) -> None:
        self.backup_table.clearSelection()
        try:
            backups = self._service.list_backups()
        except (BackupRestoreError, PermissionError) as error:
            self.backup_table.setRowCount(0)
            self.restore_button.setEnabled(False)
            self.status_label.setText(str(error))
            if show_error:
                QMessageBox.warning(self, "Không thể đọc bản sao lưu", str(error))
            return

        self.backup_table.setRowCount(len(backups))
        for row, backup in enumerate(backups):
            values = (
                backup.filename,
                backup.modified_at.strftime("%d/%m/%Y %H:%M:%S"),
                str(backup.path),
            )
            for column, value in enumerate(values):
                self.backup_table.setItem(row, column, QTableWidgetItem(value))
        self.backup_table.resizeColumnsToContents()
        self.status_label.setText(f"{len(backups)} bản sao lưu trong thư mục đã cấu hình.")
        self._update_restore_button()

    def _update_restore_button(self) -> None:
        self.restore_button.setEnabled(bool(self.backup_table.selectionModel().selectedRows()))

    def _create_backup(self) -> None:
        self.backup_button.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        backup = None
        error = None
        try:
            backup = self._service.backup_database()
        except (BackupRestoreError, PermissionError) as caught:
            error = caught
        finally:
            QApplication.restoreOverrideCursor()
            self.backup_button.setEnabled(True)
        if error is not None:
            QMessageBox.warning(self, "Sao lưu thất bại", str(error))
            return
        self._load_backups(show_error=False)
        QMessageBox.information(self, "Sao lưu thành công", f"Đã tạo: {backup.path}")

    def _restore_selected(self) -> None:
        selected_rows = self.backup_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "Chọn bản sao lưu", "Hãy chọn một file .bak để phục hồi.")
            return
        row = selected_rows[0].row()
        filename_item = self.backup_table.item(row, 0)
        if filename_item is None:
            QMessageBox.warning(self, "Không thể phục hồi", "Bản sao lưu đã chọn không hợp lệ.")
            return

        answer = QMessageBox.question(
            self,
            "Xác nhận phục hồi",
            "Bạn có chắc chắn muốn phục hồi cơ sở dữ liệu từ bản sao lưu này không?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.status_label.setText("Đã hủy phục hồi.")
            return

        self.restore_button.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        error = None
        try:
            self._service.restore_database(filename_item.text())
        except (BackupRestoreError, PermissionError) as caught:
            error = caught
        finally:
            QApplication.restoreOverrideCursor()
        if error is not None:
            self._update_restore_button()
            QMessageBox.warning(self, "Phục hồi thất bại", str(error))
            return
        self.restore_performed = True
        QMessageBox.information(
            self,
            "Phục hồi thành công",
            "QLDSV đã được phục hồi. Hãy đăng nhập lại để tiếp tục.",
        )
        self.accept()
