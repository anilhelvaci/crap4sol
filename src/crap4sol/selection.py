"""File selection (spec §4, §5): default `src/**` scan, explicit paths, exclusions."""

import subprocess
from pathlib import Path

from crap4sol.errors import AnalysisError

EXCLUDED_DIRS = frozenset({"lib", "test", "script", "node_modules"})
EXCLUDED_SUFFIXES = (".t.sol", ".s.sol")


def _is_excluded(project_root: Path, path: Path) -> bool:
    """Excluded unless a `.sol` file inside the project root; also excluded if a test/script file
    or any dir component relative to the root is an excluded dir (components above the root
    never count)."""
    if path.suffix != ".sol" or path.name.endswith(EXCLUDED_SUFFIXES):
        return True
    if not path.is_relative_to(project_root):
        return True
    parts = path.relative_to(project_root).parts[:-1]
    return any(part in EXCLUDED_DIRS for part in parts)


def _sol_under_src(base: Path) -> list[Path]:
    src = base / "src"
    if not src.is_dir():
        return []
    return [p.resolve() for p in src.rglob("*.sol") if p.is_file()]


def _finalize(project_root: Path, files: list[Path]) -> list[Path]:
    return sorted({f for f in files if not _is_excluded(project_root, f)})


def select_default(project_root: Path) -> list[Path]:
    """All `.sol` files under `<project_root>/src/**`, minus exclusions; absolute, sorted."""
    root = project_root.resolve()
    return _finalize(root, _sol_under_src(root))


def select_paths(project_root: Path, paths: list[str]) -> list[Path]:
    """Files are taken directly; directories expand to `.sol` under `<dir>/src/**`.
    Relative paths resolve against the project root. Deduped, sorted, exclusions applied."""
    root = project_root.resolve()
    files: list[Path] = []
    for raw in paths:
        p = (root / raw).resolve()
        if p.is_dir():
            files.extend(_sol_under_src(p))
        elif p.is_file():
            files.append(p)
    return _finalize(root, files)


_C_ESCAPES = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12, "r": 13, '"': 34, "\\": 92}


def _read_path(s: str) -> tuple[str, str]:
    """Read one porcelain path from the start of `s` (C-quoted or bare); return (path, rest)."""
    if not s.startswith('"'):
        return s, ""
    out = bytearray()
    i = 1
    while i < len(s):
        ch = s[i]
        if ch == '"':
            return out.decode("utf-8", errors="surrogateescape"), s[i + 1 :]
        if ch == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt in "01234567" and i + 3 < len(s):
                out.append(int(s[i + 1 : i + 4], 8))
                i += 4
                continue
            out.append(_C_ESCAPES.get(nxt, ord(nxt)))
            i += 2
            continue
        out.extend(ch.encode("utf-8"))
        i += 1
    return out.decode("utf-8", errors="surrogateescape"), ""


def parse_porcelain(text: str) -> list[str]:
    """Paths from `git status --porcelain` v1: modified, added, untracked (input order).
    Renames/copies yield the new path; anything with a deletion is dropped."""
    paths: list[str] = []
    for line in text.splitlines():
        if len(line) < 4:
            continue
        code, rest = line[:2], line[3:]
        if "D" in code or not any(c in code for c in "MA?RC"):
            continue
        if "R" in code or "C" in code:
            if rest.startswith('"'):
                _, rest = _read_path(rest)
                rest = rest.removeprefix(" -> ")
            else:
                rest = rest.split(" -> ", 1)[-1]
        path, _ = _read_path(rest)
        paths.append(path)
    return paths


def _git(project_root: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=project_root, capture_output=True, text=True, check=False
        )
    except OSError as exc:
        raise AnalysisError(f"git failed: {exc}") from exc
    if proc.returncode != 0:
        raise AnalysisError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def select_changed(project_root: Path) -> list[Path]:
    """Changed (modified/added/untracked) `.sol` files under `<project_root>/src/` per
    `git status --porcelain`, minus exclusions; absolute, deduped, sorted."""
    root = project_root.resolve()
    top = Path(_git(root, "rev-parse", "--show-toplevel").strip()).resolve()
    status = _git(root, "-c", "core.quotePath=true", "status", "--porcelain", "-uall")
    src = root / "src"
    files = [(top / rel).resolve() for rel in parse_porcelain(status)]
    return _finalize(root, [f for f in files if f.is_relative_to(src) and f.is_file()])
