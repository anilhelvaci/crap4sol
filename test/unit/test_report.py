"""T1.8-T1.10: report sort (spec §11), render (§11), threshold (§12)."""

import io

import pytest

from crap4sol.errors import EXIT_SUCCESS, EXIT_THRESHOLD_EXCEEDED
from crap4sol.metrics import Callable, Kind, Metric
from crap4sol.report import THRESHOLD, check_threshold, max_crap, render, sort_metrics


def m(contract="Vault", signature="f()", crap=1.0, coverage=1.0, kind=Kind.FUNCTION, cc=1):
    c = Callable(
        contract=contract,
        signature=signature,
        kind=kind,
        file="src/Vault.sol",
        start_line=1,
        end_line=2,
        cc=cc,
    )
    return Metric(callable=c, coverage=coverage, crap=crap)


def na(contract="Vault", signature="f()"):
    return m(contract=contract, signature=signature, crap=None, coverage=None)


def keys(metrics):
    return [(x.callable.contract, x.callable.signature) for x in metrics]


# --- T1.8 sort ---


def test_sort_orders_by_crap_descending():
    out = sort_metrics([m(signature="a()", crap=2.0), m(signature="b()", crap=9.0)])
    assert [x.crap for x in out] == [9.0, 2.0]


def test_sort_puts_na_after_all_numeric_rows():
    out = sort_metrics([na(signature="a()"), m(signature="b()", crap=1.0)])
    assert keys(out) == [("Vault", "b()"), ("Vault", "a()")]


def test_sort_breaks_crap_ties_by_contract():
    out = sort_metrics([m(contract="B", crap=3.0), m(contract="A", crap=3.0)])
    assert keys(out) == [("A", "f()"), ("B", "f()")]


def test_sort_breaks_contract_ties_by_signature():
    out = sort_metrics([m(signature="z()", crap=3.0), m(signature="a(uint256)", crap=3.0)])
    assert keys(out) == [("Vault", "a(uint256)"), ("Vault", "z()")]


def test_sort_orders_na_rows_by_contract_then_signature():
    out = sort_metrics([na("B", "a()"), na("A", "z()"), na("A", "b()")])
    assert keys(out) == [("A", "b()"), ("A", "z()"), ("B", "a()")]


def test_sort_does_not_mutate_input():
    rows = [m(signature="a()", crap=1.0), m(signature="b()", crap=2.0)]
    sort_metrics(rows)
    assert keys(rows) == [("Vault", "a()"), ("Vault", "b()")]


# --- T1.9 render ---


def test_render_golden_table():
    rows = [
        m("Vault", "withdraw(uint256)", crap=20.0, coverage=0.0, cc=4),
        m("Vault", "deposit(uint256)", crap=6.0, coverage=0.5, cc=4, kind=Kind.MODIFIER),
        m("<file>", "f()", crap=None, coverage=None, cc=1, kind=Kind.FREE),
    ]
    assert render(rows) == (
        "Function           Contract  Kind      CC   Cov%   CRAP\n"
        "-----------------  --------  --------  --  -----  -----\n"
        "withdraw(uint256)  Vault     function   4   0.0%  20.00\n"
        "deposit(uint256)   Vault     modifier   4  50.0%   6.00\n"
        "f()                <file>    free       1    N/A    N/A\n"
    )


def test_render_keeps_given_row_order():
    out = render([m(signature="low()", crap=1.0), m(signature="high()", crap=9.0)])
    lines = out.splitlines()
    assert lines[2].startswith("low()") and lines[3].startswith("high()")


def test_render_empty_has_header_only():
    assert render([]) == (
        "Function  Contract  Kind  CC  Cov%  CRAP\n"
        "--------  --------  ----  --  ----  ----\n"
    )


# --- T1.10 threshold ---


def test_threshold_is_eight():
    assert THRESHOLD == 8.0


def test_max_crap_takes_largest_numeric():
    assert max_crap([m(crap=3.0), m(crap=12.5), na()]) == 12.5


