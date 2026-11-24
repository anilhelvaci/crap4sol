"""Issue #6 (optional part): `uninstall.sh [dir]` removes the crap4sol symlink only if it
points to this checkout's `bin/crap4sol`."""

import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LAUNCHER = REPO / "bin" / "crap4sol"
UNINSTALL = REPO / "uninstall.sh"


def run(argv, cwd, env=None, timeout=60):
    return subprocess.run(
        [str(a) for a in argv], cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
    )


@pytest.fixture
def env(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    return {**os.environ, "HOME": str(home)}


def uninstall(target, cwd, env, timeout=60):
    return run([UNINSTALL] if target is None else [UNINSTALL, target], cwd, env, timeout)


def test_uninstall_is_committed_executable():
    out = subprocess.run(
        ["git", "ls-files", "-s", "uninstall.sh"], cwd=REPO, capture_output=True, text=True
    ).stdout
    assert out.startswith("100755 "), out


def test_uninstall_removes_link_to_this_launcher(tmp_path, env):
    link = tmp_path / "bin" / "crap4sol"
    link.parent.mkdir()
    link.symlink_to(LAUNCHER)
    p = uninstall(tmp_path / "bin", tmp_path, env)
    assert p.returncode == 0, p.stderr
    assert not link.is_symlink() and not link.exists()
    assert LAUNCHER.is_file()  # the launcher itself is untouched


def test_uninstall_defaults_to_home_local_bin(tmp_path, env):
    link = Path(env["HOME"]) / ".local" / "bin" / "crap4sol"
    link.parent.mkdir(parents=True)
    link.symlink_to(LAUNCHER)
    p = uninstall(None, tmp_path, env)
    assert p.returncode == 0, p.stderr
    assert not link.is_symlink()


def test_uninstall_removes_relative_link_to_this_launcher(tmp_path, env):
    # "points to" means resolves to, not string-equal
    link = tmp_path / "bin" / "crap4sol"
    link.parent.mkdir()
    link.symlink_to(os.path.relpath(LAUNCHER, link.parent))
    p = uninstall(tmp_path / "bin", tmp_path, env)
    assert p.returncode == 0, p.stderr
    assert not link.is_symlink()


def test_uninstall_keeps_link_to_other_launcher(tmp_path, env):
    other = tmp_path / "other" / "crap4sol"
    other.parent.mkdir()
    other.write_text("#!/bin/sh\n")
    link = tmp_path / "bin" / "crap4sol"
    link.parent.mkdir()
    link.symlink_to(other)
    p = uninstall(tmp_path / "bin", tmp_path, env)
    assert p.returncode == 1
    assert link.is_symlink() and link.resolve() == other.resolve()
    assert str(link) in p.stdout + p.stderr


def test_uninstall_keeps_regular_file(tmp_path, env):
    f = tmp_path / "bin" / "crap4sol"
    f.parent.mkdir()
    f.write_text("keep me\n")
    p = uninstall(tmp_path / "bin", tmp_path, env)
    assert p.returncode == 1
    assert f.read_text() == "keep me\n"


def test_uninstall_nothing_installed_is_ok(tmp_path, env):
    (tmp_path / "bin").mkdir()
    p = uninstall(tmp_path / "bin", tmp_path, env)
    assert p.returncode == 0, p.stderr


def test_uninstall_twice_second_is_noop_success(tmp_path, env):
    link = tmp_path / "bin" / "crap4sol"
    link.parent.mkdir()
    link.symlink_to(LAUNCHER)
    assert uninstall(tmp_path / "bin", tmp_path, env).returncode == 0
    p = uninstall(tmp_path / "bin", tmp_path, env)
    assert p.returncode == 0, p.stderr
    assert LAUNCHER.is_file()


def test_uninstall_keeps_dangling_link(tmp_path, env):
    # a link to a deleted file is not provably ours
    link = tmp_path / "bin" / "crap4sol"
    link.parent.mkdir()
    link.symlink_to(tmp_path / "gone" / "crap4sol")
    p = uninstall(tmp_path / "bin", tmp_path, env)
    assert p.returncode == 1
    assert link.is_symlink()


def test_uninstall_cyclic_link_terminates_and_keeps_it(tmp_path, env):
    # attack: crap4sol -> crap4sol; link resolution must not loop forever
    link = tmp_path / "bin" / "crap4sol"
    link.parent.mkdir()
    link.symlink_to("crap4sol")
    p = uninstall(tmp_path / "bin", tmp_path, env, timeout=15)
    assert p.returncode == 1
    assert link.is_symlink()
    assert str(link) in p.stdout + p.stderr


def test_uninstall_trailing_slash_target(tmp_path, env):
    link = tmp_path / "bin" / "crap4sol"
    link.parent.mkdir()
    link.symlink_to(LAUNCHER)
    p = uninstall(f"{tmp_path / 'bin'}//", tmp_path, env)
    assert p.returncode == 0, p.stderr
    assert not link.is_symlink()


def test_uninstall_relative_invocation_ignores_cdpath(tmp_path, env):
    (tmp_path / "decoy" / REPO.name / "bin").mkdir(parents=True)
    link = tmp_path / "bin" / "crap4sol"
    link.parent.mkdir()
    link.symlink_to(LAUNCHER)
    e = {**env, "CDPATH": str(tmp_path / "decoy")}
    p = run(["sh", f"{REPO.name}/uninstall.sh", tmp_path / "bin"], REPO.parent, e)
    assert p.returncode == 0, p.stderr
    assert not link.is_symlink()
