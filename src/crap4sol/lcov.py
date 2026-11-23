"""LCOV parsing (spec §7.3) and SF path normalization (spec §9.1)."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileCoverage:
    lines: dict[int, int] = field(default_factory=dict)  # DA line -> hits
    brda: list[str] = field(default_factory=list)  # raw payloads after "BRDA:"


def parse_lcov(text: str) -> dict[str, FileCoverage]:
    """Map each SF record to its DA hits and raw BRDA entries; other records are ignored."""
    report: dict[str, FileCoverage] = {}
    current: FileCoverage | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("SF:"):
            current = report.setdefault(line[3:], FileCoverage())
        elif line == "end_of_record":
            current = None
        elif current is None:
            continue
        elif line.startswith("DA:"):
            lineno, hits = line[3:].split(",")[:2]
            current.lines[int(lineno)] = int(hits)
        elif line.startswith("BRDA:"):
            current.brda.append(line[5:])
    return report


def load_lcov(path: Path) -> dict[str, FileCoverage] | None:
    """Parse the LCOV file at path; None if it is missing or empty (spec §7)."""
    path = Path(path)
    if not path.is_file():
        return None
    text = path.read_text()
    if not text.strip():
        return None
    return parse_lcov(text)


def normalize_sf(sf: str, module_root: Path) -> str:
    """Normalize an LCOV SF path to a module-relative POSIX path."""
    p = Path(sf)
    if p.is_absolute():
        root = Path(module_root)
        for candidate, base in ((p, root), (p.resolve(), root.resolve())):
            try:
                return candidate.relative_to(base).as_posix()
            except ValueError:
                pass
    return p.as_posix()
