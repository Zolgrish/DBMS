"""Password-change form for the currently authenticated user."""

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.services.change_password_service import (
    ChangePasswordError,
    ChangePasswordService,
)
from app.ui.styles import DIALOG_STYLE
from app.utils import session


class ChangePasswordDialog(QDialog):
    def __init__(
        self,
        password_service: ChangePasswordService | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._service = password_service or ChangePasswordService()
        self.setWindowTitle("Đổi mật khẩu")
        self.setMinimumWidth(430)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        username = (session.current_user or {}).get("username", "")
        layout.addWidget(QLabel(f"Tài khoản: {username}"))

        form = QFormLayout()
        form.setSpacing(12)
        self.current_password_input = self._password_input("currentPasswordInput")
        self.new_password_input = self._password_input("newPasswordInput")
        self.confirm_password_input = self._password_input("confirmPasswordInput")
        form.addRow("Mật khẩu hiện tại", self.current_password_input)
        form.addRow("Mật khẩu mới", self.new_password_input)
        form.addRow("Xác nhận mật khẩu mới", self.confirm_password_input)

        buttons = QHBoxLayout()
        buttons.addStretch()
        change_button = QPushButton("Đổi mật khẩu")
        change_button.setObjectName("changePasswordButton")
        change_button.clicked.connect(self._change_password)
        cancel_button = QPushButton("Hủy")
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(change_button)
        buttons.addWidget(cancel_button)

        layout.addLayout(form)
        layout.addLayout(buttons)

    @staticmethod
    def _password_input(object_name: str) -> QLineEdit:
        field = QLineEdit()
        field.setMaxLength(255)
        field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setObjectName(object_name)
        return field

    def _change_password(self) -> None:
        try:
            self._service.change_password(
                self.current_password_input.text(),
                self.new_password_input.text(),
                self.confirm_password_input.text(),
            )
        except ChangePasswordError as error:
            QMessageBox.warning(self, "Không thể đổi mật khẩu", str(error))
            return

        self.current_password_input.clear()
        self.new_password_input.clear()
        self.confirm_password_input.clear()
        QMessageBox.information(self, "Đổi mật khẩu", "Đổi mật khẩu thành công.")
        self.accept()
