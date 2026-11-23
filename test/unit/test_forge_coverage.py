"""T3.1-T3.2: forge coverage runner (spec §7, §14).

API under test: crap4sol.forge.run_coverage(module_root, runner=None)
  -> dict[str, FileCoverage] | None   (module-relative SF keys; None = all N/A)

`runner(argv, cwd)` is injected; it returns an object with `returncode`, `stdout`, `stderr`
(like subprocess.CompletedProcess). The default runner calls subprocess.
"""

import os
import subprocess
from pathlib import Path

import pytest

from crap4sol.errors import AnalysisError
from crap4sol.forge import run_coverage
from crap4sol.lcov import FileCoverage

LCOV = """\
TN:
SF:{sf}
DA:3,1
DA:4,0
end_of_record
"""


class FakeRunner:
    """Records calls; optionally writes an LCOV file like forge would."""

    def __init__(self, returncode=0, lcov_text=None, stdout="", stderr=""):
        self.returncode = returncode
        self.lcov_text = lcov_text
        self.stdout = stdout
        self.stderr = stderr
        self.calls = []
        self.lcov_existed_at_call = None

    def __call__(self, argv, cwd):
        self.calls.append((list(argv), Path(cwd)))
        report = Path(argv[argv.index("--report-file") + 1])
        self.lcov_existed_at_call = report.exists()
        if self.lcov_text is not None:
            report.write_text(self.lcov_text)
        return subprocess.CompletedProcess(argv, self.returncode, self.stdout, self.stderr)


@pytest.fixture
def module(tmp_path):
    m = tmp_path / "mod"
    m.mkdir()
    (m / "foundry.toml").write_text("[profile.default]\n")
    return m


# --- T3.1: invocation -------------------------------------------------------------------


def test_runs_forge_coverage_lcov_argv(module):
    fake = FakeRunner(lcov_text=LCOV.format(sf="src/A.sol"))
    run_coverage(module, runner=fake)
    argv, _ = fake.calls[0]
    assert argv == [
        "forge",
        "coverage",
        "--report",
        "lcov",
        "--report-file",
        str(module / "lcov.info"),
    ]


def test_runs_forge_in_module_root_cwd(module):
    fake = FakeRunner(lcov_text=LCOV.format(sf="src/A.sol"))
    run_coverage(module, runner=fake)
    _, cwd = fake.calls[0]
    assert cwd.resolve() == module.resolve()


def test_runs_forge_exactly_once_per_call(module):
    fake = FakeRunner(lcov_text=LCOV.format(sf="src/A.sol"))
    run_coverage(module, runner=fake)
    assert len(fake.calls) == 1


def test_deletes_stale_lcov_before_running(module):
    (module / "lcov.info").write_text(LCOV.format(sf="src/Stale.sol"))
    fake = FakeRunner(lcov_text=LCOV.format(sf="src/A.sol"))
    run_coverage(module, runner=fake)
    assert fake.lcov_existed_at_call is False


def test_returns_parsed_report_keyed_by_sf(module):
    fake = FakeRunner(lcov_text=LCOV.format(sf="src/A.sol"))
    report = run_coverage(module, runner=fake)
    assert report == {"src/A.sol": FileCoverage(lines={3: 1, 4: 0})}


def test_absolute_sf_normalized_to_module_relative(module):
    fake = FakeRunner(lcov_text=LCOV.format(sf=str(module / "src" / "A.sol")))
    report = run_coverage(module, runner=fake)
    assert list(report) == ["src/A.sol"]


# --- T3.2: errors -----------------------------------------------------------------------


def test_nonzero_exit_raises_analysis_error(module):
    fake = FakeRunner(returncode=1, lcov_text=None)
    with pytest.raises(AnalysisError):
        run_coverage(module, runner=fake)


def test_nonzero_exit_error_names_module_and_forge_stderr(module):
    fake = FakeRunner(returncode=1, stderr="Encountered 1 failing test")
    with pytest.raises(AnalysisError) as ei:
        run_coverage(module, runner=fake)
    msg = str(ei.value)
    assert "forge coverage" in msg
    assert str(module) in msg
    assert "Encountered 1 failing test" in msg


