"""Shared colors and control styling for application dialogs."""

DIALOG_STYLE = """
    QDialog { background: #f3f6fb; }
    QLabel { color: #19324d; font-size: 14px; }
    QLineEdit, QComboBox {
        color: #19324d; background: #ffffff; border: 1px solid #aebfd2;
        border-radius: 7px; min-height: 34px; padding: 3px 9px; font-size: 14px;
    }
    QLineEdit:focus, QComboBox:focus { border: 2px solid #1769aa; }
    QLineEdit:disabled { color: #65788a; background: #e8edf3; }
    QComboBox QAbstractItemView { color: #19324d; background: #ffffff; selection-background-color: #d9ebfc; }
    QPushButton {
        color: #19324d; background: #e4edf7; border: 1px solid #b9cde2;
        border-radius: 7px; min-height: 36px; padding: 3px 14px;
        font-size: 14px; font-weight: 600;
    }
    QPushButton:hover { color: #104675; background: #d2e6f9; border-color: #6aabdc; }
    QPushButton:pressed { color: #ffffff; background: #1769aa; }
    QPushButton#saveAccountButton, QPushButton#changePasswordButton, QPushButton#addAccountButton {
        color: #ffffff; background: #1769aa; border-color: #1769aa;
    }
    QPushButton#saveAccountButton:hover, QPushButton#changePasswordButton:hover,
    QPushButton#addAccountButton:hover { background: #10578f; border-color: #10578f; }
    QPushButton#saveAccountButton:pressed, QPushButton#changePasswordButton:pressed,
    QPushButton#addAccountButton:pressed { background: #0b426e; }
    QTableWidget {
        color: #19324d; background: #ffffff; alternate-background-color: #f0f5fb;
        gridline-color: #d9e3ee; border: 1px solid #cbd9e7;
        border-radius: 7px; font-size: 13px;
    }
    QTableWidget::item:selected { color: #ffffff; background: #1769aa; }
    QHeaderView::section {
        color: #19324d; background: #e4edf7; border: 0; border-bottom: 1px solid #cbd9e7;
        padding: 8px; font-size: 13px; font-weight: 700;
    }
"""
