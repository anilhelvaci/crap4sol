"""T1.6 / T1.7: line coverage attribution and N/A (spec §9.1)."""

import pytest

from crap4sol.coverage import attribute, line_coverage
from crap4sol.lcov import FileCoverage
from crap4sol.metrics import Callable, Kind, Metric


def fc(lines):
    return FileCoverage(lines=dict(lines))


def make_callable(file="src/Vault.sol", start=10, end=13, cc=4):
    return Callable(
        contract="Vault",
        signature="deposit(uint256)",
        kind=Kind.FUNCTION,
        file=file,
        start_line=start,
        end_line=end,
        cc=cc,
    )


def test_partial_coverage_is_hit_da_over_da_in_range():
    assert line_coverage(fc({10: 1, 11: 0, 12: 5, 13: 0}), 10, 13) == pytest.approx(0.5)


def test_full_coverage_is_one():
    assert line_coverage(fc({10: 1, 12: 2}), 10, 13) == pytest.approx(1.0)


def test_zero_coverage_is_zero():
    assert line_coverage(fc({10: 0, 11: 0}), 10, 13) == pytest.approx(0.0)


def test_range_includes_start_and_end_lines():
    assert line_coverage(fc({10: 1, 13: 0}), 10, 13) == pytest.approx(0.5)


def test_da_lines_outside_range_are_ignored():
    assert line_coverage(fc({9: 0, 10: 1, 14: 0}), 10, 13) == pytest.approx(1.0)


def test_no_da_in_range_is_na():
    assert line_coverage(fc({5: 1, 20: 1}), 10, 13) is None


def test_file_absent_is_na():
    assert line_coverage(None, 10, 13) is None


def test_attribute_numeric_coverage_and_crap():
    c = make_callable(cc=4)
    report = {"src/Vault.sol": fc({10: 1, 11: 0, 12: 1, 13: 0})}
    m = attribute(c, report)
    assert m == Metric(callable=c, coverage=pytest.approx(0.5), crap=pytest.approx(6.0))


def test_attribute_uncovered_callable_gets_full_crap():
    c = make_callable(cc=4)
    m = attribute(c, {"src/Vault.sol": fc({10: 0, 11: 0})})
    assert (m.coverage, m.crap) == (pytest.approx(0.0), pytest.approx(20.0))


def test_attribute_file_absent_from_report_is_na():
    c = make_callable(file="src/Other.sol")
    assert attribute(c, {"src/Vault.sol": fc({10: 1})}) == Metric(c, None, None)


def test_attribute_no_da_in_range_is_na():
    c = make_callable(start=30, end=40)
    assert attribute(c, {"src/Vault.sol": fc({10: 1})}) == Metric(c, None, None)


def test_attribute_without_lcov_report_is_na():
    c = make_callable()
    assert attribute(c, None) == Metric(c, None, None)
