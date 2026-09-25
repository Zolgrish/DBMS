"""Shared structure for role-specific dashboard windows."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.user import User


class DashboardWindow(QMainWindow):
    logout_requested = Signal()

    def __init__(self, user: User, heading: str, actions: tuple[str, ...]) -> None:
        super().__init__()
        self.user = user
        self.setWindowTitle(f"Quản lý điểm sinh viên | {heading}")
        self.resize(760, 480)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(30, 24, 30, 26)
        layout.setSpacing(18)

        top_row = QHBoxLayout()
        title = QLabel(heading)
        title.setObjectName("dashboardTitle")
        top_row.addWidget(title)
        top_row.addStretch()
        logout_button = QPushButton("Đăng xuất")
        logout_button.clicked.connect(self.logout_requested.emit)
        top_row.addWidget(logout_button)

        welcome = QLabel(f"Tài khoản: {user.username}    |    Vai trò: {user.role}")
        welcome.setObjectName("welcomeLabel")

        action_frame = QFrame()
        action_frame.setObjectName("actionFrame")
        action_layout = QVBoxLayout(action_frame)
        action_layout.setContentsMargins(20, 18, 20, 18)
        action_layout.setSpacing(12)
        action_heading = QLabel("Chức năng")
        action_heading.setObjectName("sectionTitle")
        action_layout.addWidget(action_heading)
        for action in actions:
            button = QPushButton(action)
            button.setMinimumHeight(42)
            button.clicked.connect(lambda _checked=False, name=action: self._show_placeholder(name))
            action_layout.addWidget(button)
        action_layout.addStretch()

        layout.addLayout(top_row)
        layout.addWidget(welcome)
        layout.addWidget(action_frame, 1)
        container.setStyleSheet(
            """
            QWidget { font-size: 14px; }
            QLabel#dashboardTitle { color: #173b63; font-size: 24px; font-weight: 700; }
            QLabel#sectionTitle { color: #173b63; font-size: 17px; font-weight: 600; }
            QLabel#welcomeLabel { color: #526274; }
            QFrame#actionFrame { background: #f4f7fb; border: 1px solid #dce5ef; border-radius: 8px; }
            QPushButton { min-height: 36px; padding: 0 14px; }
            """
        )
        self.setCentralWidget(container)

    def _show_placeholder(self, action: str) -> None:
        QMessageBox.information(
            self,
            action,
            f"Chức năng “{action}” sẽ được bổ sung ở milestone tiếp theo.",
        )
