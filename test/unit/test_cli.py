"""T4.1-T4.5: CLI parsing, branch rejection, empty selection, orchestration, error mapping
(spec §4-§14).

API under test:
  crap4sol.cli.main(argv=None, *, run_coverage=None, collect_callables=None) -> int
    - project root = current working directory.
    - argv None -> sys.argv[1:].
    - returns the exit code (spec §13). A SystemExit carrying the code is also accepted
      by these tests (argparse --help), see `call()`.
    - run_coverage(module_root: Path) -> dict[str, FileCoverage] | None
        default: crap4sol.forge.run_coverage
    - collect_callables(module_root: Path, files: list[Path]) -> list[Callable]
        default: crap4sol.callables.collect_callables
    - table (report.render of report.sort_metrics) on stdout; warnings/errors on stderr.
"""

from pathlib import Path

import pytest

from crap4sol.cli import main
from crap4sol.errors import AnalysisError
from crap4sol.lcov import FileCoverage
from crap4sol.metrics import Callable, Kind, Metric, crap
from crap4sol.report import render, sort_metrics

BRANCH_MSG = "Branch coverage not implemented yet."
EMPTY_MSG = "No Solidity files to analyze."


def call(argv, **kw) -> int:
    try:
        return main(argv, **kw)
    except SystemExit as e:  # argparse may exit directly
        return e.code if isinstance(e.code, int) else 1


class Recorder:
    """Fake adapters that log calls in order and return canned data per module root."""

    def __init__(self, reports=None, callables=None, cov_error=None, collect_error=None):
        self.reports = reports or {}
        self.callables = callables or {}
        self.cov_error = cov_error  # {module_root: exc}
        self.collect_error = collect_error
        self.log = []

    def run_coverage(self, module_root):
        root = Path(module_root).resolve()
        self.log.append(("coverage", root))
        if self.cov_error and root in self.cov_error:
            raise self.cov_error[root]
        return self.reports.get(root)

    def collect_callables(self, module_root, files):
        root = Path(module_root).resolve()
        self.log.append(("collect", root, sorted(Path(f).resolve() for f in files)))
        if self.collect_error and root in self.collect_error:
            raise self.collect_error[root]
        return self.callables.get(root, [])

    @property
    def kw(self):
        return {"run_coverage": self.run_coverage, "collect_callables": self.collect_callables}


def touch(p: Path, text="// SPDX-License-Identifier: MIT\n") -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


@pytest.fixture
def project(tmp_path, monkeypatch):
    """Project root (cwd) that is itself a Foundry module with src/A.sol."""
    root = tmp_path / "proj"
    touch(root / "foundry.toml", "[profile.default]\n")
    touch(root / "src" / "A.sol")
    monkeypatch.chdir(root)
    return root.resolve()


@pytest.fixture
def empty_project(tmp_path, monkeypatch):
    root = tmp_path / "empty"
    touch(root / "foundry.toml", "[profile.default]\n")
    (root / "src").mkdir()
    monkeypatch.chdir(root)
    return root.resolve()


def fn(contract, sig, cc, file="src/A.sol", start=1, end=10, kind=Kind.FUNCTION):
    return Callable(contract, sig, kind, file, start, end, cc)


def cov(**lines):
    """FileCoverage from l<N>=hits keyword args."""
    return FileCoverage(lines={int(k[1:]): v for k, v in lines.items()})


# --- T4.1: argparse -------------------------------------------------------------------


def test_help_exits_zero(project):
    rec = Recorder()
    assert call(["--help"], **rec.kw) == 0


def test_help_prints_usage_to_stdout(project, capsys):
    call(["--help"], **Recorder().kw)
    assert "usage:" in capsys.readouterr().out.lower()


def test_help_runs_no_analysis(project):
    rec = Recorder()
    call(["--help"], **rec.kw)
    assert rec.log == []


def test_unknown_flag_exits_one(project):
    assert call(["--bogus"], **Recorder().kw) == 1


def test_unknown_flag_prints_usage_to_stderr(project, capsys):
    call(["--bogus"], **Recorder().kw)
    assert "usage:" in capsys.readouterr().err.lower()


def test_unknown_flag_runs_no_analysis(project):
    rec = Recorder()
    call(["--bogus"], **rec.kw)
    assert rec.log == []


def test_invalid_coverage_value_exits_one(project):
    assert call(["--coverage", "statement"], **Recorder().kw) == 1


