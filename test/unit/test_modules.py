"""T2.6-T2.7: module root discovery and grouping (spec §3, §6).

Contract (crap4sol.modules):
  module_root(file: Path, project_root: Path) -> Path
      Walk up from the file's directory until a directory containing a `foundry.toml` FILE is
      found, never leaving the project root; fallback = project root. Absolute, resolved.
  group_by_module(files: list[Path], project_root: Path) -> dict[Path, list[Path]]
      Files grouped by module root; keys in sorted order, files sorted within each group.
"""

from pathlib import Path

import pytest

from crap4sol.modules import group_by_module, module_root


@pytest.fixture
def root(tmp_path: Path) -> Path:
    r = tmp_path.resolve() / "proj"
    r.mkdir()
    return r


def touch(root: Path, *rels: str) -> None:
    for rel in rels:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("")


# --- T2.6 module root ---------------------------------------------------------


def test_foundry_toml_at_project_root_is_module_root(root):
    touch(root, "foundry.toml", "src/A.sol")
    assert module_root(root / "src/A.sol", root) == root


def test_no_foundry_toml_falls_back_to_project_root(root):
    touch(root, "src/A.sol")
    assert module_root(root / "src/A.sol", root) == root


def test_nested_module_foundry_toml_wins_over_project_root(root):
    touch(root, "foundry.toml", "modA/foundry.toml", "modA/src/A.sol")
    assert module_root(root / "modA/src/A.sol", root) == root / "modA"


def test_nearest_foundry_toml_wins(root):
    touch(root, "modA/foundry.toml", "modA/sub/foundry.toml", "modA/sub/src/deep/X.sol")
    assert module_root(root / "modA/sub/src/deep/X.sol", root) == root / "modA/sub"


def test_walk_starts_at_files_own_directory(root):
    touch(root, "modA/src/foundry.toml", "modA/src/A.sol", "modA/foundry.toml")
    assert module_root(root / "modA/src/A.sol", root) == root / "modA/src"


def test_foundry_toml_above_project_root_is_ignored(root):
    touch(root.parent, "foundry.toml")
    touch(root, "src/A.sol")
    assert module_root(root / "src/A.sol", root) == root


def test_sibling_module_does_not_capture_file(root):
    touch(root, "modB/foundry.toml", "modA/src/A.sol")
    assert module_root(root / "modA/src/A.sol", root) == root


def test_directory_named_foundry_toml_is_not_a_marker(root):
    (root / "modA/foundry.toml").mkdir(parents=True)
    touch(root, "modA/src/A.sol")
    assert module_root(root / "modA/src/A.sol", root) == root


def test_module_root_is_resolved_even_for_unresolved_inputs(root):
    touch(root, "modA/foundry.toml", "modA/src/A.sol")
    got = module_root(root / "modA/src/../src/A.sol", root / "." / "modA" / "..")
    assert got == root / "modA"


# --- T2.7 grouping --------------------------------------------------------------


def test_group_empty_input_is_empty(root):
    assert group_by_module([], root) == {}


def test_group_files_by_module_root(root):
    touch(
        root,
        "foundry.toml",
        "src/R.sol",
        "modA/foundry.toml",
        "modA/src/A1.sol",
        "modA/src/A2.sol",
        "modB/foundry.toml",
        "modB/src/B.sol",
    )
    files = [root / p for p in ("modB/src/B.sol", "src/R.sol", "modA/src/A2.sol", "modA/src/A1.sol")]
    assert group_by_module(files, root) == {
        root: [root / "src/R.sol"],
        root / "modA": [root / "modA/src/A1.sol", root / "modA/src/A2.sol"],
        root / "modB": [root / "modB/src/B.sol"],
    }


def test_group_keys_are_sorted(root):
    touch(root, "z/foundry.toml", "z/src/Z.sol", "a/foundry.toml", "a/src/A.sol", "src/R.sol")
    files = [root / "z/src/Z.sol", root / "src/R.sol", root / "a/src/A.sol"]
    assert list(group_by_module(files, root)) == [root, root / "a", root / "z"]


def test_group_files_within_module_are_sorted(root):
    touch(root, "src/C.sol", "src/A.sol", "src/B.sol")
    files = [root / "src/C.sol", root / "src/A.sol", root / "src/B.sol"]
    assert group_by_module(files, root)[root] == [root / f"src/{n}.sol" for n in "ABC"]


def test_group_files_without_marker_join_project_root_group(root):
    touch(root, "modA/foundry.toml", "modA/src/A.sol", "other/src/O.sol", "src/R.sol")
    files = [root / "other/src/O.sol", root / "src/R.sol", root / "modA/src/A.sol"]
    assert group_by_module(files, root) == {
        root: [root / "other/src/O.sol", root / "src/R.sol"],
        root / "modA": [root / "modA/src/A.sol"],
    }


# --- review follow-ups (M2/3) -----------------------------------------------------


def test_group_values_are_resolved(root):
    touch(root, "modA/foundry.toml", "modA/src/A.sol")
    got = group_by_module([root / "modA/src/../src/A.sol"], root)
    assert got == {root / "modA": [root / "modA/src/A.sol"]}


def test_group_dedupes_same_file_spelled_differently(root):
    touch(root, "src/A.sol")
    got = group_by_module([root / "src/A.sol", root / "src/./A.sol", root / "x/../src/A.sol"], root)
    assert got == {root: [root / "src/A.sol"]}


def test_file_outside_project_root_falls_back_to_project_root(root):
    touch(root.parent, "other/foundry.toml", "other/src/O.sol")
    assert module_root(root.parent / "other/src/O.sol", root) == root


def test_symlinked_file_groups_by_target_module(root):
    touch(root, "modA/foundry.toml", "modA/src/A.sol")
    (root / "src").mkdir()
    (root / "src/Link.sol").symlink_to(root / "modA/src/A.sol")
    assert module_root(root / "src/Link.sol", root) == root / "modA"
