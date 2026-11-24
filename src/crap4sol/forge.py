"""Forge coverage runner (spec §7)."""

import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from crap4sol.errors import AnalysisError
from crap4sol.lcov import FileCoverage, load_lcov, normalize_report

Runner = Callable[[Sequence[str], Path], subprocess.CompletedProcess]


def _subprocess_runner(argv: Sequence[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run argv in cwd, capturing output so forge's chatter never reaches our stdout."""
    return subprocess.run(list(argv), cwd=cwd, capture_output=True, check=False)


def _text(out: str | bytes | None) -> str:
    if isinstance(out, bytes):
        return out.decode("utf-8", errors="replace")
    return out or ""


def _run_step(argv: Sequence[str], root: Path, runner: Runner) -> None:
    """Run one forge step in root; AnalysisError naming the step on failure."""
    step = " ".join(argv[:2])
    try:
        proc = runner(argv, root)
    except OSError as exc:
        raise AnalysisError(f"{step} failed in {root}: {exc}") from exc
    if proc.returncode != 0:
        # forge reports failing tests on stdout; stderr may hold only compiler noise
        out = (_text(proc.stderr).strip(), _text(proc.stdout).strip())
        err = "\n".join(part for part in out if part)
        raise AnalysisError(f"{step} failed in {root} (exit {proc.returncode}): {err}")


def run_coverage(
    module_root: Path, runner: Runner | None = None
) -> dict[str, FileCoverage] | None:
    """Run `forge clean`, `forge build`, then `forge coverage` in module_root and
    return the LCOV report keyed by module-relative SF; None (with a stderr warning) if no report was produced."""
    # absolute so forge (run with cwd=root) writes the report where we read it
    root = Path(module_root).absolute()
    report_file = root / "lcov.info"
    try:
        report_file.unlink(missing_ok=True)
    except OSError as exc:
        raise AnalysisError(f"{report_file}: cannot delete stale LCOV: {exc}") from exc

    # clean first so stale out/ and cache/ artifacts can't leak into the build (issue #5)
    coverage_argv = ["forge", "coverage", "--report", "lcov", "--report-file", str(report_file)]
    for argv in (["forge", "clean"], ["forge", "build"], coverage_argv):
        _run_step(argv, root, runner or _subprocess_runner)

    report = load_lcov(report_file)
    if not report:  # missing, empty, or no SF records
        print(
            f"Warning: {os.fspath(report_file)} missing or empty after forge coverage in "
            f"{root}; coverage N/A for this module",
            file=sys.stderr,
        )
        return None
    return normalize_report(report, root)
