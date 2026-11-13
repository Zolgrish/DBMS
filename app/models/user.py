"""Authenticated account model."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class User:
    username: str
    role: str
    masv: str | None
    magv: str | None
    active: bool
    full_name: str = ""
    login_name: str | None = None
    principal_sid: bytes | None = None

    def __post_init__(self) -> None:
        # Legacy call sites supplied only a username because both SQL names matched.
        if self.login_name is None:
            object.__setattr__(self, "login_name", self.username)
