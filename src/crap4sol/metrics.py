"""Callable and metric data model (spec §3, §8)."""

from dataclasses import dataclass
from enum import Enum


class Kind(Enum):
    FUNCTION = "function"
    MODIFIER = "modifier"
    CONSTRUCTOR = "constructor"
    RECEIVE = "receive"
    FALLBACK = "fallback"
    FREE = "free"


@dataclass(frozen=True)
class Callable:
    contract: str
    signature: str
    kind: Kind
    file: str
    start_line: int
    end_line: int
    cc: int


@dataclass(frozen=True)
class Metric:
    callable: Callable
    coverage: float | None  # None = N/A
    crap: float | None  # None = N/A