def test_nonzero_exit_fails_even_if_lcov_written(module):
    # failing tests may still leave a report behind; spec §7: fail fast regardless
    fake = FakeRunner(returncode=1, lcov_text=LCOV.format(sf="src/A.sol"))
    with pytest.raises(AnalysisError):
        run_coverage(module, runner=fake)


def test_stale_lcov_not_used_when_forge_fails(module):
    (module / "lcov.info").write_text(LCOV.format(sf="src/Stale.sol"))
    fake = FakeRunner(returncode=1)
    with pytest.raises(AnalysisError):
        run_coverage(module, runner=fake)
    assert not (module / "lcov.info").exists()


def test_forge_not_installed_raises_analysis_error(module):
    def missing(argv, cwd):
        raise FileNotFoundError(2, "No such file or directory", "forge")

    with pytest.raises(AnalysisError):
        run_coverage(module, runner=missing)


def test_runner_oserror_raises_analysis_error(module):
    def broken(argv, cwd):
        raise PermissionError(13, "Permission denied", "forge")

    with pytest.raises(AnalysisError):
        run_coverage(module, runner=broken)


def test_missing_lcov_after_success_returns_none(module):
    fake = FakeRunner(returncode=0, lcov_text=None)
    assert run_coverage(module, runner=fake) is None


def test_missing_lcov_after_success_warns_on_stderr(module, capsys):
    fake = FakeRunner(returncode=0, lcov_text=None)
    run_coverage(module, runner=fake)
    err = capsys.readouterr().err
    assert err.startswith("Warning:")
    assert str(module) in err


def test_empty_lcov_after_success_returns_none(module):
    fake = FakeRunner(returncode=0, lcov_text="")
    assert run_coverage(module, runner=fake) is None


def test_empty_lcov_after_success_warns_on_stderr(module, capsys):
    fake = FakeRunner(returncode=0, lcov_text="  \n")
    run_coverage(module, runner=fake)
    err = capsys.readouterr().err
    assert err.startswith("Warning:")
    assert str(module) in err


def test_present_lcov_emits_no_warning(module, capsys):
    fake = FakeRunner(lcov_text=LCOV.format(sf="src/A.sol"))
    run_coverage(module, runner=fake)
    assert capsys.readouterr().err == ""


STUB_FORGE = """#!/bin/sh
echo "Ran 3 tests (stub stdout)"
echo "stub stderr chatter" >&2
while [ $# -gt 0 ]; do
  if [ "$1" = "--report-file" ]; then shift; printf 'SF:src/A.sol\\nDA:3,1\\nend_of_record\\n' > "$1"; fi
  shift
done
exit 0
"""


