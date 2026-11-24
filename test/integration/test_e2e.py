"""T4.6: end-to-end on the foundry-sample fixture with real forge + Slither (spec §4-§13, §16).

Drives crap4sol.cli.main(argv) with the real adapters (no injection), cwd = a tmp copy of the
fixture, plus the installed `crap4sol` console script for real process exit codes.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from crap4sol.cli import main

FIXTURE = Path(__file__).parent.parent / "fixtures" / "foundry-sample"

pytestmark = pytest.mark.e2e

VAULT_ROWS = {
    ("classify(uint256)", "Vault", "function", 5),
    ("constructor()", "Vault", "constructor", 1),
    ("deposit(uint256)", "Vault", "function", 1),
    ("fallback()", "Vault", "fallback", 1),
    ("hook()", "Vault", "function", 1),
    ("onlyOwner()", "Vault", "modifier", 1),
    ("receive()", "Vault", "receive", 1),
    ("set(uint256)", "Vault", "function", 1),
    ("set(uint256,uint256)", "Vault", "function", 1),
}
BASE_ROWS = {("baseHelper()", "Base", "function", 1)}
FREE_ROWS = {("clamp(uint256,uint256)", "src/MathLib.sol", "free", 2)}


def call(argv) -> int:
    try:
        return main(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1


def rows(out: str) -> list[tuple[str, str, str, int, str, str]]:
    """Parse the report table: (signature, contract, kind, cc, cov, crap) per data row."""
    lines = out.splitlines()
    seps = [i for i, l in enumerate(lines) if re.fullmatch(r"[- ]+", l) and "-" in l]
    assert seps, f"no report table in stdout: {out!r}"
    sep = seps[0]
    parsed = []
    for line in lines[sep + 1 :]:
        if not line.strip():
            continue
        sig, contract, kind, cc, cov, crap = re.split(r"\s{2,}", line.strip())
        parsed.append((sig, contract, kind, int(cc), cov, crap))
    return parsed


def ident(r):
    return r[:4]


@pytest.fixture
def sample(tmp_path, monkeypatch):
    dst = tmp_path / "foundry-sample"
    shutil.copytree(FIXTURE, dst, ignore=shutil.ignore_patterns("out", "cache", "lcov.info"))
    monkeypatch.chdir(dst)
    return dst


@pytest.fixture(scope="module")
def default_run(tmp_path_factory):
    """One full default run, shared by the read-only assertions (forge is slow)."""
    dst = tmp_path_factory.mktemp("e2e") / "foundry-sample"
    shutil.copytree(FIXTURE, dst, ignore=shutil.ignore_patterns("out", "cache", "lcov.info"))
    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(dst)
        cap = _Capture()
        mp.setattr(sys, "stdout", cap.out)
        mp.setattr(sys, "stderr", cap.err)
        code = call([])
    return code, cap.out.getvalue(), cap.err.getvalue()


class _Capture:
    def __init__(self):
        import io

        self.out = io.StringIO()
        self.err = io.StringIO()


# --- default run ----------------------------------------------------------------------


def test_default_run_exits_two(default_run):
    code, _, _ = default_run
    assert code == 2


def test_default_run_reports_threshold_on_stderr(default_run):
    _, _, err = default_run
    assert "CRAP threshold exceeded: 30.0 > 8.0" in err


def test_default_run_rows_are_exactly_the_src_callables(default_run):
    # interface members, lib/, test/, script/ and inherited duplicates are absent
    _, out, _ = default_run
    got = [ident(r) for r in rows(out)]
    assert sorted(got) == sorted(VAULT_ROWS | BASE_ROWS | FREE_ROWS)


def test_default_run_worst_row_is_uncovered_branchy_fn(default_run):
    _, out, _ = default_run
    first = rows(out)[0]
    assert ident(first) == ("classify(uint256)", "Vault", "function", 5)
    assert first[4:] == ("0.0%", "30.00")


def test_default_run_full_row_order(default_run):
    # CRAP desc, then ties by contract, then signature (spec §11)
    _, out, _ = default_run
    assert [(r[0], r[1]) for r in rows(out)] == [
        ("classify(uint256)", "Vault"),
        ("clamp(uint256,uint256)", "src/MathLib.sol"),
        ("baseHelper()", "Base"),
        ("fallback()", "Vault"),
        ("hook()", "Vault"),
        ("onlyOwner()", "Vault"),
        ("receive()", "Vault"),
        ("set(uint256,uint256)", "Vault"),
        ("constructor()", "Vault"),
        ("deposit(uint256)", "Vault"),
        ("set(uint256)", "Vault"),
    ]


def test_default_run_covered_fn_is_low_crap(default_run):
    _, out, _ = default_run
    deposit = next(r for r in rows(out) if r[0] == "deposit(uint256)")
    assert deposit[4:] == ("100.0%", "1.00")


def test_default_run_table_has_spec_columns(default_run):
    _, out, _ = default_run
    header = re.split(r"\s{2,}", out.splitlines()[0].strip())
    assert header == ["Function", "Contract", "Kind", "CC", "Cov%", "CRAP"]


# --- explicit paths -------------------------------------------------------------------


def test_explicit_file_path_limits_rows_and_passes(sample, capsys):
    assert call(["src/MathLib.sol"]) == 0
    out, err = capsys.readouterr()
    assert {ident(r) for r in rows(out)} == FREE_ROWS
    assert "CRAP threshold exceeded" not in err


def test_explicit_dir_path_expands_to_its_src(sample, capsys):
    assert call(["."]) == 2
    out, _ = capsys.readouterr()
    assert {ident(r) for r in rows(out)} == VAULT_ROWS | BASE_ROWS | FREE_ROWS


def test_explicit_interface_only_file_gives_empty_table_exit_zero(sample, capsys):
    assert call(["src/IVault.sol"]) == 0
    assert rows(capsys.readouterr().out) == []


# --- --changed ------------------------------------------------------------------------


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(sample):
    _git(sample, "init", "-q")
    _git(sample, "add", "-A")
    _git(sample, "commit", "-q", "-m", "init")
    return sample


def test_changed_analyzes_only_modified_file(repo, capsys):
    base = repo / "src" / "Base.sol"
    base.write_text(base.read_text() + "\n// touched\n")
    assert call(["--changed"]) == 0
    assert {ident(r) for r in rows(capsys.readouterr().out)} == BASE_ROWS


def test_changed_with_clean_tree_is_empty_selection(repo, capsys):
    assert call(["--changed"]) == 0
    assert capsys.readouterr().out.strip() == "No Solidity files to analyze."


def test_changed_ignores_changed_test_files(repo, capsys):
    t = repo / "test" / "Vault.t.sol"
    t.write_text(t.read_text() + "\n// touched\n")
    assert call(["--changed"]) == 0
    assert capsys.readouterr().out.strip() == "No Solidity files to analyze."


def test_changed_includes_untracked_new_file(repo, capsys):
    (repo / "src" / "Extra.sol").write_text(
        "// SPDX-License-Identifier: MIT\n"
        "pragma solidity ^0.8.20;\n"
        "contract Extra {\n"
        "    function ping() external pure returns (uint256) { return 1; }\n"
        "}\n"
    )
    assert call(["--changed"]) == 0
    assert {ident(r) for r in rows(capsys.readouterr().out)} == {
        ("ping()", "Extra", "function", 1)
    }


# --- nested module --------------------------------------------------------------------

NESTED_SRC = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Counter {
    uint256 public n;

    function inc() external {
        n += 1;
    }

    function pick(uint256 x) external pure returns (uint256 r) {
        if (x > 1) {
            r = 2;
        } else {
            r = 1;
        }
    }
}
"""