def test_invalid_coverage_value_prints_usage_to_stderr(project, capsys):
    call(["--coverage", "statement"], **Recorder().kw)
    assert "usage:" in capsys.readouterr().err.lower()


def test_coverage_flag_without_value_exits_one(project):
    assert call(["--coverage"], **Recorder().kw) == 1


def test_changed_with_paths_is_usage_error(project, capsys):
    # spec §4 synopsis: --changed and <path...> are alternative forms
    rec = Recorder()
    assert call(["--changed", "src/A.sol"], **rec.kw) == 1
    assert "usage:" in capsys.readouterr().err.lower()
    assert rec.log == []


def test_coverage_line_is_accepted(project):
    rec = Recorder(callables={project: [fn("A", "f()", 1)]})
    assert call(["--coverage", "line"], **rec.kw) == 0
    assert ("coverage", project) in rec.log


def test_coverage_line_equals_form_is_accepted(project):
    rec = Recorder(callables={project: [fn("A", "f()", 1)]})
    assert call(["--coverage=line"], **rec.kw) == 0


def test_argv_none_reads_sys_argv(project, monkeypatch):
    monkeypatch.setattr("sys.argv", ["crap4sol", "--bogus"])
    assert call(None, **Recorder().kw) == 1


# --- T4.2: branch rejected in phase 1 -------------------------------------------------


def test_coverage_branch_exits_one(project):
    assert call(["--coverage", "branch"], **Recorder().kw) == 1


def test_coverage_branch_prints_not_implemented_to_stderr(project, capsys):
    call(["--coverage", "branch"], **Recorder().kw)
    out, err = capsys.readouterr()
    assert err.strip() == BRANCH_MSG
    assert out == ""


def test_coverage_branch_runs_no_analysis(project):
    rec = Recorder()
    call(["--coverage", "branch"], **rec.kw)
    assert rec.log == []


def test_coverage_branch_rejected_even_with_empty_selection(empty_project, capsys):
    assert call(["--coverage", "branch"], **Recorder().kw) == 1
    assert capsys.readouterr().err.strip() == BRANCH_MSG


# --- T4.3: empty selection ------------------------------------------------------------


def test_empty_selection_exits_zero(empty_project):
    assert call([], **Recorder().kw) == 0


def test_empty_selection_prints_message_to_stdout(empty_project, capsys):
    call([], **Recorder().kw)
    assert capsys.readouterr().out.strip() == EMPTY_MSG


def test_empty_selection_runs_no_analysis(empty_project):
    rec = Recorder()
    call([], **rec.kw)
    assert rec.log == []


def test_only_excluded_explicit_paths_is_empty_selection(project, capsys):
    touch(project / "src" / "A.t.sol")
    rec = Recorder()
    assert call(["src/A.t.sol"], **rec.kw) == 0
    assert capsys.readouterr().out.strip() == EMPTY_MSG
    assert rec.log == []


def test_nonexistent_explicit_path_warns_and_is_empty_selection(project, capsys):
    rec = Recorder()
    assert call(["src/Nope.sol"], **rec.kw) == 0
    out, err = capsys.readouterr()
    assert out.strip() == EMPTY_MSG
    assert "src/Nope.sol" in err
    assert rec.log == []


# --- T4.4: orchestration --------------------------------------------------------------


def test_default_selection_runs_coverage_then_collect_for_module(project):
    rec = Recorder(callables={project: [fn("A", "f()", 1)]})
    call([], **rec.kw)
    assert rec.log == [
        ("coverage", project),
        ("collect", project, [project / "src" / "A.sol"]),
    ]


def test_collect_receives_only_the_selected_files(project):
    touch(project / "src" / "B.sol")
    rec = Recorder()
    call(["src/B.sol"], **rec.kw)
    assert rec.log[-1] == ("collect", project, [project / "src" / "B.sol"])


@pytest.fixture
def two_modules(project):
    """project (root module, src/A.sol) + nested module pkg/ (pkg/src/B.sol)."""
    pkg = project / "pkg"
    touch(pkg / "foundry.toml", "[profile.default]\n")
    touch(pkg / "src" / "B.sol")
    return project, pkg.resolve()


def test_each_module_gets_one_coverage_and_one_collect(two_modules):
    root, pkg = two_modules
    rec = Recorder()
    call([".", "pkg"], **rec.kw)
    assert sorted(e for e in rec.log if e[0] == "coverage") == sorted(
        [("coverage", root), ("coverage", pkg)]
    )
    assert ("collect", root, [root / "src" / "A.sol"]) in rec.log
    assert ("collect", pkg, [pkg / "src" / "B.sol"]) in rec.log
    assert len(rec.log) == 4


