"""T2.4-T2.5: `--changed` selection (spec §5).

Contract (crap4sol.selection):
  parse_porcelain(text: str) -> list[str]
      Paths from `git status --porcelain` (v1, non -z) output, in input order: modified (either
      column), added, untracked; renames/copies give the NEW path; deletions dropped. C-quoted
      paths are unquoted.
  select_changed(project_root: Path) -> list[Path]
      Runs git in project_root; keeps changed `.sol` files under `<project_root>/src/`, applies
      §5 exclusions; absolute, resolved, deduped, sorted. git failure -> AnalysisError.
"""

import os
import subprocess
from pathlib import Path

import pytest

from crap4sol.errors import AnalysisError
from crap4sol.selection import parse_porcelain, select_changed

# --- T2.4 porcelain parser ------------------------------------------------------


@pytest.mark.parametrize("code", [" M", "M ", "MM", "A ", "AM", "??"])
def test_parse_keeps_modified_added_untracked(code):
    assert parse_porcelain(f"{code} src/A.sol\n") == ["src/A.sol"]


@pytest.mark.parametrize("code", [" D", "D ", "AD", "MD"])
def test_parse_drops_deleted(code):
    assert parse_porcelain(f"{code} src/A.sol\n") == []


@pytest.mark.parametrize("code", ["R ", "RM"])
def test_parse_rename_gives_new_path(code):
    assert parse_porcelain(f"{code} src/Old.sol -> src/New.sol\n") == ["src/New.sol"]


def test_parse_copy_gives_new_path():
    assert parse_porcelain("C  src/A.sol -> src/B.sol\n") == ["src/B.sol"]


def test_parse_preserves_input_order_and_handles_many_lines():
    text = "?? src/Z.sol\n M src/A.sol\n D src/Gone.sol\nA  src/M.sol\n"
    assert parse_porcelain(text) == ["src/Z.sol", "src/A.sol", "src/M.sol"]


def test_parse_ignores_blank_lines_and_missing_trailing_newline():
    assert parse_porcelain("\n M src/A.sol\n\n?? src/B.sol") == ["src/A.sol", "src/B.sol"]


def test_parse_empty_output_is_empty():
    assert parse_porcelain("") == []


def test_parse_unquotes_path_with_space():
    assert parse_porcelain('?? "src/a b.sol"\n') == ["src/a b.sol"]


def test_parse_unquotes_octal_utf8_escapes():
    assert parse_porcelain('?? "src/\\303\\251.sol"\n') == ["src/é.sol"]


def test_parse_unquotes_backslash_and_quote_escapes():
    assert parse_porcelain('?? "src/a\\"b\\\\c.sol"\n') == ['src/a"b\\c.sol']


def test_parse_rename_with_quoted_new_path():
    assert parse_porcelain('R  src/Old.sol -> "src/n w.sol"\n') == ["src/n w.sol"]


def test_parse_rename_with_quoted_old_path_containing_arrow():
    assert parse_porcelain('R  "src/a -> b.sol" -> src/New.sol\n') == ["src/New.sol"]


# --- T2.5 real git in a tmp repo -----------------------------------------------

GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}


@pytest.fixture(autouse=True)
def isolated_git(monkeypatch):
    for k, v in GIT_ENV.items():
        monkeypatch.setenv(k, v)


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def write(root: Path, rel: str, text: str = "// x\n") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def rels(root: Path, paths: list[Path]) -> list[str]:
    return [p.relative_to(root).as_posix() for p in paths]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path.resolve() / "repo"
    root.mkdir()
    git(root, "init", "-q")
    for rel in ("src/A.sol", "src/B.sol", "src/Keep.sol", "Root.sol", "src/notes.md"):
        write(root, rel)
    git(root, "add", "-A")
    git(root, "commit", "-qm", "init")
    return root


def test_clean_repo_selects_nothing(repo):
    assert select_changed(repo) == []


def test_modified_tracked_file_is_selected(repo):
    write(repo, "src/A.sol", "// changed\n")
    assert rels(repo, select_changed(repo)) == ["src/A.sol"]


def test_staged_added_file_is_selected(repo):
    write(repo, "src/New.sol")
    git(repo, "add", "src/New.sol")
    assert rels(repo, select_changed(repo)) == ["src/New.sol"]


def test_untracked_file_is_selected(repo):
    write(repo, "src/New.sol")
    assert rels(repo, select_changed(repo)) == ["src/New.sol"]


def test_untracked_files_in_new_directory_are_selected(repo):
    # Plain `git status --porcelain` collapses these to `?? src/sub/`.
    write(repo, "src/sub/X.sol")
    write(repo, "src/sub/deeper/Y.sol")
    assert rels(repo, select_changed(repo)) == ["src/sub/X.sol", "src/sub/deeper/Y.sol"]


