"""Lecturer self-service dialogs: Own Profile, Assigned Classes/Subjects, Class Students."""

from datetime import date, datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.services.role_portal_service import RolePortalService, RolePortalServiceError
from app.ui.styles import DIALOG_STYLE


class LecturerProfileDialog(QDialog):
    def __init__(self, portal_service: RolePortalService | None = None, parent=None) -> None:
        super().__init__(parent)
        self._service = portal_service or RolePortalService()
        self.setWindowTitle("Hồ sơ cá nhân Giảng viên")
        self.setMinimumWidth(420)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        group = QGroupBox("Thông tin giảng viên")
        form = QFormLayout(group)

        try:
            profile = self._service.get_lecturer_profile()
        except (RolePortalServiceError, PermissionError) as error:
            QMessageBox.critical(self, "Lỗi tải hồ sơ", str(error))
            profile = None

        if profile:
            form.addRow("Mã giảng viên:", QLabel(profile["magv"]))
            form.addRow("Họ:", QLabel(profile["ho"]))
            form.addRow("Tên:", QLabel(profile["ten"]))
            form.addRow("Phái:", QLabel(profile["phai"]))
        else:
            form.addRow(QLabel("Không tìm thấy thông tin giảng viên."))

        layout.addWidget(group)
        buttons = QHBoxLayout()
        buttons.addStretch()
        close_btn = QPushButton("Đóng")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)


class LecturerAssignmentsDialog(QDialog):
    PC_HEADERS = ("Mã lớp", "Tên lớp", "Mã môn", "Tên môn học", "TCLT", "TCTH")
    SV_HEADERS = ("Mã SV", "Họ", "Tên", "Phái", "Ngày sinh", "Nơi sinh", "Địa chỉ")

    def __init__(self, portal_service: RolePortalService | None = None, parent=None) -> None:
        super().__init__(parent)
        self._service = portal_service or RolePortalService()
        self._assignments: list[dict] = []

        self.setWindowTitle("Phân công cá nhân & Sinh viên lớp đang dạy")
        self.resize(900, 600)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Danh sách lớp & môn được phân công (chọn một dòng để xem danh sách sinh viên):"))

        self.pc_table = QTableWidget(0, len(self.PC_HEADERS))
        self.pc_table.setObjectName("gvPhanCongTable")
        self.pc_table.setHorizontalHeaderLabels(self.PC_HEADERS)
        self.pc_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.pc_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.pc_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pc_table.horizontalHeader().setStretchLastSection(True)
        self.pc_table.itemSelectionChanged.connect(self._on_assignment_selected)
        layout.addWidget(self.pc_table, 1)

        self.sv_label = QLabel("Danh sách sinh viên lớp đang dạy:")
        layout.addWidget(self.sv_label)

        self.sv_table = QTableWidget(0, len(self.SV_HEADERS))
        self.sv_table.setObjectName("gvSinhVienTable")
        self.sv_table.setHorizontalHeaderLabels(self.SV_HEADERS)
        self.sv_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.sv_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.sv_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.sv_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.sv_table, 2)

        buttons = QHBoxLayout()
        buttons.addStretch()
        close_btn = QPushButton("Đóng")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        self._load_assignments()

    def _load_assignments(self) -> None:
        try:
            self._assignments = self._service.get_lecturer_assignments()
        except (RolePortalServiceError, PermissionError) as error:
            QMessageBox.critical(self, "Lỗi tải phân công", str(error))
            self._assignments = []

        self.pc_table.setRowCount(len(self._assignments))
        for row, pc in enumerate(self._assignments):
            vals = (
                pc["malop"],
                pc["tenlop"],
                pc["mamh"],
                pc["tenmh"],
                str(pc["sotclt"]),
                str(pc["sotcth"]),
            )
            for col, val in enumerate(vals):
                cell = QTableWidgetItem(val)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.pc_table.setItem(row, col, cell)
        self.pc_table.resizeColumnsToContents()
        if self._assignments:
            self.pc_table.selectRow(0)

    def _on_assignment_selected(self) -> None:
        row = self.pc_table.currentRow()
        if row < 0 or row >= len(self._assignments):
            self.sv_table.setRowCount(0)
            return
        malop = self._assignments[row]["malop"]
        tenlop = self._assignments[row]["tenlop"]
        self.sv_label.setText(f"Danh sách sinh viên đang học — Lớp {malop} ({tenlop}):")
        try:
            students = self._service.get_lecturer_class_students(malop)
        except (RolePortalServiceError, PermissionError) as error:
            QMessageBox.warning(self, "Lỗi tải sinh viên", str(error))
            students = []

        self.sv_table.setRowCount(len(students))
        for r_idx, sv in enumerate(students):
            ngaysinh_str = (
                sv["ngaysinh"].strftime("%d/%m/%Y")
                if isinstance(sv["ngaysinh"], (date, datetime))
                else ""
            )
            vals = (
                sv["masv"],
                sv["ho"],
                sv["ten"],
                sv["phai"],
                ngaysinh_str,
                sv["noisinh"],
                sv["diachi"],
            )
            for c_idx, val in enumerate(vals):
                cell = QTableWidgetItem(val)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.sv_table.setItem(r_idx, c_idx, cell)
        self.sv_table.resizeColumnsToContents()