NESTED_TEST = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Counter} from "../src/Counter.sol";

contract CounterTest {
    function test_inc() public {
        Counter c = new Counter();
        c.inc();
        require(c.n() == 1, "n");
    }
}
"""


@pytest.fixture
def nested(sample):
    pkg = sample / "pkg"
    (pkg / "src").mkdir(parents=True)
    (pkg / "test").mkdir()
    shutil.copy(sample / "foundry.toml", pkg / "foundry.toml")
    (pkg / "src" / "Counter.sol").write_text(NESTED_SRC)
    (pkg / "test" / "Counter.t.sol").write_text(NESTED_TEST)
    return pkg


def test_nested_module_gets_its_own_coverage(nested, capsys):
    # pkg/ is its own Foundry module: forge runs there and its LCOV is attributed to its rows
    assert call(["pkg"]) == 0
    got = {(r[0], r[1]): r[4] for r in rows(capsys.readouterr().out)}
    assert got == {("inc()", "Counter"): "100.0%", ("pick(uint256)", "Counter"): "0.0%"}


def test_nested_module_out_dir_is_cleaned(nested, capsys):
    # issue #5: forge clean runs per module, in the nested module's root too
    (nested / "out").mkdir()
    (nested / "out" / "stale-marker.txt").write_text("stale")
    assert call(["pkg"]) == 0
    assert not (nested / "out" / "stale-marker.txt").exists()


def test_root_and_nested_modules_report_together(nested, capsys):
    assert call([".", "pkg"]) == 2
    got = {ident(r) for r in rows(capsys.readouterr().out)}
    assert got == VAULT_ROWS | BASE_ROWS | FREE_ROWS | {
        ("inc()", "Counter", "function", 1),
        ("pick(uint256)", "Counter", "function", 2),
    }


# --- failures -------------------------------------------------------------------------


def test_failing_forge_test_exits_three_without_table(sample, capsys):
    (sample / "test" / "Fail.t.sol").write_text(
        "// SPDX-License-Identifier: MIT\n"
        "pragma solidity ^0.8.20;\n"
        "contract FailTest {\n"
        "    function test_fails() public pure { require(false, \"boom\"); }\n"
        "}\n"
    )
    assert call([]) == 3
    out, err = capsys.readouterr()
    assert "forge coverage failed" in err
    assert err.startswith("crap4sol: ")
    assert out == ""


def test_compile_error_exits_three(sample, capsys):
    (sample / "src" / "Broken.sol").write_text("pragma solidity ^0.8.20;\ncontract Broken {\n")
    assert call([]) == 3
    out, err = capsys.readouterr()
    assert "Traceback" not in err
    assert err.startswith("crap4sol: ")
    assert out == ""


def test_compile_error_names_forge_build(sample, capsys):
    # issue #5: forge build runs before forge coverage, so a compile error fails at build
    (sample / "src" / "Broken.sol").write_text("pragma solidity ^0.8.20;\ncontract Broken {\n")
    assert call([]) == 3
    _, err = capsys.readouterr()
    assert "forge build failed" in err


def test_run_cleans_stale_build_artifacts(sample, capsys):
    # issue #5: forge clean runs first, wiping out/ and clearing forge's build cache
    (sample / "out").mkdir(exist_ok=True)
    (sample / "out" / "stale-marker.txt").write_text("stale")
    (sample / "cache").mkdir(exist_ok=True)
    stale_cache = sample / "cache" / "solidity-files-cache.json"
    stale_cache.write_text('{"stale": true}')
    assert call([]) == 2  # sample breaches the threshold; the run itself succeeded
    assert not (sample / "out" / "stale-marker.txt").exists()
    assert not stale_cache.exists() or stale_cache.read_text() != '{"stale": true}'


# --- console script -------------------------------------------------------------------


def _script() -> str:
    exe = Path(sys.executable).parent / "crap4sol"
    assert exe.exists(), exe
    return str(exe)


def test_console_script_help_exits_zero(sample):
    proc = subprocess.run([_script(), "--help"], cwd=sample, capture_output=True, text=True)
    assert proc.returncode == 0
    assert "usage:" in proc.stdout.lower()


def test_console_script_branch_exits_one(sample):
    proc = subprocess.run(
        [_script(), "--coverage", "branch"], cwd=sample, capture_output=True, text=True
    )
    assert proc.returncode == 1
    assert proc.stderr.strip() == "Branch coverage not implemented yet."


def test_console_script_default_run_exits_two(sample):
    proc = subprocess.run([_script()], cwd=sample, capture_output=True, text=True)
    assert proc.returncode == 2
    assert proc.stdout.splitlines()[0].startswith("Function")