def test_deleted_file_is_not_selected(repo):
    (repo / "src/A.sol").unlink()
    assert select_changed(repo) == []


def test_renamed_file_gives_new_path_only(repo):
    git(repo, "mv", "src/A.sol", "src/Renamed.sol")
    assert rels(repo, select_changed(repo)) == ["src/Renamed.sol"]


def test_changed_sol_outside_src_is_not_selected(repo):
    write(repo, "Root.sol", "// changed\n")
    write(repo, "contracts/C.sol")
    write(repo, "modA/src/M.sol")
    assert select_changed(repo) == []


def test_changed_non_sol_file_is_not_selected(repo):
    write(repo, "src/notes.md", "changed\n")
    assert select_changed(repo) == []


@pytest.mark.parametrize("rel", ["src/A.t.sol", "src/Deploy.s.sol", "src/test/H.sol", "src/lib/L.sol"])
def test_changed_excluded_file_is_not_selected(repo, rel):
    write(repo, rel)
    assert select_changed(repo) == []


def test_changed_files_are_sorted_and_absolute(repo):
    # git lists tracked changes before untracked ones: B.sol (modified) precedes A2.sol (untracked).
    write(repo, "src/B.sol", "// changed\n")
    write(repo, "src/A2.sol")
    assert select_changed(repo) == [repo / "src/A2.sol", repo / "src/B.sol"]


def test_changed_path_with_space_is_selected(repo):
    write(repo, "src/a b.sol")
    assert select_changed(repo) == [repo / "src/a b.sol"]


def test_changed_non_ascii_path_is_selected(repo):
    write(repo, "src/é.sol")
    assert select_changed(repo) == [repo / "src/é.sol"]


def test_project_root_in_repo_subdir_selects_its_own_src(repo):
    # git prints paths relative to the repo top level, not the project root.
    proj = repo / "packages/proj"
    write(repo, "packages/proj/src/P.sol")
    write(repo, "packages/other/src/O.sol")
    write(repo, "src/A.sol", "// changed\n")
    assert rels(proj, select_changed(proj)) == ["src/P.sol"]


def test_not_a_git_repo_raises_analysis_error(tmp_path, monkeypatch):
    root = tmp_path.resolve() / "plain"
    write(root, "src/A.sol")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.resolve()))
    with pytest.raises(AnalysisError):
        select_changed(root)


# --- review follow-ups (M2/2) -----------------------------------------------------


@pytest.mark.parametrize("code", ["UU", "AA", "AU", "UA", " T", "T "])
def test_parse_keeps_unmerged_and_typechanged_files(code):
    # Unmerged (conflicted) and type-changed files still exist and count as modified.
    assert parse_porcelain(f"{code} src/A.sol\n") == ["src/A.sol"]


@pytest.mark.parametrize("code", ["DD", "DU", "UD"])
def test_parse_drops_unmerged_entries_with_a_deletion(code):
    assert parse_porcelain(f"{code} src/A.sol\n") == []


def _mkdir_or_skip(path: Path) -> None:
    try:
        path.mkdir()
    except OSError as exc:  # e.g. macOS APFS rejects non-UTF-8 names
        pytest.skip(f"filesystem rejects non-UTF-8 name: {exc}")


def _non_utf8(base: Path, name: bytes) -> Path:
    return Path(os.fsdecode(os.fsencode(str(base)) + b"/" + name))


def test_non_utf8_repo_path_still_selects_changed_files(tmp_path):
    # Linux paths are bytes; git output under such a root must not crash decoding.
    root = _non_utf8(tmp_path.resolve(), b"r\xff")
    _mkdir_or_skip(root)
    git(root, "init", "-q")
    write(root, "src/A.sol")
    assert select_changed(root) == [root / "src/A.sol"]


def test_missing_git_binary_raises_analysis_error(repo, monkeypatch):
    monkeypatch.setenv("PATH", "")
    with pytest.raises(AnalysisError):
        select_changed(repo)


def test_nonexistent_project_root_raises_analysis_error(tmp_path):
    with pytest.raises(AnalysisError):
        select_changed(tmp_path.resolve() / "nope")


# --- review follow-ups (M2/3) -----------------------------------------------------


def test_non_utf8_file_name_under_src_round_trips(repo):
    (repo / "src").mkdir(exist_ok=True)
    d = _non_utf8(repo / "src", b"d\xfe")
    _mkdir_or_skip(d)
    (d / "A.sol").write_text("// x\n")
    assert select_changed(repo) == [d / "A.sol"]


def test_repo_root_with_trailing_space_in_name(tmp_path):
    # `rev-parse --show-toplevel` output must lose only its newline, not the space.
    root = tmp_path.resolve() / "r "
    root.mkdir()
    git(root, "init", "-q")
    write(root, "src/A.sol")
    assert select_changed(root) == [root / "src/A.sol"]

