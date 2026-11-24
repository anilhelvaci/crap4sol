"""Issue #6: `install.sh` symlinks `bin/crap4sol` into a PATH dir; the launcher runs crap4sol
from the checkout via `uv run --project`, keeping the caller's cwd and exit codes."""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LAUNCHER = REPO / "bin" / "crap4sol"
INSTALL = REPO / "install.sh"
FIXTURE = REPO / "test" / "fixtures" / "foundry-sample"
SYS_PATH = "/usr/bin:/bin"  # neither uv nor forge lives here

pytestmark = pytest.mark.skipif(shutil.which("uv") is None, reason="uv not on PATH")

# tests that hide uv/forge by restricting PATH to SYS_PATH are void if SYS_PATH has them
needs_bare_sys_path = pytest.mark.skipif(
    any(shutil.which(t, path=SYS_PATH) for t in ("uv", "forge")),
    reason=f"uv or forge found on {SYS_PATH}",
)


def run(argv, cwd, env=None, timeout=300):
    return subprocess.run(
        [str(a) for a in argv], cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
    )


def fake_bin(dir: Path, name: str, body: str) -> Path:
    dir.mkdir(parents=True, exist_ok=True)
    p = dir / name
    p.write_text(f"#!/bin/sh\n{body}\n")
    p.chmod(0o755)
    return p


@pytest.fixture
def env(tmp_path):
    """Env with a fake `uv` (logs argv) and fake `forge` first on PATH, HOME in tmp."""
    tools = tmp_path / "tools"
    log = tmp_path / "uv.log"
    fake_bin(tools, "uv", f'echo "$@" >> "{log}"')
    fake_bin(tools, "forge", "exit 0")
    home = tmp_path / "home"
    home.mkdir()
    e = {**os.environ, "HOME": str(home), "PATH": f"{tools}:{SYS_PATH}"}
    return e, log


def msgs(p, tmp_path) -> str:
    """stdout+stderr with tmp and repo paths masked (test names leak 'uv'/'forge'/'warn')."""
    return (p.stdout + p.stderr).replace(str(tmp_path), "<tmp>").replace(str(REPO), "<repo>")


def install(target, cwd, env):
    argv = [INSTALL] if target is None else [INSTALL, target]
    return run(argv, cwd, env)


# --- committed files -------------------------------------------------------------------


@pytest.mark.parametrize("path", ["bin/crap4sol", "install.sh"])
def test_script_is_committed_executable(path):
    out = subprocess.run(
        ["git", "ls-files", "-s", path], cwd=REPO, capture_output=True, text=True
    ).stdout
    assert out.startswith("100755 "), f"{path} not committed as executable: {out!r}"


# --- install.sh ------------------------------------------------------------------------


def test_install_creates_symlink_to_launcher(tmp_path, env):
    target = tmp_path / "bin"
    p = install(target, tmp_path, env[0])
    assert p.returncode == 0, p.stderr
    link = target / "crap4sol"
    assert link.is_symlink()
    assert link.resolve() == LAUNCHER.resolve()


def test_install_creates_missing_nested_target_dir(tmp_path, env):
    target = tmp_path / "a" / "b" / "bin"
    p = install(target, tmp_path, env[0])
    assert p.returncode == 0, p.stderr
    assert (target / "crap4sol").resolve() == LAUNCHER.resolve()


def test_install_defaults_to_home_local_bin(tmp_path, env):
    e, _ = env
    p = install(None, tmp_path, e)
    assert p.returncode == 0, p.stderr
    link = Path(e["HOME"]) / ".local" / "bin" / "crap4sol"
    assert link.is_symlink()
    assert link.resolve() == LAUNCHER.resolve()


def test_install_works_from_any_cwd(tmp_path, env):
    # repo root comes from the script's location, not the caller's cwd
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    p = install(tmp_path / "bin", elsewhere, env[0])
    assert p.returncode == 0, p.stderr
    assert (tmp_path / "bin" / "crap4sol").resolve() == LAUNCHER.resolve()


def test_install_rerun_is_idempotent(tmp_path, env):
    target = tmp_path / "bin"
    assert install(target, tmp_path, env[0]).returncode == 0
    p = install(target, tmp_path, env[0])
    assert p.returncode == 0, p.stderr
    assert (target / "crap4sol").resolve() == LAUNCHER.resolve()
    assert sorted(x.name for x in target.iterdir()) == ["crap4sol"]


def test_install_replaces_stale_symlink(tmp_path, env):
    # a symlink to an old checkout is ours to replace
    target = tmp_path / "bin"
    target.mkdir()
    old = fake_bin(tmp_path / "old", "crap4sol", "exit 0")
    (target / "crap4sol").symlink_to(old)
    p = install(target, tmp_path, env[0])
    assert p.returncode == 0, p.stderr
    assert (target / "crap4sol").resolve() == LAUNCHER.resolve()