def test_coverage_runs_before_collect_in_each_module(two_modules):
    rec = Recorder()
    call([".", "pkg"], **rec.kw)
    for mod in two_modules:
        steps = [e[0] for e in rec.log if e[1] == mod]
        assert steps == ["coverage", "collect"]


def test_report_merges_modules_sorted_worst_first(two_modules, capsys):
    root, pkg = two_modules
    a = fn("A", "low()", 1, file="src/A.sol", start=1, end=3)
    b = fn("B", "high()", 2, file="src/B.sol", start=1, end=3)
    rec = Recorder(
        reports={root: {"src/A.sol": cov(l2=1)}, pkg: {"src/B.sol": cov(l2=0)}},
        callables={root: [a], pkg: [b]},
    )
    call([".", "pkg"], **rec.kw)
    expected = render(sort_metrics([Metric(a, 1.0, crap(1, 1.0)), Metric(b, 0.0, crap(2, 0.0))]))
    assert capsys.readouterr().out == expected


def test_coverage_is_attributed_per_module_report(two_modules, capsys):
    # same module-relative file key in both modules: each callable must use its own module's LCOV
    root, pkg = two_modules
    a = fn("A", "f()", 1, file="src/X.sol", start=1, end=3)
    b = fn("B", "g()", 1, file="src/X.sol", start=1, end=3)
    rec = Recorder(
        reports={root: {"src/X.sol": cov(l2=1)}, pkg: {"src/X.sol": cov(l2=0)}},
        callables={root: [a], pkg: [b]},
    )
    call([".", "pkg"], **rec.kw)
    expected = render(sort_metrics([Metric(a, 1.0, crap(1, 1.0)), Metric(b, 0.0, crap(1, 0.0))]))
    assert capsys.readouterr().out == expected


def test_partial_line_coverage_flows_into_crap(project, capsys):
    c = fn("A", "f()", 2, start=1, end=4)
    rec = Recorder(reports={project: {"src/A.sol": cov(l2=3, l3=0)}}, callables={project: [c]})
    call([], **rec.kw)
    assert capsys.readouterr().out == render([Metric(c, 0.5, crap(2, 0.5))])


def test_no_lcov_report_gives_na_rows_and_exit_zero(project, capsys):
    c = fn("A", "branchy()", 20)
    rec = Recorder(reports={project: None}, callables={project: [c]})
    assert call([], **rec.kw) == 0
    assert capsys.readouterr().out == render([Metric(c, None, None)])


def test_threshold_exceeded_exits_two(project):
    c = fn("A", "f()", 3, start=1, end=3)
    rec = Recorder(reports={project: {"src/A.sol": cov(l2=0)}}, callables={project: [c]})
    assert call([], **rec.kw) == 2


def test_threshold_exceeded_message_on_stderr(project, capsys):
    c = fn("A", "f()", 3, start=1, end=3)  # CRAP = 9 + 3 = 12.0
    rec = Recorder(reports={project: {"src/A.sol": cov(l2=0)}}, callables={project: [c]})
    call([], **rec.kw)
    out, err = capsys.readouterr()
    assert err.strip() == "CRAP threshold exceeded: 12.0 > 8.0"
    assert out == render([Metric(c, 0.0, 12.0)])


def test_crap_exactly_at_threshold_exits_zero(project, capsys):
    c = fn("A", "f()", 8, start=1, end=3)  # covered: CRAP = CC = 8.0
    rec = Recorder(reports={project: {"src/A.sol": cov(l2=1)}}, callables={project: [c]})
    assert call([], **rec.kw) == 0
    assert capsys.readouterr().err == ""


def test_threshold_uses_max_across_modules(two_modules):
    root, pkg = two_modules
    ok = fn("A", "f()", 1, file="src/A.sol", start=1, end=3)
    bad = fn("B", "g()", 3, file="src/B.sol", start=1, end=3)
    rec = Recorder(
        reports={root: {"src/A.sol": cov(l2=1)}, pkg: {"src/B.sol": cov(l2=0)}},
        callables={root: [ok], pkg: [bad]},
    )
    assert call([".", "pkg"], **rec.kw) == 2


def test_no_callables_prints_header_only_table_exit_zero(project, capsys):
    rec = Recorder(callables={project: []})
    assert call([], **rec.kw) == 0
    assert capsys.readouterr().out == render([])


