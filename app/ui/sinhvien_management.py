"""Admin Student (Sinhvien) SubForm management dialog filtered by Class (Lop)."""

from datetime import date, datetime

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
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
from app.models.sinhvien import Sinhvien
from app.services.lop_service import LopService, LopServiceError
from app.services.sinhvien_service import SinhvienService, SinhvienServiceError
from app.ui.lop_management import LopManagementDialog
from app.ui.styles import DIALOG_STYLE


class SinhvienManagementDialog(QDialog):
    HEADERS = ("Mã SV", "Họ", "Tên", "Phái", "Ngày sinh", "Nơi sinh", "Địa chỉ", "Nghỉ học")

    def __init__(
        self,
        sinhvien_service: SinhvienService | None = None,
        lop_service: LopService | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._service = sinhvien_service or SinhvienService()
        self._lop_service = lop_service or LopService()
        self._lops: list[Lop] = []
        self._students: list[Sinhvien] = []
        self._is_adding = False
        self._current_masv: str | None = None

        self.setWindowTitle("Quản lý Sinh viên")
        self.resize(1020, 660)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)

        # Top filter bar: Class ComboBox + Search input
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Chọn lớp:"))
        self.lop_combo = QComboBox()
        self.lop_combo.setObjectName("svLopFilterCombo")
        self.lop_combo.setMinimumWidth(240)
        self.lop_combo.currentIndexChanged.connect(self._on_lop_changed)
        top_bar.addWidget(self.lop_combo)

        self.manage_lop_btn = QPushButton("Quản lý Lớp...")
        self.manage_lop_btn.setObjectName("manageLopFromSvButton")
        self.manage_lop_btn.clicked.connect(self._open_lop_management)
        top_bar.addWidget(self.manage_lop_btn)

        top_bar.addSpacing(20)
        top_bar.addWidget(QLabel("Tìm kiếm (MASV / Họ tên):"))
        self.search_input = QLineEdit()
        self.search_input.setObjectName("svSearchInput")
        self.search_input.setPlaceholderText("Nhập mã SV hoặc họ tên để lọc...")
        self.search_input.textChanged.connect(self._load_students)
        top_bar.addWidget(self.search_input)
        layout.addLayout(top_bar)

        # Student table (SubForm Grid)
        self.sv_table = QTableWidget(0, len(self.HEADERS))
        self.sv_table.setObjectName("svTable")
        self.sv_table.setHorizontalHeaderLabels(self.HEADERS)
        self.sv_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.sv_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.sv_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.sv_table.horizontalHeader().setStretchLastSection(True)
        self.sv_table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.sv_table)

        # Detail Form
        form_group = QGroupBox("Thông tin sinh viên")
        form_outer = QHBoxLayout(form_group)
        left_form = QFormLayout()
        right_form = QFormLayout()

        self.masv_input = QLineEdit()
        self.masv_input.setObjectName("svMasvInput")
        self.masv_input.setMaxLength(10)
        self.masv_input.setPlaceholderText("10 ký tự (VD: SV00000010)")
        self.masv_input.textChanged.connect(self._on_masv_changed)

        self.ho_input = QLineEdit()
        self.ho_input.setObjectName("svHoInput")
        self.ho_input.setMaxLength(40)
        self.ho_input.textChanged.connect(self._update_button_states)

        self.ten_input = QLineEdit()
        self.ten_input.setObjectName("svTenInput")
        self.ten_input.setMaxLength(10)
        self.ten_input.textChanged.connect(self._update_button_states)

        self.phai_combo = QComboBox()
        self.phai_combo.setObjectName("svPhaiCombo")
        self.phai_combo.addItem("Nam", True)
        self.phai_combo.addItem("Nữ", False)
        self.phai_combo.currentIndexChanged.connect(self._update_button_states)

        self.ngaysinh_input = QDateEdit()
        self.ngaysinh_input.setObjectName("svNgaysinhInput")
        self.ngaysinh_input.setCalendarPopup(True)
        self.ngaysinh_input.setDisplayFormat("dd/MM/yyyy")
        self.ngaysinh_input.setDate(QDate(2004, 1, 1))
        self.ngaysinh_input.setMaximumDate(QDate.currentDate())
        self.ngaysinh_input.setMinimumDate(QDate(1900, 1, 1))
        self.ngaysinh_input.dateChanged.connect(self._update_button_states)

        self.form_lop_combo = QComboBox()
        self.form_lop_combo.setObjectName("svFormLopCombo")
        self.form_lop_combo.currentIndexChanged.connect(self._update_button_states)

        left_form.addRow("Mã SV (*)", self.masv_input)
        left_form.addRow("Họ (*)", self.ho_input)
        left_form.addRow("Tên (*)", self.ten_input)
        left_form.addRow("Lớp (*)", self.form_lop_combo)
        left_form.addRow("Phái", self.phai_combo)
        left_form.addRow("Ngày sinh", self.ngaysinh_input)

        self.noisinh_input = QLineEdit()
        self.noisinh_input.setObjectName("svNoisinhInput")
        self.noisinh_input.setMaxLength(40)
        self.noisinh_input.textChanged.connect(self._update_button_states)

        self.diachi_input = QLineEdit()
        self.diachi_input.setObjectName("svDiachiInput")
        self.diachi_input.setMaxLength(80)
        self.diachi_input.textChanged.connect(self._update_button_states)

        self.ghichu_input = QLineEdit()
        self.ghichu_input.setObjectName("svGhichuInput")
        self.ghichu_input.textChanged.connect(self._update_button_states)

        hinh_row = QHBoxLayout()
        self.hinh_input = QLineEdit()
        self.hinh_input.setObjectName("svHinhInput")
        self.hinh_input.setMaxLength(1000)
        self.hinh_input.textChanged.connect(self._update_button_states)
        self.browse_hinh_btn = QPushButton("Chọn ảnh...")
        self.browse_hinh_btn.clicked.connect(self._browse_image)
        hinh_row.addWidget(self.hinh_input)
        hinh_row.addWidget(self.browse_hinh_btn)

        self.nghihoc_check = QCheckBox("Đã nghỉ học")
        self.nghihoc_check.setObjectName("svNghihocCheck")
        self.nghihoc_check.stateChanged.connect(self._update_button_states)

        right_form.addRow("Nơi sinh", self.noisinh_input)
        right_form.addRow("Địa chỉ", self.diachi_input)
        right_form.addRow("Ghi chú", self.ghichu_input)
        right_form.addRow("Hình ảnh", hinh_row)
        right_form.addRow("Trạng thái", self.nghihoc_check)

        form_outer.addLayout(left_form, 1)
        form_outer.addSpacing(16)
        form_outer.addLayout(right_form, 1)
        layout.addWidget(form_group)

        # Action Buttons
        buttons = QHBoxLayout()
        self.add_button = QPushButton("Thêm")
        self.delete_button = QPushButton("Xóa")
        self.save_button = QPushButton("Ghi")
        self.undo_button = QPushButton("Phục hồi")
        self.close_button = QPushButton("Thoát")

        self.add_button.setObjectName("addSvButton")
        self.delete_button.setObjectName("deleteSvButton")
        self.save_button.setObjectName("saveSvButton")
        self.undo_button.setObjectName("undoSvButton")
        self.close_button.setObjectName("closeSvButton")

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

    def _on_masv_changed(self, text: str) -> None:
        uppercase = text.upper()
        if uppercase != text:
            cursor = self.masv_input.cursorPosition()
            self.masv_input.setText(uppercase)
            self.masv_input.setCursorPosition(min(cursor, len(uppercase)))
        self._update_button_states()

    def _open_lop_management(self) -> None:
        current_malop = self.lop_combo.currentData()
        dialog = LopManagementDialog(lop_service=self._lop_service, parent=self)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()
        self._load_lops()
        if current_malop:
            idx = self.lop_combo.findData(current_malop)
            if idx >= 0:
                self.lop_combo.setCurrentIndex(idx)

    def _browse_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn ảnh sinh viên",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)",
        )
        if file_path:
            self.hinh_input.setText(file_path)

    def _load_lops(self) -> None:
        try:
            self._lops = self._lop_service.find_all()
        except (LopServiceError, PermissionError) as error:
            QMessageBox.critical(self, "Lỗi tải danh sách lớp", str(error))
            self._lops = []

        self.lop_combo.blockSignals(True)
        self.form_lop_combo.blockSignals(True)
        self.lop_combo.clear()
        self.form_lop_combo.clear()
        for lop in self._lops:
            label = f"{lop.malop} - {lop.tenlop}"
            self.lop_combo.addItem(label, lop.malop)
            self.form_lop_combo.addItem(label, lop.malop)
        self.lop_combo.blockSignals(False)
        self.form_lop_combo.blockSignals(False)

        self._load_students()

    def _on_lop_changed(self) -> None:
        self._is_adding = False
        self._load_students()

    def _load_students(self, select_masv: str | None = None) -> None:
        malop = self.lop_combo.currentData()
        if not malop:
            self._students = []
            self.sv_table.setRowCount(0)
            self._clear_form()
            self._update_button_states()
            return

        keyword = self.search_input.text().strip()
        try:
            self._students = self._service.find_by_lop(malop, keyword=keyword)
        except (SinhvienServiceError, PermissionError) as error:
            QMessageBox.critical(self, "Lỗi tải danh sách sinh viên", str(error))
            self._students = []

        self.sv_table.blockSignals(True)
        self.sv_table.setRowCount(len(self._students))
        target_row = 0 if self._students else -1
        for row, sv in enumerate(self._students):
            if select_masv and sv.masv == select_masv:
                target_row = row
            ngaysinh_str = (
                sv.ngaysinh.strftime("%d/%m/%Y")
                if isinstance(sv.ngaysinh, (date, datetime))
                else ""
            )
            values = (
                sv.masv,
                sv.ho or "",
                sv.ten or "",
                "Nam" if sv.phai else "Nữ",
                ngaysinh_str,
                sv.noisinh or "",
                sv.diachi or "",
                "Có" if sv.nghihoc else "Không",
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.sv_table.setItem(row, col, item)
        self.sv_table.resizeColumnsToContents()
        self.sv_table.blockSignals(False)

        self._is_adding = False
        if target_row >= 0:
            self.sv_table.selectRow(target_row)
            self._populate_from_row(target_row)
        else:
            self._clear_form()
        self._update_button_states()

    def _set_form_editable(self, editable: bool, masv_editable: bool = False) -> None:
        self.masv_input.setReadOnly(not masv_editable)
        self.ho_input.setReadOnly(not editable)
        self.ten_input.setReadOnly(not editable)
        self.form_lop_combo.setEnabled(editable)
        self.phai_combo.setEnabled(editable)
        self.ngaysinh_input.setEnabled(editable)
        self.noisinh_input.setReadOnly(not editable)
        self.diachi_input.setReadOnly(not editable)
        self.ghichu_input.setReadOnly(not editable)
        self.hinh_input.setReadOnly(not editable)
        self.browse_hinh_btn.setEnabled(editable)
        self.nghihoc_check.setEnabled(editable)

    def _populate_from_row(self, row: int) -> None:
        if 0 <= row < len(self._students):
            sv = self._students[row]
            self._current_masv = sv.masv
            self.masv_input.blockSignals(True)
            self.masv_input.setText(sv.masv)
            self.masv_input.blockSignals(False)

            self.ho_input.setText(sv.ho or "")
            self.ten_input.setText(sv.ten or "")
            lop_idx = self.form_lop_combo.findData(sv.malop)
            if lop_idx >= 0:
                self.form_lop_combo.setCurrentIndex(lop_idx)
            self.phai_combo.setCurrentIndex(0 if sv.phai else 1)

            if isinstance(sv.ngaysinh, (date, datetime)):
                self.ngaysinh_input.setDate(
                    QDate(sv.ngaysinh.year, sv.ngaysinh.month, sv.ngaysinh.day)
                )
            else:
                self.ngaysinh_input.setDate(QDate(2004, 1, 1))

            self.noisinh_input.setText(sv.noisinh or "")
            self.diachi_input.setText(sv.diachi or "")
            self.ghichu_input.setText(sv.ghichu or "")
            self.hinh_input.setText(sv.hinh or "")
            self.nghihoc_check.setChecked(sv.nghihoc)
            self._set_form_editable(True, masv_editable=False)
        else:
            self._clear_form()

    def _clear_form(self) -> None:
        self._current_masv = None
        self.masv_input.clear()
        self.ho_input.clear()
        self.ten_input.clear()
        self.noisinh_input.clear()
        self.diachi_input.clear()
        self.ghichu_input.clear()
        self.hinh_input.clear()
        self.phai_combo.setCurrentIndex(0)
        self.ngaysinh_input.setDate(QDate(2004, 1, 1))
        self.nghihoc_check.setChecked(False)
        self._set_form_editable(False, masv_editable=False)

    def _on_selection_changed(self) -> None:
        if self._is_adding:
            return
        self._populate_from_row(self.sv_table.currentRow())
        self._update_button_states()

    def _is_dirty(self) -> bool:
        if self._is_adding:
            return True
        if self._current_masv is None:
            return False
        sv = next((s for s in self._students if s.masv == self._current_masv), None)
        if sv is None:
            return False
        qdate = self.ngaysinh_input.date()
        cur_date = date(qdate.year(), qdate.month(), qdate.day())
        sv_date = (
            sv.ngaysinh.date()
            if isinstance(sv.ngaysinh, datetime)
            else sv.ngaysinh
        )
        return (
            self.ho_input.text().strip() != (sv.ho or "")
            or self.ten_input.text().strip() != (sv.ten or "")
            or self.form_lop_combo.currentData() != sv.malop
            or bool(self.phai_combo.currentData()) != sv.phai
            or cur_date != sv_date
            or self.noisinh_input.text().strip() != (sv.noisinh or "")
            or self.diachi_input.text().strip() != (sv.diachi or "")
            or self.ghichu_input.text().strip() != (sv.ghichu or "")
            or self.hinh_input.text().strip() != (sv.hinh or "")
            or self.nghihoc_check.isChecked() != sv.nghihoc
        )

    def _update_button_states(self) -> None:
        has_lop = self.lop_combo.currentData() is not None
        has_selection = self._current_masv is not None
        dirty = self._is_dirty()

        self.add_button.setEnabled(has_lop and not self._is_adding)
        self.delete_button.setEnabled(not self._is_adding and has_selection)
        self.save_button.setEnabled(self._is_adding or dirty)
        self.undo_button.setEnabled(self._is_adding or dirty)

    def _start_add(self) -> None:
        if not self.lop_combo.currentData():
            QMessageBox.warning(self, "Chưa chọn lớp", "Vui lòng chọn một lớp trước khi thêm sinh viên.")
            return
        self._is_adding = True
        self._current_masv = None
        self.sv_table.clearSelection()
        self.masv_input.clear()
        self.ho_input.clear()
        self.ten_input.clear()
        self.noisinh_input.clear()
        self.diachi_input.clear()
        self.ghichu_input.clear()
        self.hinh_input.clear()
        self.phai_combo.setCurrentIndex(0)
        self.ngaysinh_input.setDate(QDate(2004, 1, 1))
        self.nghihoc_check.setChecked(False)
        lop_idx = self.form_lop_combo.findData(self.lop_combo.currentData())
        if lop_idx >= 0:
            self.form_lop_combo.setCurrentIndex(lop_idx)
        self._set_form_editable(True, masv_editable=True)
        self.masv_input.setFocus()
        self._update_button_states()

    def _undo(self) -> None:
        if self._is_adding:
            self._is_adding = False
            if self._students:
                self.sv_table.selectRow(0)
                self._populate_from_row(0)
            else:
                self._clear_form()
        else:
            self._populate_from_row(self.sv_table.currentRow())
        self._update_button_states()

    def _save(self) -> None:
        masv = self.masv_input.text().strip().upper()
        ho = self.ho_input.text().strip()
        ten = self.ten_input.text().strip()
        malop = self.form_lop_combo.currentData() or ""
        phai = bool(self.phai_combo.currentData())
        qdate = self.ngaysinh_input.date()
        ngaysinh = date(qdate.year(), qdate.month(), qdate.day())
        noisinh = self.noisinh_input.text().strip()
        diachi = self.diachi_input.text().strip()
        ghichu = self.ghichu_input.text().strip()
        hinh = self.hinh_input.text().strip()
        nghihoc = self.nghihoc_check.isChecked()

        try:
            if self._is_adding:
                warning = self._service.create(
                    masv=masv,
                    ho=ho,
                    ten=ten,
                    malop=malop,
                    phai=phai,
                    ngaysinh=ngaysinh,
                    noisinh=noisinh,
                    diachi=diachi,
                    ghichu=ghichu,
                    nghihoc=nghihoc,
                    hinh=hinh,
                )
                if warning:
                    QMessageBox.warning(self, "Lưu ý tài khoản tự động", warning)
                else:
                    QMessageBox.information(
                        self,
                        "Thành công",
                        f"Đã thêm sinh viên '{masv}' và tự động tạo tài khoản (Mật khẩu mặc định: 123456).",
                    )
            else:
                if not self._current_masv:
                    return
                masv = self._current_masv
                self._service.update(
                    masv=masv,
                    ho=ho,
                    ten=ten,
                    malop=malop,
                    phai=phai,
                    ngaysinh=ngaysinh,
                    noisinh=noisinh,
                    diachi=diachi,
                    ghichu=ghichu,
                    nghihoc=nghihoc,
                    hinh=hinh,
                )
                QMessageBox.information(self, "Thành công", f"Đã cập nhật sinh viên '{masv}'.")
        except (SinhvienServiceError, PermissionError) as error:
            QMessageBox.warning(self, "Không thể lưu sinh viên", str(error))
            return

        # Sync top filter if class was changed during edit
        filter_idx = self.lop_combo.findData(malop)
        if filter_idx >= 0 and self.lop_combo.currentIndex() != filter_idx:
            self.lop_combo.setCurrentIndex(filter_idx)
        self._load_students(select_masv=masv)

    def _delete_selected(self) -> None:
        if not self._current_masv:
            return
        sv = next((s for s in self._students if s.masv == self._current_masv), None)
        if not sv:
            return
        answer = QMessageBox.question(
            self,
            "Xác nhận xóa sinh viên",
            f"Bạn có chắc chắn muốn xóa sinh viên '{sv.masv} — {sv.ho_ten}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.delete(sv.masv)
            QMessageBox.information(self, "Thành công", f"Đã xóa sinh viên '{sv.masv}'.")
        except (SinhvienServiceError, PermissionError) as error:
            QMessageBox.warning(self, "Không thể xóa sinh viên", str(error))
            return
        self._load_students()