def test_install_replaces_dangling_symlink(tmp_path, env):
    # old checkout deleted: the link is dangling but still ours to replace
    target = tmp_path / "bin"
    target.mkdir()
    (target / "crap4sol").symlink_to(tmp_path / "gone" / "crap4sol")
    p = install(target, tmp_path, env[0])
    assert p.returncode == 0, p.stderr
    assert (target / "crap4sol").resolve() == LAUNCHER.resolve()


def test_install_relative_target_resolves_against_cwd(tmp_path, env):
    cwd = tmp_path / "here"
    cwd.mkdir()
    p = install("rel/bin", cwd, env[0])
    assert p.returncode == 0, p.stderr
    link = cwd / "rel" / "bin" / "crap4sol"
    assert link.is_symlink()
    assert link.resolve() == LAUNCHER.resolve()
    # PATH hint must be usable from any dir: absolute target
    assert re.search(rf'export PATH="?{re.escape(str(cwd / "rel" / "bin"))}:', p.stdout + p.stderr)


def test_install_uv_sync_failure_fails_without_link(tmp_path, env):
    e, _ = env
    fake_bin(tmp_path / "tools", "uv", "echo sync-boom >&2; exit 2")
    target = tmp_path / "bin"
    p = install(target, tmp_path, e)
    assert p.returncode != 0
    assert "sync-boom" in p.stderr
    assert not (target / "crap4sol").is_symlink()


def test_install_refuses_to_overwrite_regular_file(tmp_path, env):
    target = tmp_path / "bin"
    target.mkdir()
    existing = target / "crap4sol"
    existing.write_text("keep me\n")
    p = install(target, tmp_path, env[0])
    assert p.returncode == 1
    assert not existing.is_symlink()
    assert existing.read_text() == "keep me\n"
    assert str(existing) in p.stdout + p.stderr


def test_install_refuses_directory_at_target(tmp_path, env):
    # `ln -sf` into a directory would silently drop a link inside it
    target = tmp_path / "bin"
    existing = target / "crap4sol"
    existing.mkdir(parents=True)
    p = install(target, tmp_path, env[0])
    assert p.returncode == 1
    assert not existing.is_symlink()
    assert list(existing.iterdir()) == []


def test_install_runs_uv_sync_for_repo(tmp_path, env):
    e, log = env
    p = install(tmp_path / "bin", tmp_path, e)
    assert p.returncode == 0, p.stderr
    calls = log.read_text().splitlines()
    syncs = [c.split() for c in calls if c.split()[:1] == ["sync"]]
    assert len(syncs) == 1, calls
    args = syncs[0]
    assert "--project" in args
    assert Path(args[args.index("--project") + 1]).resolve() == REPO


def test_install_prints_installed_path_and_help_hint(tmp_path, env):
    target = tmp_path / "bin"
    p = install(target, tmp_path, env[0])
    assert p.returncode == 0, p.stderr
    out = p.stdout + p.stderr
    assert str(target / "crap4sol") in out
    assert "crap4sol --help" in out


def test_install_warns_when_target_not_on_path(tmp_path, env):
    target = tmp_path / "bin"
    p = install(target, tmp_path, env[0])
    assert p.returncode == 0, p.stderr
    assert re.search(rf'export PATH="?{re.escape(str(target))}:', p.stdout + p.stderr)


def test_install_no_path_warning_when_target_on_path(tmp_path, env):
    e, _ = env
    target = tmp_path / "bin"
    e = {**e, "PATH": f"{target}:{e['PATH']}"}
    p = install(target, tmp_path, e)
    assert p.returncode == 0, p.stderr
    assert "export PATH=" not in p.stdout + p.stderr


def warned(p, tmp_path, tool) -> bool:
    return any(
        "warning" in l.lower() and re.search(rf"\b{tool}\b", l)
        for l in msgs(p, tmp_path).splitlines()
    )


@needs_bare_sys_path
def test_install_warns_but_succeeds_without_forge(tmp_path, env):
    e, _ = env
    tools = tmp_path / "tools"
    (tools / "forge").unlink()
    p = install(tmp_path / "bin", tmp_path, {**e, "PATH": f"{tools}:{SYS_PATH}"})
    assert p.returncode == 0, p.stderr
    assert warned(p, tmp_path, "forge")
    assert (tmp_path / "bin" / "crap4sol").resolve() == LAUNCHER.resolve()


@needs_bare_sys_path
def test_install_warns_but_succeeds_without_uv(tmp_path, env):
    e, _ = env
    tools = tmp_path / "tools"
    (tools / "uv").unlink()
    p = install(tmp_path / "bin", tmp_path, {**e, "PATH": f"{tools}:{SYS_PATH}"})
    assert p.returncode == 0, p.stderr
    assert warned(p, tmp_path, "uv")
    assert (tmp_path / "bin" / "crap4sol").resolve() == LAUNCHER.resolve()


