"""Module root discovery and grouping (spec §3, §6)."""

from pathlib import Path

MARKER = "foundry.toml"


def module_root(file: Path, project_root: Path) -> Path:
    """Nearest ancestor dir of `file` (starting at its own dir) holding a `foundry.toml` file,
    never leaving the project root; fallback = project root."""
    root = project_root.resolve()
    d = file.resolve().parent
    while d.is_relative_to(root):
        if (d / MARKER).is_file():
            return d
        if d == root:
            break
        d = d.parent
    return root


def group_by_module(files: list[Path], project_root: Path) -> dict[Path, list[Path]]:
    """Files grouped by module root; keys sorted, files sorted within each group."""
    groups: dict[Path, list[Path]] = {}
    for f in files:
        groups.setdefault(module_root(f, project_root), []).append(f)
    return {k: sorted(groups[k]) for k in sorted(groups)}
