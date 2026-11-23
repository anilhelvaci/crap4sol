"""T0.1: package scaffold and console entry point (plan.md M0)."""

import importlib
from importlib.metadata import entry_points


def test_package_imports():
    assert importlib.import_module("crap4sol") is not None


def test_console_script_crap4sol_points_to_cli_main():
    scripts = entry_points(group="console_scripts")
    matches = [ep for ep in scripts if ep.name == "crap4sol"]
    assert len(matches) == 1
    assert matches[0].value == "crap4sol.cli:main"


def test_cli_main_is_callable():
    cli = importlib.import_module("crap4sol.cli")
    assert callable(cli.main)
