"""Connection target configuration; SQL credentials come only from the caller."""

from __future__ import annotations

import os
from pathlib import Path

import pyodbc

# Set before any connection is opened: logout must end the physical SQL session.
pyodbc.pooling = False

try:
    from dotenv import dotenv_values
except ImportError:
    dotenv_values = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_target_settings() -> None:
    # The same .env also serves Docker bootstrap. Import only application target
    # settings, so bootstrap passwords never become implicit app credentials.
    if dotenv_values is not None:
        settings = dotenv_values(PROJECT_ROOT / ".env")
        for name in ("DB_DRIVER", "DB_SERVER", "DB_DATABASE", "QLDSV_BACKUP_DIR", "QLDSV_SQL_BACKUP_DIR"):
            if settings.get(name) is not None:
                os.environ.setdefault(name, settings[name])


_load_target_settings()


def _required_setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Thiếu {name}; hãy cấu hình đích kết nối SQL Server.")
    return value


def _odbc_value(value: str) -> str:
    return "{" + value.replace("}", "}}") + "}"


def open_sql_connection(
    username: str,
    password: str,
    database_override: str | None = None,
    *,
    autocommit: bool = True,
):
    """Open a SQL-authenticated connection without retaining or logging credentials."""
    if not username or not password:
        raise ValueError("Cần tên đăng nhập và mật khẩu SQL Server.")
    parts = (
        ("DRIVER", _required_setting("DB_DRIVER")),
        ("SERVER", _required_setting("DB_SERVER")),
        ("DATABASE", database_override or _required_setting("DB_DATABASE")),
        ("UID", username),
        ("PWD", password),
    )
    try:
        return pyodbc.connect(
            ";".join(f"{key}={_odbc_value(value)}" for key, value in parts) + ";",
            timeout=5,
            autocommit=autocommit,
        )
    finally:
        password = ""
        parts = ()


def check_database_connection(username: str, password: str) -> str:
    """Check the target database using explicitly supplied SQL credentials."""
    connection = open_sql_connection(username, password)
    try:
        cursor = connection.cursor()
        try:
            row = cursor.execute("SELECT DB_NAME()").fetchone()
            if row is None or row[0] != _required_setting("DB_DATABASE"):
                raise RuntimeError("Kết nối không trỏ tới database đã cấu hình.")
            return str(row[0])
        finally:
            cursor.close()
    finally:
        password = ""
        connection.close()
