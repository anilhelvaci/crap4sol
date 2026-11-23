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
from crap4sol.metrics import Kind

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
    with pytest.raises(AnalysisError) as ei:
        collect_callables(missing, [missing / "src" / "X.sol"])
    assert str(missing) in str(ei.value)


# --- T3.7: kind, identity -------------------------------------------------------------


def one(callables, contract, signature):
    [c] = [c for c in callables if (c.contract, c.signature) == (contract, signature)]
    return c


@pytest.mark.parametrize(
    "signature,kind",
    [
        ("constructor()", Kind.CONSTRUCTOR),
        ("receive()", Kind.RECEIVE),
        ("fallback()", Kind.FALLBACK),
        ("onlyOwner()", Kind.MODIFIER),
        ("deposit(uint256)", Kind.FUNCTION),
        ("set(uint256,uint256)", Kind.FUNCTION),
    ],
)
def test_vault_kind(all_callables, signature, kind):
    assert one(all_callables, "Vault", signature).kind is kind


def test_free_function_kind_is_free(all_callables):
    assert one(all_callables, "src/MathLib.sol", "clamp(uint256,uint256)").kind is Kind.FREE


def test_free_function_contract_is_module_relative_file(all_callables):
    # spec §8 "<file> for free functions": the file's module-relative path, not a literal
    [c] = [c for c in all_callables if c.signature == "clamp(uint256,uint256)"]
    assert c.contract == "src/MathLib.sol"


# --- T3.8: line range, CC -------------------------------------------------------------


@pytest.mark.parametrize(
    "contract,signature,start,end",
    [
        ("Vault", "onlyOwner()", 13, 16),
        ("Vault", "constructor()", 18, 20),
        ("Vault", "receive()", 22, 22),
        ("Vault", "deposit(uint256)", 26, 28),
        ("Vault", "classify(uint256)", 30, 45),
        ("Vault", "set(uint256)", 47, 49),
        ("Vault", "set(uint256,uint256)", 51, 53),
        ("Base", "baseHelper()", 7, 9),
        ("src/MathLib.sol", "clamp(uint256,uint256)", 4, 10),
    ],
)
def test_line_range(all_callables, contract, signature, start, end):
    c = one(all_callables, contract, signature)
    assert (c.start_line, c.end_line) == (start, end)


@pytest.mark.parametrize(
    "contract,signature,cc",
    [
        ("Vault", "classify(uint256)", 5),  # if/else-if/else + for + inner if/else
        ("src/MathLib.sol", "clamp(uint256,uint256)", 2),  # one if/else
        ("Vault", "deposit(uint256)", 1),  # straight line
        ("Vault", "receive()", 1),  # empty body: CFG E-N+2 clamps to >= 1
        ("Vault", "onlyOwner()", 1),  # require is not counted (spec §8.1 limitation)
        ("Base", "baseHelper()", 1),
    ],
)
def test_cyclomatic_complexity(all_callables, contract, signature, cc):
    assert one(all_callables, contract, signature).cc == cc


# --- symlinked source -----------------------------------------------------------------


@pytest.fixture(scope="module")
def linked(tmp_path_factory):
    """Module whose src/Shared.sol is a symlink to a file outside the module root."""
    base = tmp_path_factory.mktemp("sym")
    shutil.copytree(FIXTURE, base / "m")
    (base / "shared").mkdir()
    (base / "shared" / "Shared.sol").write_text(
        "// SPDX-License-Identifier: MIT\npragma solidity ^0.8.20;\n\n"
        "contract Shared {\n    function s() external pure returns (uint256) {\n"
        "        return 2;\n    }\n}\n"
    )
    (base / "m" / "src" / "Shared.sol").symlink_to(Path("../../shared/Shared.sol"))
    return base / "m"


def test_symlinked_source_keyed_by_in_module_path(linked):
    # forge's LCOV reports SF:src/Shared.sol; the row must join on the same key
    got = collect_callables(linked, [linked / "src" / "Shared.sol"])
    assert [(c.contract, c.signature, c.file) for c in got] == [("Shared", "s()", "src/Shared.sol")]


def test_symlinked_source_selected_by_resolved_path(linked):
    # module grouping hands over resolved paths (modules.group_by_module)
    got = collect_callables(linked, [(linked / "src" / "Shared.sol").resolve()])
    assert [(c.signature, c.file) for c in got] == [("s()", "src/Shared.sol")]


# --- T3.9: multiple compilation units -------------------------------------------------

MULTI = FIXTURE.parent / "foundry-multi-cu"


@pytest.fixture(scope="module")
def multi(tmp_path_factory):
    dst = tmp_path_factory.mktemp("mcu") / "m"
    shutil.copytree(MULTI, dst)
    return dst


@pytest.fixture(scope="module")
def multi_callables(multi):
    return collect_callables(multi, src(multi, "MathLib.sol", "Old.sol", "New.sol"))


def test_multi_cu_fixture_has_two_compilation_units(multi):
    from slither import Slither

    assert len(Slither(str(multi)).compilation_units) == 2


def test_multi_cu_shared_free_function_one_row(multi_callables):
    assert [c.signature for c in multi_callables].count("clamp(uint256,uint256)") == 1


def test_multi_cu_collects_each_unit(multi_callables):
    assert ids(multi_callables) == {
        ("Old", "o(uint256)"),
        ("New", "n(uint256)"),
        ("src/MathLib.sol", "clamp(uint256,uint256)"),
        ("Bits", "low(uint256)"),
    }


def test_library_member_is_function_under_library_name(multi_callables):
    c = one(multi_callables, "Bits", "low(uint256)")
    assert (c.kind, c.file) == (Kind.FUNCTION, "src/MathLib.sol")


def test_contract_seen_by_two_units_one_row(multi_callables):
    # Bits is compiled into both units; its member must not be reported twice
    assert [c.signature for c in multi_callables].count("low(uint256)") == 1
