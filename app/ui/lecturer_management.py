"""Admin lecturer entity forms, separate from SQL Account Management."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from app.models.lecturer import Lecturer
from app.services.lecturer_service import LecturerService, LecturerServiceError
from app.ui.styles import DIALOG_STYLE


class LecturerFormDialog(QDialog):
    def __init__(self, on_save: Callable, lecturer: Lecturer | None = None, parent=None) -> None:
        super().__init__(parent)
        self._on_save = on_save
        self._lecturer = lecturer
        self.setWindowTitle("Sửa giảng viên" if lecturer else "Thêm giảng viên")
        self.setMinimumWidth(430)
        self.setStyleSheet(DIALOG_STYLE)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.magv_input = QLineEdit(lecturer.magv if lecturer else "")
        self.magv_input.setObjectName("lecturerMagvInput")
        self.magv_input.setMaxLength(10)
        self.magv_input.textChanged.connect(
            lambda text: self._uppercase_identifier(self.magv_input, text)
        )
        self.magv_input.setReadOnly(lecturer is not None)
        self.ho_input = QLineEdit((lecturer.ho or "") if lecturer else "")
        self.ho_input.setObjectName("lecturerHoInput")
        self.ho_input.setMaxLength(40)
        self.ten_input = QLineEdit((lecturer.ten or "") if lecturer else "")
        self.ten_input.setObjectName("lecturerTenInput")
        self.ten_input.setMaxLength(10)
        self.phai_combo = QComboBox()
        self.phai_combo.setObjectName("lecturerPhaiCombo")
        self.phai_combo.addItem("Nam", True)
        self.phai_combo.addItem("Nữ", False)
        self.phai_combo.setCurrentIndex(0 if lecturer is None or lecturer.phai else 1)
        form.addRow("MAGV", self.magv_input)
        form.addRow("Họ", self.ho_input)
        form.addRow("Tên", self.ten_input)
        form.addRow("Phái", self.phai_combo)
        buttons = QHBoxLayout()
        buttons.addStretch()
        save_button = QPushButton("Lưu")
        save_button.setObjectName("saveLecturerButton")
        save_button.clicked.connect(self._save)
        cancel_button = QPushButton("Hủy")
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(save_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(form)
        layout.addLayout(buttons)

    @staticmethod
    def _uppercase_identifier(editor: QLineEdit, text: str) -> None:
        uppercase = text.upper()
        if uppercase == text:
            return
        cursor = editor.cursorPosition()
        editor.setText(uppercase)
        editor.setCursorPosition(min(cursor, len(uppercase)))

    def _save(self) -> None:
        values = {
            # Even a programmatic change to the read-only editor cannot rename the entity.
            "magv": self._lecturer.magv if self._lecturer else self.magv_input.text(),
            "ho": self.ho_input.text(),
            "ten": self.ten_input.text(),
            "phai": self.phai_combo.currentData(),
        }
        try:
            self._on_save(values)
        except (LecturerServiceError, PermissionError) as error:
            QMessageBox.warning(self, "Không thể lưu giảng viên", str(error))
            return
        self.accept()


class LecturerManagementDialog(QDialog):
    HEADERS = ("MAGV", "Họ", "Tên", "Phái")

    def __init__(self, lecturer_service: LecturerService | None = None, parent=None) -> None:
        super().__init__(parent)
        self._service = lecturer_service or LecturerService()
        self._lecturers: list[Lecturer] = []
        self.setWindowTitle("Quản lý giảng viên")
        self.resize(780, 480)
        self.setStyleSheet(DIALOG_STYLE)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Danh sách giảng viên"))
        self.lecturer_table = QTableWidget(0, len(self.HEADERS))
        self.lecturer_table.setObjectName("lecturerTable")
        self.lecturer_table.setHorizontalHeaderLabels(self.HEADERS)
        self.lecturer_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.lecturer_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.lecturer_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.lecturer_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.lecturer_table)
        buttons = QHBoxLayout()
        self.add_button = QPushButton("Thêm giảng viên")
        self.edit_button = QPushButton("Sửa giảng viên")
        self.delete_button = QPushButton("Xóa giảng viên")
        self.add_button.clicked.connect(self._add_lecturer)
        self.edit_button.clicked.connect(self._edit_lecturer)
        self.delete_button.clicked.connect(self._delete_lecturer)
        for button in (self.add_button, self.edit_button, self.delete_button):
            buttons.addWidget(button)
        buttons.addStretch()
        close_button = QPushButton("Đóng")
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)
        self._load_lecturers()

    def _load_lecturers(self) -> None:
        try:
            self._lecturers = self._service.find_all_lecturers()
        except (LecturerServiceError, PermissionError) as error:
            QMessageBox.critical(self, "Lỗi tải giảng viên", str(error))
            self._lecturers = []
        self.lecturer_table.setRowCount(len(self._lecturers))
        for row, lecturer in enumerate(self._lecturers):
            for column, value in enumerate((lecturer.magv, lecturer.ho or "", lecturer.ten or "",
                                            "Nam" if lecturer.phai else "Nữ")):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.lecturer_table.setItem(row, column, item)
        self.lecturer_table.resizeColumnsToContents()

    def _selected_lecturer(self) -> Lecturer | None:
        row = self.lecturer_table.currentRow()
        if row < 0 or row >= len(self._lecturers):
            QMessageBox.information(self, "Chọn giảng viên", "Hãy chọn một giảng viên.")
            return None
        return self._lecturers[row]

    def _open_form(self, lecturer: Lecturer | None = None) -> None:
        def save(values) -> None:
            operation = self._service.update_lecturer if lecturer else self._service.create_lecturer
            operation(**values)

        dialog = LecturerFormDialog(save, lecturer=lecturer, parent=self)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._load_lecturers()
        finally:
            dialog.deleteLater()

    def _add_lecturer(self) -> None:
        self._open_form()

    def _edit_lecturer(self) -> None:
        lecturer = self._selected_lecturer()
        if lecturer is not None:
            self._open_form(lecturer)

    def _delete_lecturer(self) -> None:
        lecturer = self._selected_lecturer()
        if lecturer is None:
            return
        name = " ".join(part for part in (lecturer.ho, lecturer.ten) if part) or "—"
        answer = QMessageBox.question(
            self, "Xác nhận xóa giảng viên",
            f"Xóa giảng viên {lecturer.magv} — {name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.delete_lecturer(lecturer.magv)
        except (LecturerServiceError, PermissionError) as error:
            QMessageBox.warning(self, "Không thể xóa giảng viên", str(error))
            return
        self._load_lecturers()