@pytest.fixture
def stub_forge(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    forge = bin_dir / "forge"
    forge.write_text(STUB_FORGE)
    forge.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    return forge


def test_default_runner_uses_forge_on_path(module, stub_forge):
    report = run_coverage(module)
    assert report == {"src/A.sol": FileCoverage(lines={3: 1})}


def test_forge_stdout_not_leaked_to_stdout(module, stub_forge, capfd):
    # the report table owns stdout; forge's chatter must not interleave with it
    run_coverage(module)
    assert "Ran 3 tests" not in capfd.readouterr().out


def test_forge_stderr_not_leaked_on_success(module, stub_forge, capfd):
    run_coverage(module)
    assert "stub stderr chatter" not in capfd.readouterr().err


# --- review follow-ups ------------------------------------------------------------------


def test_relative_module_root_reads_report_forge_wrote(tmp_path, module, monkeypatch):
    # forge runs with cwd=module and resolves a relative --report-file against that cwd
    class CwdRunner(FakeRunner):
        def __call__(self, argv, cwd):
            self.calls.append((list(argv), Path(cwd)))
            report = Path(cwd) / argv[argv.index("--report-file") + 1]
            report.write_text(self.lcov_text)
            return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.chdir(tmp_path)
    fake = CwdRunner(lcov_text=LCOV.format(sf="src/A.sol"))
    report = run_coverage(Path("mod"), runner=fake)
    assert report == {"src/A.sol": FileCoverage(lines={3: 1, 4: 0})}


def test_relative_module_root_deletes_stale_lcov(tmp_path, module, monkeypatch):
    (module / "lcov.info").write_text(LCOV.format(sf="src/Stale.sol"))
    monkeypatch.chdir(tmp_path)
    fake = FakeRunner(returncode=1)
    with pytest.raises(AnalysisError):
        run_coverage(Path("mod"), runner=fake)
    assert not (module / "lcov.info").exists()


def test_bytes_stderr_decoded_in_error(module):
    fake = FakeRunner(returncode=1, stderr=b"\xff boom")
    with pytest.raises(AnalysisError) as ei:
        run_coverage(module, runner=fake)
    msg = str(ei.value)
    assert "boom" in msg
    assert "b'" not in msg


def test_failing_tests_reported_on_stdout_appear_in_error(module):
    # forge prints failing tests on stdout and may leave stderr empty
    fake = FakeRunner(returncode=1, stdout="[FAIL: assertion failed] test_x() (gas: 1)", stderr="")
    with pytest.raises(AnalysisError) as ei:
        run_coverage(module, runner=fake)
    assert "[FAIL: assertion failed] test_x()" in str(ei.value)


def test_undeletable_stale_lcov_raises_before_running(module):
    (module / "lcov.info").mkdir()
    fake = FakeRunner(lcov_text=LCOV.format(sf="src/A.sol"))
    with pytest.raises(AnalysisError):
        run_coverage(module, runner=fake)
    assert fake.calls == []


def test_runner_oserror_message_names_forge_and_module(module):
    def missing(argv, cwd):
        raise FileNotFoundError(2, "No such file or directory", "forge")

    with pytest.raises(AnalysisError) as ei:
        run_coverage(module, runner=missing)
    assert "forge coverage" in str(ei.value)
    assert str(module) in str(ei.value)


def test_malformed_lcov_raises_analysis_error(module):
    fake = FakeRunner(lcov_text="SF:src/A.sol\nDA:x,1\nend_of_record\n")
    with pytest.raises(AnalysisError):
        run_coverage(module, runner=fake)


def test_default_runner_missing_forge_raises_analysis_error(module, monkeypatch):
    monkeypatch.setenv("PATH", str(module))  # no forge on PATH
    with pytest.raises(AnalysisError):
        run_coverage(module)


# --- round-2 review follow-ups ----------------------------------------------------------


def test_error_includes_stdout_fail_lines_even_with_stderr_noise(module):
    # routine compiler warnings on stderr must not hide the [FAIL] lines forge prints on stdout
    fake = FakeRunner(
        returncode=1,
        stdout="[FAIL: assertion failed] test_x() (gas: 1)",
        stderr="Warning: unused variable",
    )
    with pytest.raises(AnalysisError) as ei:
        run_coverage(module, runner=fake)
    msg = str(ei.value)
    assert "[FAIL: assertion failed] test_x()" in msg
    assert "Warning: unused variable" in msg


def test_lcov_without_sf_records_returns_none(module):
    fake = FakeRunner(lcov_text="TN:\n")
    assert run_coverage(module, runner=fake) is None


def test_lcov_without_sf_records_warns_on_stderr(module, capsys):
    fake = FakeRunner(lcov_text="TN:\n")
    run_coverage(module, runner=fake)
    err = capsys.readouterr().err
    assert err.startswith("Warning:")
    assert str(module) in err


FAILING_STUB_FORGE = """#!/bin/sh
echo "[FAIL: boom] test_stub() (gas: 1)"
exit 1
"""


def test_default_runner_nonzero_exit_raises_with_forge_output(module, tmp_path, monkeypatch):
    bin_dir = tmp_path / "failbin"
    bin_dir.mkdir()
    forge = bin_dir / "forge"
    forge.write_text(FAILING_STUB_FORGE)
    forge.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    with pytest.raises(AnalysisError) as ei:
        run_coverage(module)
    assert "[FAIL: boom] test_stub()" in str(ei.value)
