"""Command-line entry point (spec §4-§14)."""

import argparse
import os
import sys
from collections.abc import Callable as Fn
from pathlib import Path
from typing import NoReturn

from crap4sol import callables, forge, report, selection
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
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")


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


def _analyze(
    root: Path, files: list[Path], run_coverage: CoverageFn, collect_callables: CollectFn
) -> list[Metric]:
    """Per module: coverage, then callables; fail fast on the first error (spec §6, §7)."""
    metrics: list[Metric] = []
    for module, module_files in group_by_module(files, root).items():
        lcov = run_coverage(module)
        metrics.extend(attribute(c, lcov) for c in collect_callables(module, module_files))
    return metrics


def _emit(text: str) -> None:
    """Write to stdout and flush, so a broken pipe surfaces here rather than at exit."""
    sys.stdout.write(text)
    sys.stdout.flush()


def _silence_stdout() -> None:
    """Point the stdout fd at devnull so the interpreter's exit flush doesn't raise again
    (Python docs, signal module: note on SIGPIPE)."""
    try:
        fd = sys.stdout.fileno()
    except (AttributeError, OSError, ValueError):  # not backed by a real fd
        return
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, fd)
    finally:
        os.close(devnull)


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
    if args.changed and args.paths:
        parser.print_usage(sys.stderr)
        print("crap4sol: error: --changed takes no paths", file=sys.stderr)
        return EXIT_USAGE
    if args.coverage == "branch":
        print(BRANCH_MSG, file=sys.stderr)
        return EXIT_USAGE

    try:
        root = Path.cwd().resolve()
        files = _select(root, args)
        if not files:
            _emit(EMPTY_MSG + "\n")
            return EXIT_SUCCESS
        metrics = _analyze(
            root,
            files,
            run_coverage or forge.run_coverage,
            collect_callables or callables.collect_callables,
        )
        _emit(report.render(report.sort_metrics(metrics)))
    except BrokenPipeError as exc:  # stdout reader went away: the report was not delivered
        _silence_stdout()
        print(f"crap4sol: cannot write report: {exc}", file=sys.stderr)
        return EXIT_ANALYSIS_FAILURE
    except (AnalysisError, OSError) as exc:
        print(f"crap4sol: {exc}", file=sys.stderr)
        return EXIT_ANALYSIS_FAILURE
    except Exception as exc:  # analyzer crash or unresolvable path: never exit 1 (usage)
        print(f"crap4sol: unexpected error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_ANALYSIS_FAILURE

    return report.check_threshold(metrics, sys.stderr)