def test_max_crap_with_no_numeric_is_zero():
    assert max_crap([na(), na()]) == 0.0


def test_max_crap_of_empty_is_zero():
    assert max_crap([]) == 0.0


def test_check_threshold_at_exactly_eight_is_not_exceeded():
    err = io.StringIO()
    assert check_threshold([m(crap=8.0)], err) == EXIT_SUCCESS
    assert err.getvalue() == ""


def test_check_threshold_above_eight_returns_exit_2():
    assert check_threshold([m(crap=8.25)], io.StringIO()) == EXIT_THRESHOLD_EXCEEDED


def test_check_threshold_above_eight_writes_message():
    err = io.StringIO()
    check_threshold([m(crap=20.0), m(crap=3.0)], err)
    assert err.getvalue() == "CRAP threshold exceeded: 20.0 > 8.0\n"


def test_check_threshold_message_keeps_max_precision():
    err = io.StringIO()
    check_threshold([m(crap=8.25)], err)
    assert err.getvalue() == "CRAP threshold exceeded: 8.25 > 8.0\n"


def test_check_threshold_with_only_na_is_not_exceeded():
    assert check_threshold([na()], io.StringIO()) == EXIT_SUCCESS


# --- review follow-ups on be1ffaf ---


def crap_cell(row):
    return render([row]).splitlines()[2].split()[-1]


def cov_cell(row):
    return render([row]).splitlines()[2].split()[-2]


def test_sort_puts_na_after_zero_crap_row():
    out = sort_metrics([na(signature="a()"), m(signature="b()", crap=0.0)])
    assert keys(out) == [("Vault", "b()"), ("Vault", "a()")]


def _at(file, start, crap=3.0):
    c = Callable("Vault", "f()", Kind.FUNCTION, file, start, start + 1, 1)
    return Metric(c, 1.0, crap)


def test_sort_breaks_signature_ties_by_file():
    out = sort_metrics([_at("src/b/Vault.sol", 1), _at("src/a/Vault.sol", 1)])
    assert [x.callable.file for x in out] == ["src/a/Vault.sol", "src/b/Vault.sol"]


def test_sort_breaks_file_ties_by_start_line():
    out = sort_metrics([_at("src/Vault.sol", 30), _at("src/Vault.sol", 5)])
    assert [x.callable.start_line for x in out] == [5, 30]


def test_check_threshold_finds_worst_row_not_in_first_place():
    err = io.StringIO()
    code = check_threshold([m(crap=1.0), m(crap=2.0), m(crap=9.5)], err)
    assert (code, err.getvalue()) == (EXIT_THRESHOLD_EXCEEDED, "CRAP threshold exceeded: 9.5 > 8.0\n")


def test_render_crap_just_over_threshold_does_not_display_as_threshold():
    assert crap_cell(m(crap=8.004)) == "8.01"


def test_render_crap_rounds_up_to_two_decimals():
    assert crap_cell(m(crap=2.001)) == "2.01"


def test_render_crap_exact_two_decimal_value_is_unchanged():
    assert crap_cell(m(crap=1.1)) == "1.10"


def test_render_coverage_just_below_full_does_not_display_as_full():
    assert cov_cell(m(coverage=0.9996)) == "99.9%"


def test_render_coverage_exact_one_decimal_value_is_unchanged():
    assert cov_cell(m(coverage=0.29)) == "29.0%"


def test_render_full_coverage_is_hundred_percent():
    assert cov_cell(m(coverage=1.0)) == "100.0%"


# --- review follow-ups on 76bf812: no snapping near a rounding step ---


def test_render_crap_a_hair_over_threshold_does_not_display_as_threshold():
    assert crap_cell(m(crap=8.0 + 1e-9)) == "8.01"


def test_render_coverage_a_hair_below_full_does_not_display_as_full():
    assert cov_cell(m(coverage=1 - 1e-10)) == "99.9%"
