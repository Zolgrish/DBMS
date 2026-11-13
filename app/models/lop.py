"""Class (Lop) business entity."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Lop:
    malop: str
    tenlop: str

