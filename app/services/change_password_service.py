"""Self SQL Login password changes using the authenticated QLDSV session."""

import re

import pyodbc

from app.repositories.account_repository import AccountRepository
from app.utils import session


class ChangePasswordError(Exception):
    """Validation or persistence error safe to display in the UI."""


class ChangePasswordService:
    SESSION_ERROR = "Phiên SQL không còn hợp lệ. Vui lòng đăng nhập lại."
    SQL_ERRORS = {
        52101: "Danh tính SQL của phiên không hợp lệ. Vui lòng đăng nhập lại.",
        52102: "Mật khẩu hiện tại không đúng.",
        52103: "Mật khẩu mới không đáp ứng chính sách hoặc lịch sử mật khẩu SQL Server.",
        52104: "Không thể đổi mật khẩu SQL Server.",
    }

    def __init__(self, account_repository: AccountRepository | None = None) -> None:
        self._accounts = account_repository or AccountRepository()

    def change_password(
        self,
        current_password: str,
        new_password: str,
        confirm_password: str,
    ) -> None:
        failure = None
        try:
            session.require_qldsv_connection()
            if not current_password:
                raise ChangePasswordError("Mật khẩu hiện tại không được để trống.")
            if not new_password:
                raise ChangePasswordError("Mật khẩu mới không được để trống.")
            if not confirm_password:
                raise ChangePasswordError("Vui lòng xác nhận mật khẩu mới.")
            if len(current_password.encode("utf-16-le")) > 256:
                raise ChangePasswordError("Mật khẩu hiện tại không được vượt quá 128 đơn vị UTF-16.")
            if len(new_password.encode("utf-16-le")) > 256:
                raise ChangePasswordError("Mật khẩu mới không được vượt quá 128 đơn vị UTF-16.")
            if new_password != confirm_password:
                raise ChangePasswordError("Mật khẩu mới và xác nhận mật khẩu không khớp.")
            # No principal name, reconnect or Python password-policy decision.
            self._accounts.update_password(current_password, new_password)
        except session.SessionRequiredError:
            failure = self.SESSION_ERROR
        except UnicodeError:
            failure = "Mật khẩu chứa dữ liệu Unicode không hợp lệ."
        except ChangePasswordError as error:
            failure = str(error)
        except pyodbc.Error as error:
            # Inspect only known error numbers; never log/display diagnostics.
            numbers = re.findall(r"(?<!\d)521\d{2}(?!\d)", " ".join(str(part) for part in error.args))
            if "52101" in numbers:
                session.invalidate_session()
                numbers = ["52101"]
            failure = next((self.SQL_ERRORS[int(number)] for number in numbers
                            if int(number) in self.SQL_ERRORS), self.SQL_ERRORS[52104])
        finally:
            current_password = new_password = confirm_password = ""
        # Outside the handlers: neither cause nor context retains driver errors.
        if failure is not None:
            raise ChangePasswordError(failure) from None
