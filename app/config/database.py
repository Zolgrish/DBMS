"""SQL Server connection settings and a read-only connectivity check."""

from __future__ import annotations

import os
from pathlib import Path

import pyodbc

try:
    from dotenv import load_dotenv
except ImportError:  # Environment variables can still be configured by the OS.
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if load_dotenv is not None:
    load_dotenv(PROJECT_ROOT / ".env", override=False)


def _required_setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Thiếu {name}; hãy tạo .env từ .env.example và cấu hình lại.")
    return value


def _odbc_value(value: str) -> str:
    """Brace an ODBC value so spaces and semicolons are handled safely."""
    return "{" + value.replace("}", "}}") + "}"


def get_connection_string() -> str:
    """Build the connection string from environment variables loaded from .env."""
    driver = _required_setting("DB_DRIVER")
    server = _required_setting("DB_SERVER")
    database = _required_setting("DB_DATABASE")
    trusted = _required_setting("DB_TRUSTED_CONNECTION").lower()

    parts = [
        f"DRIVER={_odbc_value(driver)}",
        f"SERVER={_odbc_value(server)}",
        f"DATABASE={_odbc_value(database)}",
    ]

    if trusted in {"yes", "true", "1"}:
        parts.append("Trusted_Connection=yes")
    elif trusted in {"no", "false", "0"}:
        username = os.getenv("DB_USERNAME", "").strip()
        password = os.getenv("DB_PASSWORD", "")
        if not username or not password:
            raise ValueError(
                "Cần cấu hình DB_USERNAME và DB_PASSWORD khi tắt xác thực Windows."
            )
        parts.extend((f"UID={_odbc_value(username)}", f"PWD={_odbc_value(password)}"))
    else:
        raise ValueError("DB_TRUSTED_CONNECTION chỉ nhận yes/no.")

    return ";".join(parts) + ";"


def get_connection() -> pyodbc.Connection:
    """Open a SQL Server connection."""
    return pyodbc.connect(get_connection_string(), timeout=5)


def check_database_connection() -> str:
    """Confirm QLDSV and dbo.TaiKhoan are readable without changing data."""
    connection = get_connection()
    try:
        row = connection.cursor().execute(
            "SELECT DB_NAME(), OBJECT_ID(N'dbo.TaiKhoan', N'U')"
        ).fetchone()
        expected_database = _required_setting("DB_DATABASE")
        if row is None or row[0] != expected_database:
            raise RuntimeError(
                f"Kết nối được nhưng không xác nhận được database {expected_database}."
            )
        if row[1] is None:
            raise RuntimeError("Không tìm thấy bảng dbo.TaiKhoan trong QLDSV.")
        return str(row[0])
    finally:
        connection.close()


if __name__ == "__main__":
    print(f"Connected to SQL Server database: {check_database_connection()}")
