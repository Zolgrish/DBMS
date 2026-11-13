"""Subject (Monhoc) business entity."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Monhoc:
    mamh: str
    tenmh: str
    sotclt: int
    sotcth: int

