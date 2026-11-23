"""T2.1-T2.3: default selection, exclusions, explicit paths (spec §4, §5).

Contract (crap4sol.selection):
  select_default(project_root: Path) -> list[Path]
  select_paths(project_root: Path, paths: list[str]) -> list[Path]
Both return absolute, resolved file paths, deduplicated and sorted.
Exclusions (§5) are matched on path components relative to the project root.
"""

from pathlib import Path

import pytest

from crap4sol.selection import select_default, select_paths


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path.resolve()


def touch(root: Path, *rels: str) -> None:
    for rel in rels:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("// x\n")


def rels(root: Path, paths: list[Path]) -> list[str]:
    return [p.relative_to(root).as_posix() for p in paths]


# --- T2.1 default selection ---------------------------------------------------


def test_default_selects_sol_files_under_src_recursively_sorted(root):
    touch(root, "src/b/Deep.sol", "src/A.sol", "src/b/C.sol")
    assert rels(root, select_default(root)) == ["src/A.sol", "src/b/C.sol", "src/b/Deep.sol"]


def test_default_returns_absolute_paths(root):
    touch(root, "src/A.sol")
    assert select_default(root) == [root / "src/A.sol"]


def test_default_ignores_non_sol_files_under_src(root):
    touch(root, "src/A.sol", "src/README.md", "src/A.sol.bak", "src/x.json")
    assert rels(root, select_default(root)) == ["src/A.sol"]


def test_default_ignores_sol_files_outside_src(root):
    touch(root, "src/A.sol", "Root.sol", "contracts/B.sol")
    assert rels(root, select_default(root)) == ["src/A.sol"]


def test_default_without_src_dir_selects_nothing(root):
    touch(root, "contracts/B.sol")
    assert select_default(root) == []


def test_default_ignores_directories_named_like_sol_files(root):
    (root / "src/Weird.sol").mkdir(parents=True)
    touch(root, "src/Weird.sol/Inner.sol")
    assert rels(root, select_default(root)) == ["src/Weird.sol/Inner.sol"]


# --- T2.2 exclusions ----------------------------------------------------------


def test_default_excludes_t_sol_files(root):
    touch(root, "src/A.sol", "src/A.t.sol")
    assert rels(root, select_default(root)) == ["src/A.sol"]


def test_default_excludes_s_sol_files(root):
    touch(root, "src/A.sol", "src/Deploy.s.sol")
    assert rels(root, select_default(root)) == ["src/A.sol"]


@pytest.mark.parametrize("excluded_dir", ["lib", "test", "script", "node_modules"])
def test_default_excludes_files_under_excluded_dir_inside_src(root, excluded_dir):
    touch(root, "src/A.sol", f"src/{excluded_dir}/X.sol")
    assert rels(root, select_default(root)) == ["src/A.sol"]


def test_exclusion_matches_whole_dir_name_not_substring(root):
    touch(root, "src/libs/X.sol", "src/testing/Y.sol", "src/mylib/Z.sol")
    assert rels(root, select_default(root)) == [
        "src/libs/X.sol",
        "src/mylib/Z.sol",
        "src/testing/Y.sol",
    ]


def test_exclusion_ignores_dirs_above_project_root(tmp_path):
    # Project root itself lives under a directory named `test`: that must not exclude it.
    root = (tmp_path / "test" / "lib" / "proj").resolve()
    touch(root, "src/A.sol")
    assert rels(root, select_default(root)) == ["src/A.sol"]


def test_sol_suffix_inside_name_is_not_t_sol(root):
    # `Gadget.sol` ends in `t.sol` but not `.t.sol`.
    touch(root, "src/Gadget.sol", "src/Uses.sol")
    assert rels(root, select_default(root)) == ["src/Gadget.sol", "src/Uses.sol"]


@pytest.mark.parametrize(
    "rel",
    ["lib/forge-std/src/Test.sol", "test/Foo.sol", "script/Deploy.sol", "node_modules/x/A.sol"],
)
def test_explicit_file_under_excluded_dir_is_excluded(root, rel):
    touch(root, rel)
    assert select_paths(root, [rel]) == []


@pytest.mark.parametrize("rel", ["src/A.t.sol", "src/Deploy.s.sol"])
def test_explicit_test_or_script_file_is_excluded(root, rel):
    touch(root, rel)
    assert select_paths(root, [rel]) == []


def test_explicit_dir_expansion_applies_exclusions(root):
    touch(root, "modA/src/A.sol", "modA/src/A.t.sol", "modA/src/test/H.sol")
    assert rels(root, select_paths(root, ["modA"])) == ["modA/src/A.sol"]


