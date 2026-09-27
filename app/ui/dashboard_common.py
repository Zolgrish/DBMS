"""Shared visual layout and actions for role-specific dashboards."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.user import User
from app.ui.change_password import ChangePasswordDialog


class DashboardWindow(QMainWindow):
    logout_requested = Signal()

    def __init__(self, user: User, heading: str, actions: tuple[str, ...]) -> None:
        super().__init__()
        self.user = user
        self.setWindowTitle(f"Quản lý điểm sinh viên | {heading}")
        self.setMinimumSize(720, 500)
        self.resize(820, 560)

        container = QWidget(self)
        container.setObjectName("dashboardRoot")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(24)

        top_row = QHBoxLayout()
        top_row.setSpacing(18)
        heading_group = QVBoxLayout()
        heading_group.setSpacing(6)
        eyebrow = QLabel("QLDSV  /  KHÔNG GIAN LÀM VIỆC")
        eyebrow.setObjectName("eyebrow")
        title = QLabel(heading)
        title.setObjectName("dashboardTitle")
        heading_group.addWidget(eyebrow)
        heading_group.addWidget(title)
        top_row.addLayout(heading_group)
        top_row.addStretch()

        logout_button = QPushButton("Đăng xuất")
        logout_button.setObjectName("logoutButton")
        logout_button.setMinimumSize(120, 44)
        logout_button.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_button.clicked.connect(self.logout_requested.emit)
        top_row.addWidget(logout_button, alignment=Qt.AlignmentFlag.AlignTop)

        account_card = QFrame()
        account_card.setObjectName("accountCard")
        account_layout = QHBoxLayout(account_card)
        account_layout.setContentsMargins(20, 16, 20, 16)
        account_layout.setSpacing(16)
        account_caption = QLabel("ĐANG ĐĂNG NHẬP")
        account_caption.setObjectName("accountCaption")
        account_name = QLabel(user.username)
        account_name.setObjectName("accountName")
        role_label = QLabel(user.role)
        role_label.setObjectName("roleBadge")
        role_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        account_layout.addWidget(account_caption)
        account_layout.addWidget(account_name)
        account_layout.addStretch()
        account_layout.addWidget(role_label)

        action_frame = QFrame()
        action_frame.setObjectName("actionFrame")
        action_layout = QVBoxLayout(action_frame)
        action_layout.setContentsMargins(26, 24, 26, 26)
        action_layout.setSpacing(18)
        action_heading = QLabel("Chức năng")
        action_heading.setObjectName("sectionTitle")
        action_layout.addWidget(action_heading)

        action_grid = QGridLayout()
        action_grid.setHorizontalSpacing(14)
        action_grid.setVerticalSpacing(14)
        for index, action in enumerate(actions):
            button = QPushButton(action)
            button.setObjectName("actionButton")
            button.setMinimumHeight(56)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda _checked=False, name=action: self._handle_action(name)
            )
            action_grid.addWidget(button, index // 2, index % 2)
        action_grid.setColumnStretch(0, 1)
        action_grid.setColumnStretch(1, 1)
        action_layout.addLayout(action_grid)
        action_layout.addStretch()

        layout.addLayout(top_row)
        layout.addWidget(account_card)
        layout.addWidget(action_frame)
        layout.addStretch()
        self.setCentralWidget(container)
        container.setStyleSheet(
            """
            QWidget#dashboardRoot { background: #101a2b; }
            QLabel { color: #18283d; font-size: 14px; }
            QLabel#eyebrow { color: #8fc8ff; font-size: 11px; font-weight: 700; }
            QLabel#dashboardTitle { color: #ffffff; font-size: 25px; font-weight: 700; }
            QFrame#accountCard { background: #1b2b43; border: 1px solid #344860; border-radius: 12px; }
            QLabel#accountCaption { color: #b7c8da; font-size: 11px; font-weight: 700; }
            QLabel#accountName { color: #ffffff; font-size: 15px; font-weight: 600; }
            QLabel#roleBadge { color: #e9f5ff; background: #28547b; border-radius: 12px;
                               padding: 5px 14px; font-size: 12px; font-weight: 700; }
            QFrame#actionFrame { background: #ffffff; border: 1px solid #dce5ef; border-radius: 14px; }
            QLabel#sectionTitle { color: #18283d; font-size: 19px; font-weight: 700; }
            QPushButton#actionButton { color: #17324d; background: #edf4fb; border: 1px solid #bed2e7;
                                       border-radius: 9px; padding: 0 18px; font-size: 15px;
                                       font-weight: 600; text-align: left; }
            QPushButton#actionButton:hover { color: #103f6a; background: #d9ebfc; border-color: #66a9df; }
            QPushButton#actionButton:pressed { color: #ffffff; background: #1769aa; border-color: #1769aa; }
            QPushButton#actionButton:focus { border: 2px solid #1769aa; }
            QPushButton#logoutButton { color: #ffffff; background: #284664; border: 1px solid #517295;
                                       border-radius: 9px; padding: 0 16px; font-size: 14px; font-weight: 600; }
            QPushButton#logoutButton:hover { background: #385c80; border-color: #8ab6df; }
            QPushButton#logoutButton:pressed { background: #17324d; }
            """
        )

    def _handle_action(self, action: str) -> None:
        if action == "Đổi mật khẩu":
            dialog = ChangePasswordDialog(parent=self)
            try:
                dialog.exec()
            finally:
                dialog.deleteLater()
            return

        QMessageBox.information(self, action, "Chức năng chưa được triển khai.")
