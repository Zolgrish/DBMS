"""Admin Subject (Monhoc) management dialog with Them, Xoa, Ghi, Phuc hoi, Thoat."""

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
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.models.monhoc import Monhoc
from app.services.monhoc_service import MonhocService, MonhocServiceError
from app.ui.styles import DIALOG_STYLE


class MonhocManagementDialog(QDialog):
    HEADERS = ("Mã môn học", "Tên môn học", "Số TC Lý thuyết", "Số TC Thực hành")

    def __init__(self, monhoc_service: MonhocService | None = None, parent=None) -> None:
        super().__init__(parent)
        self._service = monhoc_service or MonhocService()
        self._monhocs: list[Monhoc] = []
        self._is_adding = False
        self._current_mamh: str | None = None

        self.setWindowTitle("Quản lý Môn học")
        self.resize(800, 520)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Danh sách môn học"))

        self.monhoc_table = QTableWidget(0, len(self.HEADERS))
        self.monhoc_table.setObjectName("monhocTable")
        self.monhoc_table.setHorizontalHeaderLabels(self.HEADERS)
        self.monhoc_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.monhoc_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.monhoc_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.monhoc_table.horizontalHeader().setStretchLastSection(True)
        self.monhoc_table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.monhoc_table)

        form_group = QGroupBox("Thông tin môn học")
        form_layout = QFormLayout(form_group)

        self.mamh_input = QLineEdit()
        self.mamh_input.setObjectName("mamhInput")
        self.mamh_input.setMaxLength(5)
        self.mamh_input.setPlaceholderText("VD: CSDL (tối đa 5 ký tự)")
        self.mamh_input.textChanged.connect(self._on_mamh_changed)

        self.tenmh_input = QLineEdit()
        self.tenmh_input.setObjectName("tenmhInput")
        self.tenmh_input.setMaxLength(40)
        self.tenmh_input.setPlaceholderText("VD: Cơ sở dữ liệu")
        self.tenmh_input.textChanged.connect(self._update_button_states)

        self.sotclt_spin = QSpinBox()
        self.sotclt_spin.setObjectName("sotcltSpin")
        self.sotclt_spin.setRange(0, 99)
        self.sotclt_spin.valueChanged.connect(self._update_button_states)

        self.sotcth_spin = QSpinBox()
        self.sotcth_spin.setObjectName("sotcthSpin")
        self.sotcth_spin.setRange(0, 99)
        self.sotcth_spin.valueChanged.connect(self._update_button_states)

        form_layout.addRow("Mã môn học (*)", self.mamh_input)
        form_layout.addRow("Tên môn học (*)", self.tenmh_input)
        form_layout.addRow("Số tín chỉ lý thuyết", self.sotclt_spin)
        form_layout.addRow("Số tín chỉ thực hành", self.sotcth_spin)
        layout.addWidget(form_group)

        buttons = QHBoxLayout()
        self.add_button = QPushButton("Thêm")
        self.delete_button = QPushButton("Xóa")
        self.save_button = QPushButton("Ghi")
        self.undo_button = QPushButton("Phục hồi")
        self.close_button = QPushButton("Thoát")

        self.add_button.setObjectName("addMonhocButton")
        self.delete_button.setObjectName("deleteMonhocButton")
        self.save_button.setObjectName("saveMonhocButton")
        self.undo_button.setObjectName("undoMonhocButton")
        self.close_button.setObjectName("closeMonhocButton")

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

        self._load_monhocs()

    def _on_mamh_changed(self, text: str) -> None:
        uppercase = text.upper()
        if uppercase != text:
            cursor = self.mamh_input.cursorPosition()
            self.mamh_input.setText(uppercase)
            self.mamh_input.setCursorPosition(min(cursor, len(uppercase)))
        self._update_button_states()

    def _load_monhocs(self, select_mamh: str | None = None) -> None:
        try:
            self._monhocs = self._service.find_all()
        except (MonhocServiceError, PermissionError) as error:
            QMessageBox.critical(self, "Lỗi tải danh sách môn học", str(error))
            self._monhocs = []

        self.monhoc_table.blockSignals(True)
        self.monhoc_table.setRowCount(len(self._monhocs))
        target_row = 0 if self._monhocs else -1
        for row, mh in enumerate(self._monhocs):
            if select_mamh and mh.mamh == select_mamh:
                target_row = row
            for col, value in enumerate((mh.mamh, mh.tenmh, str(mh.sotclt), str(mh.sotcth))):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col >= 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.monhoc_table.setItem(row, col, item)
        self.monhoc_table.resizeColumnsToContents()
        self.monhoc_table.blockSignals(False)

        self._is_adding = False
        if target_row >= 0:
            self.monhoc_table.selectRow(target_row)
            self._populate_from_row(target_row)
        else:
            self._clear_form()
        self._update_button_states()

    def _populate_from_row(self, row: int) -> None:
        if 0 <= row < len(self._monhocs):
            mh = self._monhocs[row]
            self._current_mamh = mh.mamh
            self.mamh_input.setText(mh.mamh)
            self.mamh_input.setReadOnly(True)
            self.tenmh_input.setText(mh.tenmh)
            self.tenmh_input.setReadOnly(False)
            self.sotclt_spin.setValue(mh.sotclt)
            self.sotclt_spin.setEnabled(True)
            self.sotcth_spin.setValue(mh.sotcth)
            self.sotcth_spin.setEnabled(True)
        else:
            self._clear_form()

    def _clear_form(self) -> None:
        self._current_mamh = None
        self.mamh_input.clear()
        self.tenmh_input.clear()
        self.sotclt_spin.setValue(0)
        self.sotcth_spin.setValue(0)
        self.mamh_input.setReadOnly(True)
        self.tenmh_input.setReadOnly(True)
        self.sotclt_spin.setEnabled(False)
        self.sotcth_spin.setEnabled(False)

    def _on_selection_changed(self) -> None:
        if self._is_adding:
            return
        row = self.monhoc_table.currentRow()
        self._populate_from_row(row)
        self._update_button_states()

    def _is_dirty(self) -> bool:
        if self._is_adding:
            return True
        if self._current_mamh is None:
            return False
        current_mh = next((m for m in self._monhocs if m.mamh == self._current_mamh), None)
        if current_mh is None:
            return False
        return (
            self.tenmh_input.text().strip() != current_mh.tenmh
            or self.sotclt_spin.value() != current_mh.sotclt
            or self.sotcth_spin.value() != current_mh.sotcth
        )

    def _update_button_states(self) -> None:
        has_selection = self._current_mamh is not None
        dirty = self._is_dirty()

        self.add_button.setEnabled(not self._is_adding)
        self.delete_button.setEnabled(not self._is_adding and has_selection)
        self.save_button.setEnabled(self._is_adding or dirty)
        self.undo_button.setEnabled(self._is_adding or dirty)

    def _start_add(self) -> None:
        self._is_adding = True
        self._current_mamh = None
        self.monhoc_table.clearSelection()
        self.mamh_input.setReadOnly(False)
        self.tenmh_input.setReadOnly(False)
        self.sotclt_spin.setEnabled(True)
        self.sotcth_spin.setEnabled(True)
        self.mamh_input.clear()
        self.tenmh_input.clear()
        self.sotclt_spin.setValue(2)
        self.sotcth_spin.setValue(1)
        self.mamh_input.setFocus()
        self._update_button_states()

    def _undo(self) -> None:
        if self._is_adding:
            self._is_adding = False
            if self._monhocs:
                self.monhoc_table.selectRow(0)
                self._populate_from_row(0)
            else:
                self._clear_form()
        else:
            row = self.monhoc_table.currentRow()
            self._populate_from_row(row)
        self._update_button_states()

    def _save(self) -> None:
        mamh = self.mamh_input.text().strip().upper()
        tenmh = self.tenmh_input.text().strip()
        sotclt = self.sotclt_spin.value()
        sotcth = self.sotcth_spin.value()
        try:
            if self._is_adding:
                self._service.create(mamh, tenmh, sotclt, sotcth)
                QMessageBox.information(self, "Thành công", f"Đã thêm môn học '{mamh}'.")
            else:
                if not self._current_mamh:
                    return
                self._service.update(self._current_mamh, tenmh, sotclt, sotcth)
                QMessageBox.information(self, "Thành công", f"Đã cập nhật môn học '{self._current_mamh}'.")
                mamh = self._current_mamh
        except (MonhocServiceError, PermissionError) as error:
            QMessageBox.warning(self, "Không thể lưu môn học", str(error))
            return
        self._load_monhocs(select_mamh=mamh)

    def _delete_selected(self) -> None:
        if not self._current_mamh:
            return
        mh = next((m for m in self._monhocs if m.mamh == self._current_mamh), None)
        if not mh:
            return
        answer = QMessageBox.question(
            self,
            "Xác nhận xóa môn học",
            f"Bạn có chắc chắn muốn xóa môn học '{mh.mamh} — {mh.tenmh}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.delete(mh.mamh)
            QMessageBox.information(self, "Thành công", f"Đã xóa môn học '{mh.mamh}'.")
        except (MonhocServiceError, PermissionError) as error:
            QMessageBox.warning(self, "Không thể xóa môn học", str(error))
            return
        self._load_monhocs()

