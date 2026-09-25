"""Authenticated account model."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class User:
    username: str
    role: str
    masv: str | None
    magv: str | None
    active: bool
