"""Admin Class (Lop) management dialog with Them, Xoa, Ghi, Phuc hoi, Thoat."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.models.lop import Lop
from app.services.lop_service import LopService, LopServiceError
from app.ui.styles import DIALOG_STYLE


class LopManagementDialog(QDialog):
    HEADERS = ("Mã lớp", "Tên lớp")

    def __init__(self, lop_service: LopService | None = None, parent=None) -> None:
        super().__init__(parent)
        self._service = lop_service or LopService()
        self._lops: list[Lop] = []
        self._is_adding = False
        self._current_malop: str | None = None

        self.setWindowTitle("Quản lý danh mục Lớp")
        self.resize(760, 500)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Danh sách lớp học"))

        self.lop_table = QTableWidget(0, len(self.HEADERS))
        self.lop_table.setObjectName("lopTable")
        self.lop_table.setHorizontalHeaderLabels(self.HEADERS)
        self.lop_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.lop_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.lop_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.lop_table.horizontalHeader().setStretchLastSection(True)
        self.lop_table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.lop_table)

        form_group = QGroupBox("Thông tin lớp")
        form_layout = QFormLayout(form_group)
        self.malop_input = QLineEdit()
        self.malop_input.setObjectName("malopInput")
        self.malop_input.setMaxLength(8)
        self.malop_input.setPlaceholderText("VD: CNTT01 (tối đa 8 ký tự)")
        self.malop_input.textChanged.connect(self._on_malop_changed)

        self.tenlop_input = QLineEdit()
        self.tenlop_input.setObjectName("tenlopInput")
        self.tenlop_input.setMaxLength(40)
        self.tenlop_input.setPlaceholderText("VD: Công nghệ thông tin 01")
        self.tenlop_input.textChanged.connect(self._update_button_states)

        form_layout.addRow("Mã lớp (*)", self.malop_input)
        form_layout.addRow("Tên lớp (*)", self.tenlop_input)
        layout.addWidget(form_group)

        buttons = QHBoxLayout()
        self.add_button = QPushButton("Thêm")
        self.delete_button = QPushButton("Xóa")
        self.save_button = QPushButton("Ghi")
        self.undo_button = QPushButton("Phục hồi")
        self.close_button = QPushButton("Thoát")

        self.add_button.setObjectName("addLopButton")
        self.delete_button.setObjectName("deleteLopButton")
        self.save_button.setObjectName("saveLopButton")
        self.undo_button.setObjectName("undoLopButton")
        self.close_button.setObjectName("closeLopButton")

        self.add_button.clicked.connect(self._start_add)
        self.delete_button.clicked.connect(self._delete_selected)
        self.save_button.clicked.connect(self._save)
        self.undo_button.clicked.connect(self._undo)
        self.close_button.clicked.connect(self.accept)

        for btn in (self.add_button, self.delete_button, self.save_button, self.undo_button):
            buttons.addWidget(btn)
        buttons.addStretch()
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

        self._load_lops()

    def _on_malop_changed(self, text: str) -> None:
        uppercase = text.upper()
        if uppercase != text:
            cursor = self.malop_input.cursorPosition()
            self.malop_input.setText(uppercase)
            self.malop_input.setCursorPosition(min(cursor, len(uppercase)))
        self._update_button_states()

    def _load_lops(self, select_malop: str | None = None) -> None:
        try:
            self._lops = self._service.find_all()
        except (LopServiceError, PermissionError) as error:
            QMessageBox.critical(self, "Lỗi tải danh sách lớp", str(error))
            self._lops = []

        self.lop_table.blockSignals(True)
        self.lop_table.setRowCount(len(self._lops))
        target_row = 0 if self._lops else -1
        for row, lop in enumerate(self._lops):
            if select_malop and lop.malop == select_malop:
                target_row = row
            for col, value in enumerate((lop.malop, lop.tenlop)):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.lop_table.setItem(row, col, item)
        self.lop_table.resizeColumnsToContents()
        self.lop_table.blockSignals(False)

        self._is_adding = False
        if target_row >= 0:
            self.lop_table.selectRow(target_row)
            self._populate_from_row(target_row)
        else:
            self._clear_form()
        self._update_button_states()

    def _populate_from_row(self, row: int) -> None:
        if 0 <= row < len(self._lops):
            lop = self._lops[row]
            self._current_malop = lop.malop
            self.malop_input.setText(lop.malop)
            self.malop_input.setReadOnly(True)
            self.tenlop_input.setText(lop.tenlop)
            self.tenlop_input.setReadOnly(False)
        else:
            self._clear_form()

    def _clear_form(self) -> None:
        self._current_malop = None
        self.malop_input.clear()
        self.tenlop_input.clear()
        self.malop_input.setReadOnly(True)
        self.tenlop_input.setReadOnly(True)

    def _on_selection_changed(self) -> None:
        if self._is_adding:
            return
        row = self.lop_table.currentRow()
        self._populate_from_row(row)
        self._update_button_states()

    def _is_dirty(self) -> bool:
        if self._is_adding:
            return True
        if self._current_malop is None:
            return False
        current_lop = next((l for l in self._lops if l.malop == self._current_malop), None)
        if current_lop is None:
            return False
        return self.tenlop_input.text().strip() != current_lop.tenlop

    def _update_button_states(self) -> None:
        has_selection = self._current_malop is not None
        dirty = self._is_dirty()

        self.add_button.setEnabled(not self._is_adding)
        self.delete_button.setEnabled(not self._is_adding and has_selection)
        self.save_button.setEnabled(self._is_adding or dirty)
        self.undo_button.setEnabled(self._is_adding or dirty)

    def _start_add(self) -> None:
        self._is_adding = True
        self._current_malop = None
        self.lop_table.clearSelection()
        self.malop_input.setReadOnly(False)
        self.tenlop_input.setReadOnly(False)
        self.malop_input.clear()
        self.tenlop_input.clear()
        self.malop_input.setFocus()
        self._update_button_states()

    def _undo(self) -> None:
        if self._is_adding:
            self._is_adding = False
            if self._lops:
                self.lop_table.selectRow(0)
                self._populate_from_row(0)
            else:
                self._clear_form()
        else:
            row = self.lop_table.currentRow()
            self._populate_from_row(row)
        self._update_button_states()

    def _save(self) -> None:
        malop = self.malop_input.text().strip().upper()
        tenlop = self.tenlop_input.text().strip()
        try:
            if self._is_adding:
                self._service.create(malop, tenlop)
                QMessageBox.information(self, "Thành công", f"Đã thêm lớp '{malop}'.")
            else:
                if not self._current_malop:
                    return
                self._service.update(self._current_malop, tenlop)
                QMessageBox.information(self, "Thành công", f"Đã cập nhật lớp '{self._current_malop}'.")
                malop = self._current_malop
        except (LopServiceError, PermissionError) as error:
            QMessageBox.warning(self, "Không thể lưu lớp", str(error))
            return
        self._load_lops(select_malop=malop)

    def _delete_selected(self) -> None:
        if not self._current_malop:
            return
        lop = next((l for l in self._lops if l.malop == self._current_malop), None)
        if not lop:
            return
        answer = QMessageBox.question(
            self,
            "Xác nhận xóa lớp",
            f"Bạn có chắc chắn muốn xóa lớp '{lop.malop} — {lop.tenlop}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.delete(lop.malop)
            QMessageBox.information(self, "Thành công", f"Đã xóa lớp '{lop.malop}'.")
        except (LopServiceError, PermissionError) as error:
            QMessageBox.warning(self, "Không thể xóa lớp", str(error))
            return
        self._load_lops()

