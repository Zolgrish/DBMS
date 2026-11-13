"""Admin-only Teaching Assignment (PhanCong) management dialog."""

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

from app.services.lecturer_service import LecturerService, LecturerServiceError
from app.services.lop_service import LopService, LopServiceError
from app.services.monhoc_service import MonhocService, MonhocServiceError
from app.services.role_portal_service import RolePortalService, RolePortalServiceError
from app.ui.styles import DIALOG_STYLE


class PhanCongManagementDialog(QDialog):
    HEADERS = ("Mã GV", "Họ tên giảng viên", "Mã lớp", "Tên lớp", "Mã MH", "Tên môn học")

    def __init__(
        self,
        portal_service: RolePortalService | None = None,
        lecturer_service: LecturerService | None = None,
        lop_service: LopService | None = None,
        monhoc_service: MonhocService | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._service = portal_service or RolePortalService()
        self._lecturer_service = lecturer_service or LecturerService()
        self._lop_service = lop_service or LopService()
        self._monhoc_service = monhoc_service or MonhocService()
        self._items: list[dict] = []

        self.setWindowTitle("Quản lý Phân công giảng dạy")
        self.resize(900, 540)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)

        add_group = QGroupBox("Thêm phân công mới")
        add_layout = QHBoxLayout(add_group)

        add_layout.addWidget(QLabel("Giảng viên:"))
        self.gv_combo = QComboBox()
        self.gv_combo.setMinimumWidth(180)
        add_layout.addWidget(self.gv_combo)

        add_layout.addWidget(QLabel("Lớp:"))
        self.lop_combo = QComboBox()
        self.lop_combo.setMinimumWidth(150)
        add_layout.addWidget(self.lop_combo)

        add_layout.addWidget(QLabel("Môn học:"))
        self.mh_combo = QComboBox()
        self.mh_combo.setMinimumWidth(180)
        add_layout.addWidget(self.mh_combo)

        self.add_button = QPushButton("Thêm phân công")
        self.add_button.setObjectName("addPhanCongButton")
        self.add_button.clicked.connect(self._add_phancong)
        add_layout.addWidget(self.add_button)
        layout.addWidget(add_group)

        layout.addWidget(QLabel("Danh sách phân công hiện tại"))
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setObjectName("phanCongTable")
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        self.delete_button = QPushButton("Xóa phân công")
        self.delete_button.setObjectName("deletePhanCongButton")
        self.delete_button.clicked.connect(self._delete_selected)
        buttons.addWidget(self.delete_button)
        buttons.addStretch()
        close_button = QPushButton("Thoát")
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

        self._load_combos()
        self._load_phancong()

    def _load_combos(self) -> None:
        self.gv_combo.clear()
        self.lop_combo.clear()
        self.mh_combo.clear()
        try:
            for gv in self._lecturer_service.find_all_lecturers():
                name = " ".join(p for p in (gv.ho, gv.ten) if p).strip()
                self.gv_combo.addItem(f"{gv.magv} - {name}", gv.magv)
            for lop in self._lop_service.find_all():
                self.lop_combo.addItem(f"{lop.malop} - {lop.tenlop}", lop.malop)
            for mh in self._monhoc_service.find_all():
                self.mh_combo.addItem(f"{mh.mamh} - {mh.tenmh}", mh.mamh)
        except (LecturerServiceError, LopServiceError, MonhocServiceError, PermissionError) as error:
            QMessageBox.critical(self, "Lỗi tải dữ liệu", str(error))

    def _load_phancong(self) -> None:
        try:
            self._items = self._service.find_all_phancong()
        except (RolePortalServiceError, PermissionError) as error:
            QMessageBox.critical(self, "Lỗi tải phân công", str(error))
            self._items = []

        self.table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            values = (
                item["magv"],
                item["hoten_gv"],
                item["malop"],
                item["tenlop"],
                item["mamh"],
                item["tenmh"],
            )
            for col, val in enumerate(values):
                cell = QTableWidgetItem(val)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, cell)
        self.table.resizeColumnsToContents()

    def _add_phancong(self) -> None:
        magv = self.gv_combo.currentData() or ""
        malop = self.lop_combo.currentData() or ""
        mamh = self.mh_combo.currentData() or ""
        try:
            self._service.add_phancong(magv, malop, mamh)
        except (RolePortalServiceError, PermissionError) as error:
            QMessageBox.warning(self, "Không thể thêm phân công", str(error))
            return
        self._load_phancong()

    def _delete_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._items):
            QMessageBox.information(self, "Chọn phân công", "Hãy chọn một dòng phân công để xóa.")
            return
        item = self._items[row]
        answer = QMessageBox.question(
            self,
            "Xác nhận xóa phân công",
            f"Xóa phân công {item['magv']} dạy {item['mamh']} cho lớp {item['malop']}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.delete_phancong(item["magv"], item["malop"], item["mamh"])
        except (RolePortalServiceError, PermissionError) as error:
            QMessageBox.warning(self, "Không thể xóa phân công", str(error))
            return
        self._load_phancong()

