"""Role checks based on the current authenticated session."""

from app.utils import session


def require_admin() -> None:
    current_user = session.current_user
    if current_user is None or current_user.get("role") != "Admin":
        raise PermissionError("Chỉ Admin được phép quản lý tài khoản.")


def require_student_masv() -> str:
    current_user = session.current_user
    if current_user is None or current_user.get("role") != "SinhVien":
        raise PermissionError("Chỉ sinh viên được xem điểm của mình.")

    masv = current_user.get("masv", "").strip()
    if not masv:
        raise PermissionError("Phiên đăng nhập không có MASV hợp lệ.")
    return masv


def require_lecturer_magv() -> str:
    """Return the trusted SQL-session lecturer identity, never a UI selection."""
    current_user = session.current_user
    if current_user is None or current_user.get("role") != "GiangVien":
        raise PermissionError("Chỉ giảng viên được sử dụng chức năng nhập điểm được phân công.")
    magv = (current_user.get("magv") or "").strip()
    if not magv:
        raise PermissionError("Phiên đăng nhập không có MAGV hợp lệ.")
    return magv
