"""T3.3-T3.6: fixture project, Slither load, callable collection and exclusions (spec §8, §14).

API under test: crap4sol.callables.collect_callables(module_root, files) -> list[Callable]
  - module_root: Foundry module root (Path); Slither(module_root) is loaded once per call.
  - files: selected .sol files (absolute Paths) under module_root.
  - Callable.file is the module-relative POSIX path (same key space as LCOV SF, spec §9.1).
  - Compile/load failure -> AnalysisError (spec §14).

The fixture is copied to a tmp dir so forge/Slither build artifacts never land in the repo.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from crap4sol.callables import collect_callables
from crap4sol.errors import AnalysisError

FIXTURE = Path(__file__).parent.parent / "fixtures" / "foundry-sample"

pytestmark = pytest.mark.slither


@pytest.fixture(scope="module")
def sample(tmp_path_factory):
    dst = tmp_path_factory.mktemp("fx") / "foundry-sample"
    shutil.copytree(FIXTURE, dst)
    return dst


def src(root, *names):
    return [root / "src" / n for n in names]


ALL_SRC = ("Vault.sol", "Base.sol", "IVault.sol", "MathLib.sol")


@pytest.fixture(scope="module")
def all_callables(sample):
    return collect_callables(sample, src(sample, *ALL_SRC))


def ids(callables):
    return {(c.contract, c.signature) for c in callables}


# --- T3.3: fixture --------------------------------------------------------------------


@pytest.mark.e2e
def test_fixture_forge_tests_pass(sample):
    proc = subprocess.run(["forge", "test"], cwd=sample, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


# --- T3.5: collection -----------------------------------------------------------------


def test_collects_vault_declared_callables(all_callables):
    vault = {s for c, s in ids(all_callables) if c == "Vault"}
    assert vault == {
        "constructor()",
        "receive()",
        "fallback()",
        "onlyOwner()",
        "deposit(uint256)",
        "classify(uint256)",
        "set(uint256)",
        "set(uint256,uint256)",
        "hook()",
    }


def test_overloads_are_separate_rows(all_callables):
    sets = [c for c in all_callables if c.contract == "Vault" and c.signature.startswith("set(")]
    assert len(sets) == 2


def test_collects_free_function(all_callables):
    free = [c for c in all_callables if c.signature == "clamp(uint256,uint256)"]
    assert len(free) == 1
    assert free[0].file == "src/MathLib.sol"


def test_inherited_callable_only_under_declarer(all_callables):
    helpers = [c for c in all_callables if c.signature == "baseHelper()"]
    assert [(c.contract, c.file) for c in helpers] == [("Base", "src/Base.sol")]


def test_no_duplicate_rows(all_callables):
    keys = [(c.file, c.contract, c.signature) for c in all_callables]
    assert len(keys) == len(set(keys))


def test_file_is_module_relative_posix(all_callables):
    assert {c.file for c in all_callables} == {"src/Vault.sol", "src/Base.sol", "src/MathLib.sol"}


def test_only_selected_files_collected(sample):
    got = collect_callables(sample, src(sample, "Vault.sol"))
    assert {c.file for c in got} == {"src/Vault.sol"}


def test_imported_free_function_not_collected_unless_its_file_selected(sample):
    got = collect_callables(sample, src(sample, "Vault.sol"))
    assert "clamp(uint256,uint256)" not in {c.signature for c in got}


def test_inherited_callable_not_collected_from_unselected_base(sample):
    got = collect_callables(sample, src(sample, "Vault.sol"))
    assert "baseHelper()" not in {c.signature for c in got}


def test_relative_file_paths_accepted(sample, monkeypatch):
    monkeypatch.chdir(sample)
    got = collect_callables(sample, [Path("src/MathLib.sol")])
    assert [c.signature for c in got] == ["clamp(uint256,uint256)"]


def test_empty_selection_returns_empty(sample):
    assert collect_callables(sample, []) == []


# --- T3.6: exclusions -----------------------------------------------------------------


def test_interface_members_excluded(sample):
    assert collect_callables(sample, src(sample, "IVault.sol")) == []


def test_abstract_declaration_excluded(all_callables):
    assert ("Base", "hook()") not in ids(all_callables)


def test_slither_synthesized_constructors_excluded(all_callables):
    assert not [c for c in all_callables if c.signature.startswith("slitherConstructor")]


# --- T3.4: load failures --------------------------------------------------------------


@pytest.fixture
def broken(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "foundry.toml").write_text('[profile.default]\nsolc_version = "0.8.39"\n')
    (tmp_path / "src" / "X.sol").write_text("pragma solidity ^0.8.20;\ncontract X {\n")
    return tmp_path


def test_compile_failure_raises_analysis_error(broken):
    with pytest.raises(AnalysisError):
        collect_callables(broken, [broken / "src" / "X.sol"])


def test_compile_failure_error_names_module(broken):
    with pytest.raises(AnalysisError) as ei:
        collect_callables(broken, [broken / "src" / "X.sol"])
    assert str(broken) in str(ei.value)


def test_missing_module_root_raises_analysis_error(tmp_path):
    missing = tmp_path / "nope"
    with pytest.raises(AnalysisError):
        collect_callables(missing, [missing / "src" / "X.sol"])
