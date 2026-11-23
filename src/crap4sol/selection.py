"""File selection (spec §4, §5): default `src/**` scan, explicit paths, exclusions."""

from pathlib import Path

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
