"""In-memory session for the currently authenticated user."""

from app.models.user import User


current_user: dict[str, str] | None = None


def set_current_user(user: User) -> None:
    global current_user
    current_user = {
        "username": user.username,
        "role": user.role,
        "masv": user.masv or "",
        "magv": user.magv or "",
    }


def clear_session() -> None:
    global current_user
    current_user = None
