"""Real console script with unwritable stdout/stderr (review round 4).

The report (or the empty-selection message) that cannot be delivered is an I/O failure:
exit 3, never 1/120, and no interpreter 'Exception ignored' noise at shutdown.
Pipes are made with os.pipe() and the read end is closed before spawning, so the write
always hits EPIPE (no race with a `head` process).
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest


def _script() -> str:
    exe = Path(sys.executable).parent / "crap4sol"
    assert exe.exists(), exe
    return str(exe)


@pytest.fixture
def empty_dir(tmp_path):
    # no src/: empty selection, so the tool writes "No Solidity files to analyze." to stdout
    return tmp_path


def _closed_pipe_fd() -> int:
    r, w = os.pipe()
    os.close(r)
    return w


def test_stdout_closed_pipe_exits_three(empty_dir):
    w = _closed_pipe_fd()
    try:
        proc = subprocess.run([_script()], cwd=empty_dir, stdout=w, stderr=subprocess.PIPE)
    finally:
        os.close(w)
    assert proc.returncode == 3, proc.stderr


def test_stdout_closed_pipe_no_exception_ignored(empty_dir):
    w = _closed_pipe_fd()
    try:
        proc = subprocess.run(
            [_script()], cwd=empty_dir, stdout=w, stderr=subprocess.PIPE, text=True
        )
    finally:
        os.close(w)
    assert "Exception ignored" not in proc.stderr
    assert "Traceback" not in proc.stderr
    assert "cannot write report" in proc.stderr


def test_stdout_and_stderr_closed_pipe_exits_three(empty_dir):
    # `crap4sol 2>&1 | head -c0`
    w = _closed_pipe_fd()
    try:
        proc = subprocess.run([_script()], cwd=empty_dir, stdout=w, stderr=w)
    finally:
        os.close(w)
    assert proc.returncode == 3


@pytest.mark.skipif(not os.path.exists("/dev/full"), reason="needs /dev/full")
def test_stdout_dev_full_exits_three(empty_dir):
    with open("/dev/full", "w") as full:
        proc = subprocess.run(
            [_script()], cwd=empty_dir, stdout=full, stderr=subprocess.PIPE, text=True
        )
    assert proc.returncode == 3, proc.stderr


@pytest.mark.skipif(not os.path.exists("/dev/full"), reason="needs /dev/full")
def test_stdout_dev_full_no_exception_ignored(empty_dir):
    with open("/dev/full", "w") as full:
        proc = subprocess.run(
            [_script()], cwd=empty_dir, stdout=full, stderr=subprocess.PIPE, text=True
        )
    assert "Exception ignored" not in proc.stderr
    assert "Traceback" not in proc.stderr
    assert "cannot write report" in proc.stderr


def test_healthy_streams_empty_selection_exits_zero(empty_dir):
    proc = subprocess.run([_script()], cwd=empty_dir, capture_output=True, text=True)
    assert proc.returncode == 0
    assert proc.stdout == "No Solidity files to analyze.\n"


# --- review round 5: fds closed at start ------------------------------------------------


def _sh(cmd: str, cwd, **env):
    """Run `crap4sol` through sh so redirections like `>&-` close fds before exec."""
    e = {**os.environ, **env}
    return subprocess.run(
        ["sh", "-c", cmd.replace("crap4sol", f'"{_script()}"', 1)],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=e,
    )


def test_stdout_closed_fd_exits_three(empty_dir):
    proc = _sh("crap4sol >&-", empty_dir)
    assert proc.returncode == 3, proc.stderr
    assert "Traceback" not in proc.stderr


def test_stderr_closed_fd_analysis_error_exits_three(empty_dir):
    # --changed outside a git repo -> analysis failure, with fd 2 closed
    (empty_dir / "src").mkdir()
    (empty_dir / "src" / "A.sol").write_text("// x\n")
    proc = _sh(
        "crap4sol --changed 2>&-", empty_dir, GIT_CEILING_DIRECTORIES=str(empty_dir.parent)
    )
    assert proc.returncode == 3


def test_help_into_closed_pipe_exits_three(empty_dir):
    w = _closed_pipe_fd()
    try:
        proc = subprocess.run(
            [_script(), "--help"], cwd=empty_dir, stdout=w, stderr=subprocess.PIPE, text=True
        )
    finally:
        os.close(w)
    assert proc.returncode == 3, proc.stderr
    assert "Exception ignored" not in proc.stderr