def test_install_no_prereq_warning_when_all_present(tmp_path, env):
    p = install(tmp_path / "bin", tmp_path, {**env[0], "PATH": f"{tmp_path / 'bin'}:{env[0]['PATH']}"})
    assert p.returncode == 0, p.stderr
    out = msgs(p, tmp_path)
    assert "forge" not in out
    assert "warn" not in out.lower()


# --- launcher --------------------------------------------------------------------------


@pytest.fixture
def linked(tmp_path):
    """Launcher reached through a two-hop chain (absolute, then relative symlink)."""
    hop = tmp_path / "opt" / "crap4sol"
    hop.parent.mkdir()
    hop.symlink_to(LAUNCHER)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    link = bin_dir / "crap4sol"
    link.symlink_to(Path("..") / "opt" / "crap4sol")
    return link


@pytest.fixture
def work(tmp_path):
    # deeper than bin/: a relative hop resolved against cwd instead of the link's dir breaks
    d = tmp_path / "a" / "b" / "work"
    d.mkdir(parents=True)
    return d


def test_launcher_help_through_symlink_chain(linked, work):
    p = run([linked, "--help"], work)
    assert p.returncode == 0, p.stderr
    assert p.stdout.startswith("usage: crap4sol")


def test_launcher_stdout_stderr_match_direct_uv_run(linked, work):
    # output passes through untouched: no extra banner, no uv chatter
    direct = run(["uv", "run", "--quiet", "--project", REPO, "crap4sol", "--help"], work)
    p = run([linked, "--help"], work)
    assert (p.returncode, p.stdout, p.stderr) == (direct.returncode, direct.stdout, direct.stderr)


def test_launcher_passes_usage_error_exit_one(linked, work):
    p = run([linked, "--bogus"], work)
    assert p.returncode == 1
    assert p.stdout == ""
    assert "usage: crap4sol" in p.stderr


def test_launcher_passes_branch_rejection(linked, work):
    p = run([linked, "--coverage", "branch"], work)
    assert p.returncode == 1
    assert "Branch coverage not implemented yet." in p.stderr


def test_launcher_keeps_cwd_empty_project_exit_zero(linked, work):
    # cwd = work (no src/): the repo checkout's own tree is not analyzed
    p = run([linked], work)
    assert p.returncode == 0, p.stderr
    assert "No Solidity files to analyze." in p.stdout + p.stderr


def test_launcher_keeps_cwd_and_passes_exit_three(linked, tmp_path):
    # cwd has a .sol under src/; failing fake forge → analysis failure exit 3.
    # If the launcher switched cwd to the repo (no .sol in src/), it would exit 0.
    proj = tmp_path / "proj"
    (proj / "src").mkdir(parents=True)
    (proj / "foundry.toml").write_text("[profile.default]\n")
    (proj / "src" / "A.sol").write_text("pragma solidity ^0.8.0;\ncontract A {}\n")
    tools = tmp_path / "tools"
    fake_bin(tools, "forge", "echo forge-boom >&2; exit 7")
    p = run([linked], proj, {**os.environ, "PATH": f"{tools}:{os.environ['PATH']}"})
    assert p.returncode == 3, p.stdout + p.stderr
    assert "forge clean failed" in p.stderr
    assert p.stdout == ""


@needs_bare_sys_path
def test_launcher_without_uv_exits_three_with_hint(linked, work, tmp_path):
    p = run([linked, "--help"], work, {**os.environ, "PATH": SYS_PATH})
    assert p.returncode == 3
    assert p.stdout == ""
    err = msgs(p, tmp_path)
    assert "uv" in err
    assert "install" in err.lower()


@pytest.mark.e2e
def test_launcher_e2e_on_fixture_reports_and_exits_two(linked, tmp_path):
    dst = tmp_path / "foundry-sample"
    shutil.copytree(FIXTURE, dst, ignore=shutil.ignore_patterns("out", "cache", "lcov.info"))
    p = run([linked], dst, timeout=900)
    assert p.returncode == 2, p.stderr
    assert "classify(uint256)" in p.stdout
    assert "CRAP threshold exceeded: 30.0 > 8.0" in p.stderr
    assert (dst / "lcov.info").is_file()  # coverage ran in the caller's project


def test_launcher_uv_env_failure_exits_three_not_uv_code(linked, work, tmp_path):
    # uv itself fails before crap4sol starts (fresh env, offline, empty cache): its own
    # exit code (1/2) must not masquerade as crap4sol's usage error / threshold exit
    e = {
        **os.environ,
        "UV_OFFLINE": "1",
        "UV_CACHE_DIR": str(tmp_path / "empty-cache"),
        "UV_PROJECT_ENVIRONMENT": str(tmp_path / "fresh-venv"),
    }
    p = run([linked, "--help"], work, e)
    assert p.returncode == 3, p.stdout + p.stderr
    assert p.stdout == ""
    assert "usage: crap4sol" not in p.stderr
