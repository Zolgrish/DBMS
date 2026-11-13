"""Student self-service dialogs: Own Profile/Class/Subjects and Own Grades."""

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


class StudentProfileDialog(QDialog):
    MH_HEADERS = ("Mã môn", "Tên môn học", "Số TC Lý thuyết", "Số TC Thực hành")

    def __init__(self, portal_service: RolePortalService | None = None, parent=None) -> None:
        super().__init__(parent)
        self._service = portal_service or RolePortalService()

        self.setWindowTitle("Hồ sơ bản thân, Lớp & Môn học")
        self.resize(720, 560)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)

        group = QGroupBox("Thông tin sinh viên & Lớp")
        form = QFormLayout(group)
        try:
            profile = self._service.get_student_profile_and_class()
        except (RolePortalServiceError, PermissionError) as error:
            QMessageBox.critical(self, "Lỗi tải hồ sơ", str(error))
            profile = None

        if profile:
            ngaysinh_str = (
                profile["ngaysinh"].strftime("%d/%m/%Y")
                if isinstance(profile["ngaysinh"], (date, datetime))
                else "—"
            )
            ho_ten = " ".join(p for p in (profile["ho"], profile["ten"]) if p).strip()
            form.addRow("Mã sinh viên:", QLabel(profile["masv"]))
            form.addRow("Họ và tên:", QLabel(ho_ten))
            form.addRow("Lớp:", QLabel(f"{profile['malop']} — {profile['tenlop']}"))
            form.addRow("Phái:", QLabel(profile["phai"]))
            form.addRow("Ngày sinh:", QLabel(ngaysinh_str))
            form.addRow("Nơi sinh:", QLabel(profile["noisinh"] or "—"))
            form.addRow("Địa chỉ:", QLabel(profile["diachi"] or "—"))
            form.addRow("Trạng thái:", QLabel("Đã nghỉ học" if profile["nghihoc"] else "Đang học"))
        else:
            form.addRow(QLabel("Không tìm thấy thông tin sinh viên."))
        layout.addWidget(group)

        layout.addWidget(QLabel("Danh sách môn học:"))
        self.mh_table = QTableWidget(0, len(self.MH_HEADERS))
        self.mh_table.setObjectName("svMonhocTable")
        self.mh_table.setHorizontalHeaderLabels(self.MH_HEADERS)
        self.mh_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.mh_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.mh_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.mh_table)

        try:
            subjects = self._service.get_student_subjects()
        except (RolePortalServiceError, PermissionError):
            subjects = []

        self.mh_table.setRowCount(len(subjects))
        for r_idx, mh in enumerate(subjects):
            for c_idx, val in enumerate((mh["mamh"], mh["tenmh"], str(mh["sotclt"]), str(mh["sotcth"]))):
                cell = QTableWidgetItem(val)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.mh_table.setItem(r_idx, c_idx, cell)
        self.mh_table.resizeColumnsToContents()

        buttons = QHBoxLayout()
        buttons.addStretch()
        close_btn = QPushButton("Đóng")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)


class StudentGradesDialog(QDialog):
    HEADERS = ("Mã môn học", "Tên môn học", "Lần thi", "Điểm")

    def __init__(self, portal_service: RolePortalService | None = None, parent=None) -> None:
        super().__init__(parent)
        self._service = portal_service or RolePortalService()

        self.setWindowTitle("Bảng điểm cá nhân")
        self.resize(680, 440)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Kết quả điểm thi các môn của bạn:"))

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setObjectName("svOwnGradesTable")
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        try:
            grades = self._service.get_student_own_grades()
        except (RolePortalServiceError, PermissionError) as error:
            QMessageBox.warning(self, "Lỗi tải điểm", str(error))
            grades = []

        self.table.setRowCount(len(grades))
        for r_idx, g in enumerate(grades):
            diem_str = "Vắng" if g["diem"] is None else f"{g['diem']:g}"
            for c_idx, val in enumerate((g["mamh"], g["tenmh"], str(g["lan"]), diem_str)):
                cell = QTableWidgetItem(val)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if c_idx >= 2:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(r_idx, c_idx, cell)
        self.table.resizeColumnsToContents()

        buttons = QHBoxLayout()
        buttons.addStretch()
        close_btn = QPushButton("Đóng")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

