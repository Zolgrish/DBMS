"""Admin account list and account create/edit/status actions."""

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
        on_save: Callable[[dict[str, str]], None],
        account: User | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._on_save = on_save
        self._is_create = account is None
        self.setWindowTitle(title)
        self.setMinimumWidth(430)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(12)

        self.username_input = QLineEdit(account.username if account else "")
        self.username_input.setMaxLength(50)
        self.username_input.setObjectName("accountUsernameInput")
        self.username_input.setEnabled(self._is_create)
        form.addRow("Username", self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setMaxLength(255)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setObjectName("accountPasswordInput")
        self.password_input.setVisible(self._is_create)
        if self._is_create:
            form.addRow("Mật khẩu", self.password_input)

        self.role_combo = QComboBox()
        self.role_combo.addItems(["Admin", "SinhVien", "GiangVien"])
        self.role_combo.setObjectName("accountRoleCombo")
        if account:
            self.role_combo.setCurrentText(account.role)
        form.addRow("Vai trò", self.role_combo)

        self.masv_input = QLineEdit(account.masv or "" if account else "")
        self.masv_input.setMaxLength(10)
        self.masv_input.setObjectName("accountMasvInput")
        form.addRow("MASV", self.masv_input)

        self.magv_input = QLineEdit(account.magv or "" if account else "")
        self.magv_input.setMaxLength(10)
        self.magv_input.setObjectName("accountMagvInput")
        form.addRow("MAGV", self.magv_input)

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

    def _update_role_fields(self, role: str) -> None:
        self.masv_input.setEnabled(role == "SinhVien")
        self.magv_input.setEnabled(role == "GiangVien")
        if role != "SinhVien":
            self.masv_input.clear()
        if role != "GiangVien":
            self.magv_input.clear()

    def _save(self) -> None:
        values = {
            "username": self.username_input.text(),
            "role": self.role_combo.currentText(),
            "masv": self.masv_input.text(),
            "magv": self.magv_input.text(),
        }
        if self._is_create:
            values["password"] = self.password_input.text()

        try:
            self._on_save(values)
        except (AccountServiceError, PermissionError) as error:
            QMessageBox.warning(self, "Không thể lưu tài khoản", str(error))
            return
        self.accept()


class AccountManagementDialog(QDialog):
    HEADERS = ("Username", "Role", "MASV", "MAGV", "Status")

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
        self.edit_button = QPushButton("Sửa")
        self.edit_button.setObjectName("editAccountButton")
        self.edit_button.clicked.connect(self._edit_account)
        self.toggle_button = QPushButton("Khóa/Mở khóa")
        self.toggle_button.setObjectName("toggleAccountButton")
        self.toggle_button.clicked.connect(self._toggle_account_status)
        close_button = QPushButton("Đóng")
        close_button.clicked.connect(self.accept)
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.edit_button)
        buttons.addWidget(self.toggle_button)
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
                account.username,
                account.role,
                account.masv or "",
                account.magv or "",
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
        def save(values: dict[str, str]) -> None:
            self._service.create_account(**values)

        dialog = AccountFormDialog("Thêm tài khoản", save, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_accounts()

    def _edit_account(self) -> None:
        account = self._selected_account()
        if account is None:
            return

        def save(values: dict[str, str]) -> None:
            self._service.update_account(**values)

        dialog = AccountFormDialog("Sửa tài khoản", save, account, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_accounts()

    def _toggle_account_status(self) -> None:
        account = self._selected_account()
        if account is None:
            return
        try:
            self._service.update_account_status(account.username, not account.active)
        except (AccountServiceError, PermissionError) as error:
            QMessageBox.warning(self, "Không thể cập nhật tài khoản", str(error))
            return
        self._load_accounts()
