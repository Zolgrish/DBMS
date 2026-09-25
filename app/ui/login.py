"""Login window. Database access is delegated to AuthService."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.user import User
from app.services.auth_service import AuthService, AuthenticationError


class LoginWindow(QMainWindow):
    authenticated = Signal(object)

    def __init__(self, auth_service: AuthService) -> None:
        super().__init__()
        self._auth_service = auth_service
        self.setWindowTitle("Quản lý điểm sinh viên | Đăng nhập")
        self.setMinimumWidth(420)
        self.setFixedHeight(310)
        self._build_ui()

    def _build_ui(self) -> None:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(36, 30, 36, 28)
        layout.setSpacing(16)

        title = QLabel("Quản lý điểm sinh viên")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("Đăng nhập để tiếp tục")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        form = QFormLayout()
        form.setSpacing(12)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Nhập tên đăng nhập")
        self.username_input.setObjectName("usernameInput")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Nhập mật khẩu")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setObjectName("passwordInput")
        self.password_input.returnPressed.connect(self._login)
        form.addRow("Tên đăng nhập", self.username_input)
        form.addRow("Mật khẩu", self.password_input)

        buttons = QHBoxLayout()
        self.login_button = QPushButton("Đăng nhập")
        self.login_button.setObjectName("primaryButton")
        self.login_button.clicked.connect(self._login)
        exit_button = QPushButton("Thoát")
        exit_button.clicked.connect(self.close)
        buttons.addWidget(self.login_button)
        buttons.addWidget(exit_button)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(4)
        layout.addLayout(form)
        layout.addStretch()
        layout.addLayout(buttons)
        container.setStyleSheet(
            """
            QWidget { font-size: 14px; }
            QLabel#title { color: #173b63; font-size: 22px; font-weight: 700; }
            QLineEdit { min-height: 34px; padding: 2px 9px; }
            QPushButton { min-height: 36px; padding: 0 14px; }
            QPushButton#primaryButton { background: #1769aa; color: white; font-weight: 600; }
            QPushButton#primaryButton:hover { background: #12578f; }
            """
        )
        self.setCentralWidget(container)

    def _login(self) -> None:
        try:
            user = self._auth_service.login(
                self.username_input.text(), self.password_input.text()
            )
        except AuthenticationError as error:
            QMessageBox.warning(self, "Đăng nhập không thành công", str(error))
            self.password_input.clear()
            self.password_input.setFocus()
            return

        self.password_input.clear()
        self.authenticated.emit(user)

    def prepare_for_logout(self) -> None:
        self.password_input.clear()
        self.username_input.setFocus()
