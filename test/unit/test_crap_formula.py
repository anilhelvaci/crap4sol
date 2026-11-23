"""T1.1 / T1.2: CRAP formula (spec §10) and CC clamp (spec §8.1)."""

import pytest

from crap4sol.metrics import clamp_cc, crap


def test_crap_with_zero_coverage_is_cc_squared_plus_cc():
    assert crap(4, 0.0) == pytest.approx(20.0)


def test_crap_with_half_coverage_applies_cubed_uncovered_fraction():
    assert crap(4, 0.5) == pytest.approx(6.0)


def test_crap_with_full_coverage_equals_cc():
    assert crap(4, 1.0) == pytest.approx(4.0)


def test_crap_of_trivial_uncovered_callable_is_two():
    assert crap(1, 0.0) == pytest.approx(2.0)


def test_crap_returns_float():
    assert isinstance(crap(3, 1.0), float)


def test_clamp_cc_raises_zero_to_one():
    assert clamp_cc(0) == 1


def test_clamp_cc_raises_negative_to_one():
    assert clamp_cc(-2) == 1


def test_clamp_cc_keeps_values_at_least_one():
    assert clamp_cc(1) == 1
    assert clamp_cc(7) == 7
