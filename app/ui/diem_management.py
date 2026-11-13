"""Grading (Nhap diem) dialog for Admin and Lecturer (Lan 1 & Lan 2)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.models.diem import DiemSinhvienRow
from app.services.diem_service import DiemService, DiemServiceError
from app.ui.phancong_management import PhanCongManagementDialog
from app.ui.styles import DIALOG_STYLE
from app.utils import session


class DiemManagementDialog(QDialog):
    HEADERS = ("Mã SV", "Họ và tên", "Điểm")

    def __init__(self, diem_service: DiemService | None = None, parent=None) -> None:
        super().__init__(parent)
        self._service = diem_service or DiemService()
        self._rows: list[DiemSinhvienRow] = []
        self._active_malop: str | None = None
        self._active_mamh: str | None = None
        self._active_lan: int | None = None

        self.setWindowTitle("Nhập điểm sinh viên")
        self.resize(820, 560)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)

        # Selection Bar: Lớp -> Môn học -> Lần thi -> Bắt đầu
        filter_group = QGroupBox("Thông tin môn thi")
        filter_layout = QHBoxLayout(filter_group)

        filter_layout.addWidget(QLabel("Lớp:"))
        self.lop_combo = QComboBox()
        self.lop_combo.setObjectName("diemLopCombo")
        self.lop_combo.setMinimumWidth(180)
        self.lop_combo.currentIndexChanged.connect(self._on_lop_changed)
        filter_layout.addWidget(self.lop_combo)

        filter_layout.addSpacing(10)
        filter_layout.addWidget(QLabel("Môn học:"))
        self.monhoc_combo = QComboBox()
        self.monhoc_combo.setObjectName("diemMonhocCombo")
        self.monhoc_combo.setMinimumWidth(200)
        self.monhoc_combo.currentIndexChanged.connect(self._update_start_button)
        filter_layout.addWidget(self.monhoc_combo)

        filter_layout.addSpacing(10)
        filter_layout.addWidget(QLabel("Lần thi:"))
        self.lan_combo = QComboBox()
        self.lan_combo.setObjectName("diemLanCombo")
        self.lan_combo.addItem("Lần 1", 1)
        self.lan_combo.addItem("Lần 2", 2)
        self.lan_combo.currentIndexChanged.connect(self._update_start_button)
        filter_layout.addWidget(self.lan_combo)

        filter_layout.addSpacing(12)
        self.start_button = QPushButton("Bắt đầu")
        self.start_button.setObjectName("diemStartButton")
        self.start_button.clicked.connect(self._start_grading)
        filter_layout.addWidget(self.start_button)

        layout.addWidget(filter_group)

        hint = QLabel(
            "Lưu ý: Chỉ hiển thị sinh viên còn đang học. "
            "Nhập điểm từ 0 đến 10; để trống ô Điểm nếu sinh viên vắng thi (NULL)."
        )
        hint.setStyleSheet("color: #475569; font-size: 12px;")
        layout.addWidget(hint)

        # Grading Grid
        self.diem_table = QTableWidget(0, len(self.HEADERS))
        self.diem_table.setObjectName("diemTable")
        self.diem_table.setHorizontalHeaderLabels(self.HEADERS)
        self.diem_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.diem_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.diem_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.diem_table)

        # Action Buttons
        buttons = QHBoxLayout()
        self.save_button = QPushButton("Ghi điểm")
        self.delete_button = QPushButton("Xóa điểm")
        self.undo_button = QPushButton("Phục hồi")
        self.phancong_button = QPushButton("Quản lý Phân công...")
        self.close_button = QPushButton("Thoát")

        self.save_button.setObjectName("saveDiemButton")
        self.delete_button.setObjectName("deleteDiemButton")
        self.undo_button.setObjectName("undoDiemButton")
        self.phancong_button.setObjectName("openPhanCongButton")
        self.close_button.setObjectName("closeDiemButton")

        self.save_button.clicked.connect(self._save_grades)
        self.delete_button.clicked.connect(self._delete_selected_grade)
        self.undo_button.clicked.connect(self._reload_grid)
        self.phancong_button.clicked.connect(self._open_phancong)
        self.close_button.clicked.connect(self.accept)

        self.save_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.undo_button.setEnabled(False)

        is_admin = bool(session.current_user and session.current_user.get("role") == "Admin")
        self.delete_button.setVisible(is_admin)
        self.phancong_button.setVisible(is_admin)

        buttons.addWidget(self.save_button)
        buttons.addWidget(self.delete_button)
        buttons.addWidget(self.undo_button)
        buttons.addWidget(self.phancong_button)
        buttons.addStretch()
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

        self._load_lops()

    def _load_lops(self) -> None:
        try:
            lops = self._service.get_lops_for_grading()
        except (DiemServiceError, PermissionError) as error:
            QMessageBox.critical(self, "Lỗi tải danh sách lớp", str(error))
            lops = []

        self.lop_combo.blockSignals(True)
        self.lop_combo.clear()
        for lop in lops:
            self.lop_combo.addItem(f"{lop.malop} - {lop.tenlop}", lop.malop)
        self.lop_combo.blockSignals(False)

        self._on_lop_changed()

    def _on_lop_changed(self) -> None:
        malop = self.lop_combo.currentData()
        self.monhoc_combo.blockSignals(True)
        self.monhoc_combo.clear()
        if malop:
            try:
                monhocs = self._service.get_monhocs_for_grading(malop)
            except (DiemServiceError, PermissionError) as error:
                QMessageBox.critical(self, "Lỗi tải môn học", str(error))
                monhocs = []
            for mh in monhocs:
                self.monhoc_combo.addItem(f"{mh.mamh} - {mh.tenmh}", mh.mamh)
        self.monhoc_combo.blockSignals(False)
        self._clear_grid()
        self._update_start_button()

    def _update_start_button(self) -> None:
        ready = (
            self.lop_combo.currentData() is not None
            and self.monhoc_combo.currentData() is not None
            and self.lan_combo.currentData() in (1, 2)
        )
        self.start_button.setEnabled(ready)

    def _clear_grid(self) -> None:
        self._rows = []
        self._active_malop = None
        self._active_mamh = None
        self._active_lan = None
        self.diem_table.setRowCount(0)
        self.save_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.undo_button.setEnabled(False)

    def _start_grading(self) -> None:
        malop = self.lop_combo.currentData()
        mamh = self.monhoc_combo.currentData()
        lan = self.lan_combo.currentData()
        if not malop or not mamh or lan not in (1, 2):
            return

        self._load_grading_grid(malop, mamh, lan)

    def _reload_grid(self) -> None:
        if self._active_malop and self._active_mamh and self._active_lan in (1, 2):
            self._load_grading_grid(self._active_malop, self._active_mamh, self._active_lan)

    def _load_grading_grid(self, malop: str, mamh: str, lan: int) -> None:
        try:
            rows = self._service.get_grading_list(malop, mamh, lan)
        except (DiemServiceError, PermissionError) as error:
            QMessageBox.warning(self, "Không thể mở danh sách nhập điểm", str(error))
            self._clear_grid()
            return

        if not rows:
            msg = (
                "Không có sinh viên nào cần nhập điểm lần 2 (tất cả sinh viên đã đạt >= 5)."
                if lan == 2
                else "Lớp này hiện chưa có sinh viên đang học."
            )
            QMessageBox.information(self, "Thông báo", msg)
            self._clear_grid()
            return

        self._active_malop = malop
        self._active_mamh = mamh
        self._active_lan = lan
        self._rows = rows

        self.diem_table.setRowCount(len(rows))
        for row_idx, sv in enumerate(rows):
            masv_item = QTableWidgetItem(sv.masv)
            masv_item.setFlags(masv_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.diem_table.setItem(row_idx, 0, masv_item)

            name_item = QTableWidgetItem(sv.ho_ten)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.diem_table.setItem(row_idx, 1, name_item)

            diem_text = "" if sv.diem is None else f"{sv.diem:g}"
            diem_item = QTableWidgetItem(diem_text)
            diem_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.diem_table.setItem(row_idx, 2, diem_item)

        self.diem_table.resizeColumnsToContents()
        self.save_button.setEnabled(True)
        self.delete_button.setEnabled(True)
        self.undo_button.setEnabled(True)

    def _save_grades(self) -> None:
        if not self._active_mamh or self._active_lan not in (1, 2) or not self._rows:
            return

        items: list[tuple[str, str]] = []
        for row_idx, sv in enumerate(self._rows):
            cell = self.diem_table.item(row_idx, 2)
            raw_text = cell.text() if cell is not None else ""
            items.append((sv.masv, raw_text))

        try:
            self._service.save_grades(self._active_mamh, self._active_lan, items)
        except (DiemServiceError, PermissionError) as error:
            QMessageBox.warning(self, "Lỗi nhập điểm", str(error))
            return

        QMessageBox.information(
            self,
            "Thành công",
            f"Đã lưu điểm lần {self._active_lan} cho lớp {self._active_malop} - môn {self._active_mamh}.",
        )
        self._reload_grid()

    def _delete_selected_grade(self) -> None:
        if not self._active_mamh or self._active_lan not in (1, 2) or not self._rows:
            return
        row_idx = self.diem_table.currentRow()
        if row_idx < 0 or row_idx >= len(self._rows):
            QMessageBox.information(self, "Chọn sinh viên", "Hãy chọn một dòng sinh viên cần xóa điểm.")
            return
        sv = self._rows[row_idx]
        answer = QMessageBox.question(
            self,
            "Xác nhận xóa điểm",
            f"Xóa điểm lần {self._active_lan} môn {self._active_mamh} của sinh viên {sv.masv} — {sv.ho_ten}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.delete_grade(sv.masv, self._active_mamh, self._active_lan)
        except (DiemServiceError, PermissionError) as error:
            QMessageBox.warning(self, "Không thể xóa điểm", str(error))
            return
        QMessageBox.information(self, "Thành công", f"Đã xóa điểm của sinh viên {sv.masv}.")
        self._reload_grid()

    def _open_phancong(self) -> None:
        dialog = PhanCongManagementDialog(parent=self)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

