"""Authenticated identity and exclusive ownership of the live SQL connections."""

from contextlib import contextmanager

import pyodbc
from PySide6.QtCore import QObject, Signal

from app.models.user import User


class SessionRequiredError(ValueError):
    """No usable authenticated connection remains; the user must log in again."""


class _SessionEvents(QObject):
    invalidated = Signal()


events = _SessionEvents()
current_user: dict[str, str] | None = None
_qldsv_connection = None
_master_connection = None


def close_connection(connection) -> None:
    """Best-effort cleanup, including already closed/broken ODBC connections."""
    if connection is not None:
        try:
            connection.close()
        except Exception:
            pass


def clear_session() -> None:
    global current_user, _qldsv_connection, _master_connection
    qldsv, master = _qldsv_connection, _master_connection
    current_user = None
    _qldsv_connection = _master_connection = None
    close_connection(qldsv)
    if master is not qldsv:
        close_connection(master)


def invalidate_session() -> None:
    """Clear resources and ask the UI to return to login after the current action."""
    clear_session()
    events.invalidated.emit()


def invalidate_qldsv_connection() -> None:
    """Release QLDSV before restore; retain master only for restore/cleanup."""
    global _qldsv_connection
    connection, _qldsv_connection = _qldsv_connection, None
    close_connection(connection)


def set_authenticated(user: User, qldsv_connection, master_connection=None) -> None:
    global current_user, _qldsv_connection, _master_connection
    clear_session()
    current_user = {
        "username": user.username,
        "role": user.role,
        "masv": user.masv or "",
        "magv": user.magv or "",
    }
    _qldsv_connection = qldsv_connection
    _master_connection = master_connection


def set_current_user(user: User) -> None:
    """Identity-only compatibility for isolated service/UI tests; supplies no SQL access."""
    set_authenticated(user, None)


def require_qldsv_connection():
    if current_user is None or _qldsv_connection is None:
        raise SessionRequiredError("Phiên SQL không còn hiệu lực. Vui lòng đăng nhập lại.")
    return _qldsv_connection


def require_master_connection():
    if current_user is None or current_user["role"] != "Admin" or _master_connection is None:
        raise SessionRequiredError("Cần đăng nhập lại bằng tài khoản Admin để truy cập master.")
    return _master_connection


def is_connection_error(error: pyodbc.Error) -> bool:
    state = str(error.args[0]) if error.args else ""
    return (
        state.startswith("08")
        or state in {"IM002", "HYT00", "HYT01"}
        or "closed connection" in state.lower()
    )


@contextmanager
def _borrow_cursor(connection):
    cursor = None
    try:
        cursor = connection.cursor()
        yield cursor
    except pyodbc.Error as error:
        if is_connection_error(error):
            invalidate_session()
            raise SessionRequiredError("Mất kết nối SQL Server. Vui lòng đăng nhập lại.") from None
        raise
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except pyodbc.Error:
                pass


def qldsv_cursor():
    """Repositories borrow a cursor and never close the session's connection."""
    return _borrow_cursor(require_qldsv_connection())


def master_cursor():
    return _borrow_cursor(require_master_connection())
