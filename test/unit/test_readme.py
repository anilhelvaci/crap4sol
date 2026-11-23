"""T4.7: README documents install, usage, exit codes, CC limitations, via-IR (plan.md M4)."""

from pathlib import Path

import pytest

README = Path(__file__).resolve().parents[2] / "README.md"


@pytest.fixture(scope="module")
def text():
    return README.read_text(encoding="utf-8") if README.is_file() else ""


def test_readme_exists():
    assert README.is_file()


def test_readme_has_install_section(text):
    assert "## Install" in text


def test_readme_has_usage_section(text):
    assert "## Usage" in text


@pytest.mark.parametrize(
    "form",
    ["crap4sol --changed", "crap4sol --coverage", "crap4sol --help"],
)
def test_readme_shows_cli_forms(text, form):
    assert form in text


def test_readme_has_exit_codes_section(text):
    assert "## Exit codes" in text


@pytest.mark.parametrize("code", ["0", "1", "2", "3"])
def test_readme_lists_each_exit_code(text, code):
    section = text.split("## Exit codes", 1)[1].split("\n## ", 1)[0]
    assert f"| {code} " in section or f"`{code}`" in section


def test_readme_states_threshold(text):
    assert "8.0" in text


def test_readme_states_branch_coverage_not_implemented(text):
    assert "Branch coverage not implemented yet." in text


def test_readme_documents_cc_limitations(text):
    # spec §8.1 known limitations
    for item in ("&&", "||", "require"):
        assert item in text


def test_readme_mentions_via_ir(text):
    assert "via-IR" in text or "via_ir" in text
