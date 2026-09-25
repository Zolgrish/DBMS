"""Authentication and session creation."""

import logging

import pyodbc

from app.models.user import User
from app.repositories.account_repository import AccountRepository
from app.utils import session


class AuthenticationError(Exception):
    """Expected authentication failure safe to show in the UI."""


class InvalidCredentialsError(AuthenticationError):
    pass


class LockedAccountError(AuthenticationError):
    pass


class AuthenticationServiceError(AuthenticationError):
    pass


class AuthService:
    def __init__(self, account_repository: AccountRepository | None = None) -> None:
        self._accounts = account_repository or AccountRepository()

    def login(self, username: str, password: str) -> User:
        username = username.strip()
        if not username or not password:
            raise InvalidCredentialsError("Vui lòng nhập tên đăng nhập và mật khẩu.")

        try:
            user = self._accounts.find_by_credentials(username, password)
        except (pyodbc.Error, ValueError):
            logging.exception("Không thể truy cập tài khoản trong SQL Server.")
            raise AuthenticationServiceError(
                "Không thể kết nối cơ sở dữ liệu. Hãy kiểm tra SQL Server và cấu hình kết nối."
            ) from None

        if user is None:
            raise InvalidCredentialsError("Tên đăng nhập hoặc mật khẩu không đúng.")
        if not user.active:
            raise LockedAccountError("Tài khoản đã bị khóa. Vui lòng liên hệ quản trị viên.")

        session.set_current_user(user)
        return user
