"""LCOV parsing (spec §7.3) and SF path normalization (spec §9.1)."""

import os.path
from dataclasses import dataclass, field
from pathlib import Path

from crap4sol.errors import AnalysisError


@dataclass
class FileCoverage:
    lines: dict[int, int] = field(default_factory=dict)  # DA line -> hits
    brda: list[str] = field(default_factory=list)  # raw payloads after "BRDA:"


def parse_lcov(text: str) -> dict[str, FileCoverage]:
    """Map each SF record to its DA hits and raw BRDA entries; other records are ignored."""
    report: dict[str, FileCoverage] = {}
    current: FileCoverage | None = None
    sf = ""
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("SF:"):
            sf = line[3:]
            current = report.setdefault(sf, FileCoverage())
        elif line == "end_of_record":
            current = None
        elif current is None:
            continue
        elif line.startswith("DA:"):
            lineno, hits = _parse_da(line, sf)
            current.lines[lineno] = current.lines.get(lineno, 0) + hits
        elif line.startswith("BRDA:"):
            current.brda.append(line[5:])
    return report


def _parse_da(line: str, sf: str) -> tuple[int, int]:
    """Parse 'DA:<line>,<hits>[,<checksum>]'; malformed input is an analysis failure."""
    fields = line[3:].split(",")
    try:
        lineno, hits = int(fields[0]), int(fields[1])
    except (IndexError, ValueError):
        lineno = hits = -1
    if lineno < 1 or hits < 0:
        raise AnalysisError(f"malformed LCOV DA record in SF {sf}: {line!r}")
    return lineno, hits


def _merge(into: FileCoverage, other: FileCoverage) -> None:
    for lineno, hits in other.lines.items():
        into.lines[lineno] = into.lines.get(lineno, 0) + hits
    into.brda.extend(other.brda)


def load_lcov(path: Path) -> dict[str, FileCoverage] | None:
    """Parse the LCOV file at path; None if it is missing or empty (spec §7)."""
    path = Path(path)
    if not path.is_file():
        return None
    text = path.read_text()
    if not text.strip():
        return None
    try:
        return parse_lcov(text)
    except AnalysisError as e:
        raise AnalysisError(f"{path}: {e}") from e


def normalize_sf(sf: str, module_root: Path) -> str:
    """Normalize an LCOV SF path to a module-relative POSIX path."""
    p = Path(os.path.normpath(sf))
    if p.is_absolute():
        root = Path(module_root)
        for candidate, base in ((p, root), (p.resolve(), root.resolve())):
            try:
                return candidate.relative_to(base).as_posix()
            except ValueError:
                pass
    return p.as_posix()


def normalize_report(report: dict[str, FileCoverage], module_root: Path) -> dict[str, FileCoverage]:
    """Re-key a report by module-relative SF; entries that collide are merged (hits summed)."""
    out: dict[str, FileCoverage] = {}
    for sf, fc in report.items():
        _merge(out.setdefault(normalize_sf(sf, module_root), FileCoverage()), fc)
    return out
