"""Lecturer business entity, independent of authenticated SQL identity."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Lecturer:
    magv: str
    ho: str | None
    ten: str | None
    phai: bool
