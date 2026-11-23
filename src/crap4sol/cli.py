"""Command-line entry point (spec §4-§14)."""

import argparse
import os
import sys
from collections.abc import Callable as Fn
from pathlib import Path
from typing import NoReturn

from crap4sol import forge, report, selection
from crap4sol.coverage import attribute
from crap4sol.errors import (
    EXIT_ANALYSIS_FAILURE,
    EXIT_SUCCESS,
    EXIT_USAGE,
    AnalysisError,
)
from crap4sol.lcov import FileCoverage
from crap4sol.metrics import Callable, Metric
from crap4sol.modules import group_by_module

BRANCH_MSG = "Branch coverage not implemented yet."
EMPTY_MSG = "No Solidity files to analyze."

CoverageFn = Fn[[Path], dict[str, FileCoverage] | None]
CollectFn = Fn[[Path, list[Path]], list[Callable]]


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        """Usage errors exit 1 (spec §13), not argparse's default 2."""
        _err(self.format_usage().rstrip("\n"))
        _err(f"{self.prog}: error: {message}")
        sys.exit(EXIT_USAGE)

    def print_help(self, file=None) -> None:
        """argparse swallows help write errors; route stdout help through _emit so an
        undeliverable --help surfaces as _Unwritable."""
        if file is None:
            _emit(self.format_help())
        else:
            super().print_help(file)


def _parser() -> _Parser:
    p = _Parser(prog="crap4sol", description="CRAP quality gate for Foundry Solidity projects.")
    p.add_argument("--coverage", choices=("line", "branch"), default="line",
                   help="coverage measure (default: line)")
    p.add_argument("--changed", action="store_true",
                   help="analyze changed .sol files under src/ (git status)")
    p.add_argument("paths", nargs="*", metavar="path",
                   help="file to analyze, or directory whose src/ is scanned")
    return p


def _select(root: Path, args: argparse.Namespace) -> list[Path]:
    if args.changed:
        return selection.select_changed(root)
    if args.paths:
        return selection.select_paths(root, args.paths)
    return selection.select_default(root)


def _default_collect(module_root: Path, files: list[Path]) -> list[Callable]:
    # Imported lazily: Slither calls sys.stdout.isatty() at import, which crashes when
    # stdout is closed (`crap4sol >&-`); inside the analysis try that is an exit 3.
    from crap4sol.callables import collect_callables

    return collect_callables(module_root, files)


def _analyze(
    root: Path, files: list[Path], run_coverage: CoverageFn, collect_callables: CollectFn
) -> list[Metric]:
    """Per module: coverage, then callables; fail fast on the first error (spec §6, §7)."""
    metrics: list[Metric] = []
    for module, module_files in group_by_module(files, root).items():
        lcov = run_coverage(module)
        metrics.extend(attribute(c, lcov) for c in collect_callables(module, module_files))
    return metrics


def _silence(stream) -> None:
    """Point the stream's fd at devnull so the interpreter's exit flush doesn't raise again
    (Python docs, signal module: note on SIGPIPE)."""
    try:
        fd = stream.fileno()
    except (AttributeError, OSError, ValueError):  # not backed by a real fd
        return
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, fd)
    finally:
        os.close(devnull)


class _Unwritable(Exception):
    """stdout could not take our output (closed fd, broken pipe, full disk)."""


def _emit(text: str) -> None:
    """Write to stdout and flush, so a write failure surfaces here rather than at exit."""
    if sys.stdout is None:  # fd 1 closed at startup (`crap4sol >&-`)
        raise _Unwritable("stdout is closed")
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
    except (OSError, ValueError) as exc:  # ValueError: write to a closed file object
        _silence(sys.stdout)
        raise _Unwritable(str(exc)) from exc


class _Stderr:
    """stderr that never raises: a diagnostic that cannot be written must not change the
    exit code (e.g. `crap4sol 2>&1 | head -c0`)."""

    def write(self, text: str) -> int:
        if sys.stderr is None:  # fd 2 closed at startup (`crap4sol 2>&-`)
            return len(text)
        try:
            sys.stderr.write(text)
            sys.stderr.flush()
        except (OSError, ValueError):
            _silence(sys.stderr)
        return len(text)


def _err(message: str) -> None:
    _Stderr().write(f"{message}\n")


def main(
    argv: list[str] | None = None,
    *,
    run_coverage: CoverageFn | None = None,
    collect_callables: CollectFn | None = None,
) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # --help (0) or usage error (1)
        return exc.code if isinstance(exc.code, int) else EXIT_USAGE
    except _Unwritable as exc:  # --help text not delivered: same rule as the report
        _err(f"crap4sol: cannot write help: {exc}")
        return EXIT_ANALYSIS_FAILURE
    if args.changed and args.paths:
        _err(parser.format_usage().rstrip("\n"))
        _err("crap4sol: error: --changed takes no paths")
        return EXIT_USAGE
    if args.coverage == "branch":
        _err(BRANCH_MSG)
        return EXIT_USAGE

    if sys.stdout is None:  # report can never be delivered: don't run forge/Slither for it
        _err("crap4sol: cannot write report: stdout is closed")
        return EXIT_ANALYSIS_FAILURE

    try:
        root = Path.cwd().resolve()
        files = _select(root, args)
        metrics: list[Metric] = []
        if files:
            metrics = _analyze(
                root,
                files,
                run_coverage or forge.run_coverage,
                collect_callables or _default_collect,
            )
            text = report.render(report.sort_metrics(metrics))
        else:
            text = EMPTY_MSG + "\n"
    except (AnalysisError, OSError) as exc:
        _err(f"crap4sol: {exc}")
        return EXIT_ANALYSIS_FAILURE
    except Exception as exc:  # analyzer crash or unresolvable path: never exit 1 (usage)
        _err(f"crap4sol: unexpected error: {type(exc).__name__}: {exc}")
        return EXIT_ANALYSIS_FAILURE

    try:
        _emit(text)
    except _Unwritable as exc:  # closed pipe, full disk: the output was not delivered
        _err(f"crap4sol: cannot write report: {exc}")
        return EXIT_ANALYSIS_FAILURE

    return report.check_threshold(metrics, _Stderr())
