"""Admin SQL account list, creation and confirmed deletion."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.models.user import User
from app.services.account_service import AccountService, AccountServiceError
from app.ui.styles import DIALOG_STYLE


class AccountFormDialog(QDialog):
    def __init__(
        self,
        title: str,
        on_save: Callable[[dict[str, str | None]], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._on_save = on_save
        self.setWindowTitle(title)
        self.setMinimumWidth(430)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(12)

        self.password_input = QLineEdit()
        self.password_input.setMaxLength(128)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setObjectName("accountPasswordInput")
        form.addRow("Mật khẩu", self.password_input)
        self.password_input.setPlaceholderText(
            "Để trống để dùng mật khẩu mặc định; mật khẩu tự đặt phải đáp ứng SQL Server CHECK_POLICY"
        )
        self.staff_password_hint = QLabel(
            "Nếu không nhập mật khẩu, hệ thống sẽ dùng mật khẩu mặc định: Qldsv@123456."
        )
        self.staff_password_hint.setWordWrap(True)
        form.addRow(self.staff_password_hint)
        self.student_password_hint = QLabel("Mật khẩu mặc định: 123456 (SQL Server cấp)")
        form.addRow(self.student_password_hint)

        self.role_combo = QComboBox()
        self.role_combo.addItems(["Admin", "GiangVien", "SinhVien"])
        self.role_combo.setObjectName("accountRoleCombo")
        form.addRow("Vai trò", self.role_combo)

        self.masv_input = QLineEdit()
        self.masv_input.setMaxLength(10)
        self.masv_input.setObjectName("accountMasvInput")
        self.masv_input.textChanged.connect(
            lambda text: self._uppercase_identifier(self.masv_input, text)
        )
        self.masv_label = QLabel("MASV")
        form.addRow(self.masv_label, self.masv_input)

        self.magv_input = QLineEdit()
        self.magv_input.setMaxLength(10)
        self.magv_input.setObjectName("accountMagvInput")
        self.magv_input.textChanged.connect(
            lambda text: self._uppercase_identifier(self.magv_input, text)
        )
        self.magv_input.setPlaceholderText("MAGV đã có trong danh sách giảng viên")
        self.magv_label = QLabel("MAGV")
        form.addRow(self.magv_label, self.magv_input)

        buttons = QHBoxLayout()
        buttons.addStretch()
        save_button = QPushButton("Lưu")
        save_button.setObjectName("saveAccountButton")
        save_button.clicked.connect(self._save)
        cancel_button = QPushButton("Hủy")
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(save_button)
        buttons.addWidget(cancel_button)

        layout.addLayout(form)
        layout.addLayout(buttons)
        self.role_combo.currentTextChanged.connect(self._update_role_fields)
        self._update_role_fields(self.role_combo.currentText())

    @staticmethod
    def _uppercase_identifier(editor: QLineEdit, text: str) -> None:
        uppercase = text.upper()
        if uppercase == text:
            return
        cursor = editor.cursorPosition()
        editor.setText(uppercase)
        editor.setCursorPosition(min(cursor, len(uppercase)))

    def _update_role_fields(self, role: str) -> None:
        student = role == "SinhVien"
        self.masv_input.setEnabled(student)
        self.magv_input.setEnabled(not student)
        self.masv_input.setVisible(student)
        self.masv_label.setVisible(student)
        self.magv_input.setVisible(not student)
        self.magv_label.setVisible(not student)
        self.staff_password_hint.setVisible(not student)
        self.password_input.setEnabled(not student)
        self.student_password_hint.setVisible(student)
        if student:
            self.password_input.clear()
            self.magv_input.clear()
        else:
            self.masv_input.clear()

    def _save(self) -> None:
        values = {
            "role": self.role_combo.currentText(),
            "masv": self.masv_input.text(),
            "magv": self.magv_input.text(),
        }
        values["password"] = None if values["role"] == "SinhVien" else (self.password_input.text() or None)
        self.password_input.clear()

        try:
            self._on_save(values)
        except (AccountServiceError, PermissionError) as error:
            QMessageBox.warning(self, "Không thể lưu tài khoản", str(error))
            return
        self.accept()


class AccountManagementDialog(QDialog):
    HEADERS = (
        "Mã",
        "Họ và tên",
        "Vai trò",
        "Trạng thái",
    )
    ROLE_LABELS = {
        "Admin": "Admin",
        "GiangVien": "Giảng viên",
        "SinhVien": "Sinh viên",
    }

    def __init__(
        self,
        account_service: AccountService | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._service = account_service or AccountService()
        self._accounts: list[User] = []
        self.setWindowTitle("Quản lý tài khoản")
        self.resize(820, 500)
        self.setStyleSheet(DIALOG_STYLE)
        self._build_ui()
        self._load_accounts()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Danh sách tài khoản")
        heading.setStyleSheet("font-size: 19px; font-weight: 600; color: #173b63;")

        self.account_table = QTableWidget(0, len(self.HEADERS))
        self.account_table.setObjectName("accountTable")
        self.account_table.setHorizontalHeaderLabels(self.HEADERS)
        self.account_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.account_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.account_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.account_table.horizontalHeader().setStretchLastSection(True)
        self.account_table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        buttons = QHBoxLayout()
        self.add_button = QPushButton("Thêm tài khoản")
        self.add_button.setObjectName("addAccountButton")
        self.add_button.clicked.connect(self._add_account)
        self.delete_button = QPushButton("Xóa tài khoản")
        self.delete_button.setObjectName("deleteAccountButton")
        self.delete_button.clicked.connect(self._delete_account)
        close_button = QPushButton("Đóng")
        close_button.clicked.connect(self.accept)
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.delete_button)
        buttons.addStretch()
        buttons.addWidget(close_button)

        layout.addWidget(heading)
        layout.addWidget(self.account_table, 1)
        layout.addLayout(buttons)

    def _load_accounts(self) -> None:
        try:
            self._accounts = self._service.find_all_accounts()
        except (AccountServiceError, PermissionError) as error:
            QMessageBox.critical(self, "Lỗi tải tài khoản", str(error))
            self._accounts = []

        self.account_table.setRowCount(len(self._accounts))
        for row, account in enumerate(self._accounts):
            values = (
                (account.masv if account.role == "SinhVien" else account.magv) or account.username,
                account.full_name or "—",
                self.ROLE_LABELS.get(account.role, account.role),
                "Đang hoạt động" if account.active else "Đã khóa",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.account_table.setItem(row, column, item)
        self.account_table.resizeColumnsToContents()

    def _selected_account(self) -> User | None:
        row = self.account_table.currentRow()
        if row < 0 or row >= len(self._accounts):
            QMessageBox.information(self, "Chọn tài khoản", "Hãy chọn một tài khoản.")
            return None
        return self._accounts[row]

    def _add_account(self) -> None:
        def save(values: dict[str, str | None]) -> None:
            self._service.create_account(**values)

        dialog = AccountFormDialog("Thêm tài khoản", save, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_accounts()

    def _delete_account(self) -> None:
        account = self._selected_account()
        if account is None:
            return

        answer = QMessageBox.question(
            self,
            "Xác nhận xóa tài khoản",
            f"Bạn có chắc chắn muốn xóa SQL Login/User của {account.username}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.delete_account(account.username)
        except (AccountServiceError, PermissionError) as error:
            QMessageBox.warning(self, "Không thể xóa tài khoản", str(error))
            return
        self._load_accounts()
