"""Change-password rules for the current in-memory session."""

import logging

import pyodbc

from app.repositories.account_repository import AccountRepository
from app.utils import session


class ChangePasswordError(Exception):
    """Validation or persistence error safe to display in the UI."""


class ChangePasswordService:
    def __init__(self, account_repository: AccountRepository | None = None) -> None:
        self._accounts = account_repository or AccountRepository()

    def change_password(
        self,
        current_password: str,
        new_password: str,
        confirm_password: str,
    ) -> None:
        current_user = session.current_user
        if current_user is None or not current_user.get("username"):
            raise ChangePasswordError("Phiên đăng nhập không còn hợp lệ.")
        if not current_password:
            raise ChangePasswordError("Mật khẩu hiện tại không được để trống.")
        if not new_password:
            raise ChangePasswordError("Mật khẩu mới không được để trống.")
        if not confirm_password:
            raise ChangePasswordError("Vui lòng xác nhận mật khẩu mới.")
        if len(new_password) > 255:
            raise ChangePasswordError("Mật khẩu mới không được vượt quá 255 ký tự.")
        if new_password != confirm_password:
            raise ChangePasswordError("Mật khẩu mới và xác nhận mật khẩu không khớp.")

        try:
            changed = self._accounts.update_password(
                current_user["username"],
                current_password,
                new_password,
            )
        except (pyodbc.Error, ValueError):
            logging.exception("Không thể cập nhật mật khẩu trong SQL Server.")
            raise ChangePasswordError("Không thể truy cập cơ sở dữ liệu.") from None

        if not changed:
            raise ChangePasswordError("Mật khẩu hiện tại không đúng.")