# --- T4.5: error mapping --------------------------------------------------------------


def test_coverage_analysis_error_exits_three(project):
    rec = Recorder(cov_error={project: AnalysisError("forge coverage failed: boom")})
    assert call([], **rec.kw) == 3


def test_coverage_analysis_error_message_on_stderr_no_table(project, capsys):
    rec = Recorder(cov_error={project: AnalysisError("forge coverage failed: boom")})
    call([], **rec.kw)
    out, err = capsys.readouterr()
    assert "forge coverage failed: boom" in err
    assert out == ""


def test_coverage_failure_skips_collect(project):
    # fail fast (spec §7, §14): no Slither run after forge failed
    rec = Recorder(cov_error={project: AnalysisError("boom")})
    call([], **rec.kw)
    assert [e[0] for e in rec.log] == ["coverage"]


def test_failure_in_first_module_stops_other_modules(two_modules):
    root, pkg = two_modules
    rec = Recorder(cov_error={root: AnalysisError("boom"), pkg: AnalysisError("boom")})
    assert call([".", "pkg"], **rec.kw) == 3
    assert len(rec.log) == 1


def test_collect_analysis_error_exits_three(project, capsys):
    rec = Recorder(collect_error={project: AnalysisError("Slither failed for module x")})
    assert call([], **rec.kw) == 3
    out, err = capsys.readouterr()
    assert "Slither failed for module x" in err
    assert out == ""


def test_oserror_exits_three(project, capsys):
    rec = Recorder(collect_error={project: PermissionError(13, "Permission denied", "src/A.sol")})
    assert call([], **rec.kw) == 3
    out, err = capsys.readouterr()
    assert "Permission denied" in err
    assert out == ""


def test_analysis_error_beats_threshold(two_modules, capsys):
    # a failure anywhere is exit 3 even if an earlier module already exceeded the threshold
    root, pkg = two_modules
    bad = fn("A", "f()", 3, file="src/A.sol", start=1, end=3)
    rec = Recorder(
        reports={root: {"src/A.sol": cov(l2=0)}},
        callables={root: [bad]},
        cov_error={pkg: AnalysisError("boom")},
    )
    assert call([".", "pkg"], **rec.kw) == 3
    assert "CRAP threshold exceeded" not in capsys.readouterr().err


def test_changed_outside_git_repo_exits_three(project, capsys, monkeypatch):
    # git status fails -> AnalysisError from selection -> exit 3, no traceback
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(project.parent))
    rec = Recorder()
    assert call(["--changed"], **rec.kw) == 3
    err = capsys.readouterr().err
    assert "git" in err
    assert "Traceback" not in err
    assert rec.log == []


# --- review follow-ups: exit codes without the call() helper, unexpected failures -------


def test_main_returns_one_for_bad_flag_without_raising(project):
    # console script does sys.exit(main()): main itself must return the code
    assert main(["--bogus"], **Recorder().kw) == 1


def test_main_returns_zero_for_help_without_raising(project):
    assert main(["--help"], **Recorder().kw) == 0


def test_explicit_symlink_loop_path_exits_three(project, capsys):
    # unreadable source path (spec §14): Path.resolve raises RuntimeError on py3.12
    (project / "src" / "Loop.sol").symlink_to("Loop.sol")
    rec = Recorder()
    assert call(["src/Loop.sol"], **rec.kw) == 3
    out, err = capsys.readouterr()
    assert "Loop.sol" in err
    assert "Traceback" not in err
    assert out == ""
    assert rec.log == []


def test_unexpected_collector_exception_exits_three(project, capsys):
    # an analyzer crash (e.g. IndexError on odd Slither source mapping) is an analysis failure,
    # never exit 1 (which means usage error)
    rec = Recorder(collect_error={project: IndexError("list index out of range")})
    assert call([], **rec.kw) == 3
    out, err = capsys.readouterr()
    assert "list index out of range" in err
    assert out == ""


def test_unexpected_coverage_exception_exits_three(project, capsys):
    rec = Recorder(cov_error={project: RuntimeError("weird forge state")})
    assert call([], **rec.kw) == 3
    out, err = capsys.readouterr()
    assert "weird forge state" in err
    assert out == ""


def test_unexpected_exception_still_fails_fast(two_modules):
    root, pkg = two_modules
    rec = Recorder(cov_error={root: RuntimeError("x"), pkg: RuntimeError("x")})
    call([".", "pkg"], **rec.kw)
    assert len(rec.log) == 1