# --- T2.3 explicit paths ------------------------------------------------------


def test_explicit_file_is_selected_directly_even_outside_src(root):
    touch(root, "contracts/B.sol")
    assert rels(root, select_paths(root, ["contracts/B.sol"])) == ["contracts/B.sol"]


def test_explicit_relative_path_resolves_against_project_root(root):
    touch(root, "src/A.sol")
    assert select_paths(root, ["src/A.sol"]) == [root / "src/A.sol"]


def test_explicit_absolute_file_path_is_accepted(root):
    touch(root, "src/A.sol")
    assert select_paths(root, [str(root / "src/A.sol")]) == [root / "src/A.sol"]


def test_explicit_dir_expands_to_sol_under_its_src_subtree(root):
    touch(root, "modA/src/A.sol", "modA/src/sub/B.sol")
    assert rels(root, select_paths(root, ["modA"])) == ["modA/src/A.sol", "modA/src/sub/B.sol"]


def test_explicit_dir_does_not_take_sol_outside_its_src(root):
    touch(root, "modA/Top.sol", "modA/contracts/C.sol", "modA/src/A.sol")
    assert rels(root, select_paths(root, ["modA"])) == ["modA/src/A.sol"]


def test_explicit_dir_without_src_selects_nothing(root):
    touch(root, "modA/Top.sol")
    assert select_paths(root, ["modA"]) == []


def test_explicit_dot_dir_expands_to_project_src(root):
    touch(root, "src/A.sol", "Root.sol")
    assert rels(root, select_paths(root, ["."])) == ["src/A.sol"]


def test_explicit_paths_are_sorted(root):
    touch(root, "src/Z.sol", "src/A.sol", "src/M.sol")
    got = select_paths(root, ["src/Z.sol", "src/A.sol", "src/M.sol"])
    assert rels(root, got) == ["src/A.sol", "src/M.sol", "src/Z.sol"]


def test_explicit_duplicate_file_is_deduped(root):
    touch(root, "src/A.sol")
    assert rels(root, select_paths(root, ["src/A.sol", "src/A.sol"])) == ["src/A.sol"]


def test_explicit_same_file_spelled_differently_is_deduped(root):
    touch(root, "src/A.sol")
    got = select_paths(root, ["src/A.sol", "./src/A.sol", "src/../src/A.sol"])
    assert rels(root, got) == ["src/A.sol"]


def test_explicit_file_and_its_dir_are_deduped(root):
    touch(root, "src/A.sol", "src/B.sol")
    got = select_paths(root, ["src/A.sol", "."])
    assert rels(root, got) == ["src/A.sol", "src/B.sol"]


# --- review round 1 -------------------------------------------------------------


@pytest.mark.parametrize("rel", ["README.md", "foundry.toml", "src/A.sol.bak"])
def test_explicit_non_sol_file_is_not_selected(root, rel):
    touch(root, rel)
    assert select_paths(root, [rel]) == []


def test_explicit_file_outside_project_root_is_not_selected(tmp_path):
    root = (tmp_path / "proj").resolve()
    touch(root, "src/A.sol")
    touch(tmp_path, "other/src/B.sol")
    assert select_paths(root, [str(tmp_path / "other/src/B.sol")]) == []


def test_explicit_dotdot_file_escaping_project_root_is_not_selected(tmp_path):
    root = (tmp_path / "proj").resolve()
    touch(tmp_path, "x/lib/A.sol", "x/src/B.sol")
    assert select_paths(root, ["../x/lib/A.sol", "../x/src/B.sol"]) == []


def test_explicit_dir_outside_project_root_selects_nothing(tmp_path):
    root = (tmp_path / "proj").resolve()
    touch(tmp_path, "other/src/B.sol")
    assert select_paths(root, [str(tmp_path / "other")]) == []


def test_default_skips_src_symlink_resolving_outside_project_root(tmp_path):
    root = (tmp_path / "proj").resolve()
    touch(root, "src/A.sol")
    touch(tmp_path, "outside/Y.sol")
    # A symlinked FILE (rglob yields it on every Python version) resolving outside the root.
    (root / "src/Ext.sol").symlink_to(tmp_path / "outside/Y.sol")
    assert rels(root, select_default(root)) == ["src/A.sol"]


def test_explicit_excluded_dir_selects_nothing(root):
    touch(root, "lib/forge-std/src/X.sol")
    assert select_paths(root, ["lib/forge-std"]) == []


def test_explicit_src_dir_expands_to_src_src_only(root):
    # §4: a directory expands to `<dir>/src/**`, so `src` means `src/src/**`.
    touch(root, "src/A.sol")
    assert select_paths(root, ["src"]) == []
