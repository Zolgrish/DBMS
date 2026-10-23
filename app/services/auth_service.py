"""Authenticate SQL credentials and publish only a fully verified SQL session."""

import pyodbc

from app.config.database import open_sql_connection
from app.models.user import User
from app.utils import session


class AuthenticationError(Exception):
    """Expected authentication failure safe to show in the UI."""


class InvalidCredentialsError(AuthenticationError):
    pass


class AuthenticationServiceError(AuthenticationError):
    pass


class AuthService:
    def login(self, username: str, password: str) -> User:
        session.clear_session()
        username = username.strip()
        if not username or not password:
            raise InvalidCredentialsError("Vui lòng nhập tên đăng nhập và mật khẩu.")

        qldsv = master = None
        published = False
        failure = None
        try:
            qldsv = open_sql_connection(username, password, autocommit=True)
            cursor = qldsv.cursor()
            try:
                rows = cursor.execute("EXEC dbo.sp_ThongTinDangNhap;").fetchall()
            finally:
                cursor.close()
            if len(rows) != 1 or len(rows[0]) != 3:
                raise AuthenticationServiceError("SQL Server trả về danh tính không hợp lệ.")
            login_name, database_user, sql_role = rows[0]
            roles = {"QLDSV_ADMIN": "Admin", "QLDSV_GIANGVIEN": "GiangVien", "QLDSV_SINHVIEN": "SinhVien"}
            if (
                not isinstance(login_name, str) or not login_name.strip()
                or not isinstance(database_user, str) or not database_user.strip()
                or sql_role not in roles
            ):
                raise AuthenticationServiceError("Mapping Login/User hoặc business role không hợp lệ.")
            role = roles[sql_role]
            user = User(
                username=login_name,
                role=role,
                masv=database_user if role == "SinhVien" else None,
                magv=database_user if role in {"Admin", "GiangVien"} else None,
                active=True,
            )
            if role == "Admin":
                master = open_sql_connection(username, password, database_override="master", autocommit=True)
                cursor = master.cursor()
                try:
                    rows = cursor.execute("SELECT SUSER_SNAME();").fetchall()
                finally:
                    cursor.close()
                if len(rows) != 1 or rows[0][0] != login_name:
                    raise AuthenticationServiceError("Danh tính kết nối master không khớp Login đã xác thực.")
            session.set_authenticated(user, qldsv, master)
            published = True
        except pyodbc.Error as error:
            state = str(error.args[0]) if error.args else ""
            mapping_failure = any(
                str(number) in str(part)
                for number in (52020, 52021)
                for part in error.args[1:]
            )
            if state == "28000" and not mapping_failure:
                failure = InvalidCredentialsError("Tên đăng nhập hoặc mật khẩu SQL Server không đúng.")
            elif session.is_connection_error(error):
                failure = AuthenticationServiceError("Không thể kết nối SQL Server. Hãy kiểm tra driver, mạng và cấu hình.")
            else:
                failure = AuthenticationServiceError("Không thể xác minh SQL Login/User và quyền truy cập. Hãy liên hệ Admin.")
        except AuthenticationError as error:
            failure = error
        except Exception:
            failure = AuthenticationServiceError("Không thể xác thực phiên SQL Server. Hãy kiểm tra cấu hình kết nối.")
        finally:
            password = ""
            if not published:
                session.close_connection(qldsv)
                if master is not qldsv:
                    session.close_connection(master)
        # Raise outside the driver handler so diagnostics are not retained as context.
        if failure is not None:
            raise failure from None
        return user
