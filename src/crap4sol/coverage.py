"""Line coverage attribution to callables (spec §9.1)."""

from crap4sol.lcov import FileCoverage
from crap4sol.metrics import Callable, Metric, crap


def line_coverage(file_cov: FileCoverage | None, start: int, end: int) -> float | None:
    """Hit DA lines / DA lines in [start, end]; None (N/A) if file absent or no DA in range."""
    if file_cov is None:
        return None
    hits = [h for line, h in file_cov.lines.items() if start <= line <= end]
    if not hits:
        return None
    return sum(1 for h in hits if h > 0) / len(hits)


def attribute(c: Callable, report: dict[str, FileCoverage] | None) -> Metric:
    """Coverage and CRAP for one callable; both N/A when coverage is N/A."""
    file_cov = report.get(c.file) if report is not None else None
    coverage = line_coverage(file_cov, c.start_line, c.end_line)
    if coverage is None:
        return Metric(c, None, None)
    return Metric(c, coverage, crap(c.cc, coverage))
