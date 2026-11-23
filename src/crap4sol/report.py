"""Report table (spec §11) and CRAP threshold check (spec §12)."""

import math
from typing import TextIO

from crap4sol.errors import EXIT_SUCCESS, EXIT_THRESHOLD_EXCEEDED
from crap4sol.metrics import Metric

THRESHOLD = 8.0

_HEADERS = ("Function", "Contract", "Kind", "CC", "Cov%", "CRAP")
_RIGHT_ALIGNED = {"CC", "Cov%", "CRAP"}
_NA = "N/A"


def sort_metrics(metrics: list[Metric]) -> list[Metric]:
    """CRAP descending, N/A rows last; ties by contract, then signature."""

    def key(m: Metric):
        is_na = m.crap is None
        c = m.callable
        return (is_na, 0.0 if is_na else -m.crap, c.contract, c.signature, c.file, c.start_line)

    return sorted(metrics, key=key)


def _round_to(x: float, digits: int, rounder) -> float:
    """Round x to `digits` decimals with ceil/floor, ignoring binary float noise (1.1 stays 1.1)."""
    scale = 10**digits
    return rounder(round(x * scale, 6)) / scale


def _cells(m: Metric) -> tuple[str, ...]:
    c = m.callable
    # Display never flatters: coverage rounds down, CRAP rounds up.
    cov = _NA if m.coverage is None else f"{_round_to(m.coverage * 100, 1, math.floor):.1f}%"
    crap = _NA if m.crap is None else f"{_round_to(m.crap, 2, math.ceil):.2f}"
    return (c.signature, c.contract, c.kind.value, str(c.cc), cov, crap)


def render(metrics: list[Metric]) -> str:
    """Render metrics as an aligned text table, in the given order."""
    rows = [_cells(m) for m in metrics]
    widths = [max([len(h)] + [len(r[i]) for r in rows]) for i, h in enumerate(_HEADERS)]

    def line(cells) -> str:
        parts = [
            cell.rjust(w) if h in _RIGHT_ALIGNED else cell.ljust(w)
            for cell, w, h in zip(cells, widths, _HEADERS)
        ]
        return "  ".join(parts).rstrip() + "\n"

    out = [line(_HEADERS), line("-" * w for w in widths)]
    out.extend(line(r) for r in rows)
    return "".join(out)


def max_crap(metrics: list[Metric]) -> float:
    """Largest numeric CRAP; 0.0 when there is none."""
    return max((m.crap for m in metrics if m.crap is not None), default=0.0)


def check_threshold(metrics: list[Metric], err: TextIO) -> int:
    """EXIT_THRESHOLD_EXCEEDED (with a stderr message) if max CRAP > THRESHOLD."""
    worst = max_crap(metrics)
    if worst > THRESHOLD:
        err.write(f"CRAP threshold exceeded: {worst} > {THRESHOLD}\n")
        return EXIT_THRESHOLD_EXCEEDED
    return EXIT_SUCCESS
