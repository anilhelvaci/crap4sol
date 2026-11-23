"""T0.2: exit codes (spec §13) and AnalysisError."""

import pytest

from crap4sol import errors


def test_exit_success_is_0():
    assert errors.EXIT_SUCCESS == 0


def test_exit_usage_is_1():
    assert errors.EXIT_USAGE == 1


def test_exit_threshold_exceeded_is_2():
    assert errors.EXIT_THRESHOLD_EXCEEDED == 2


def test_exit_analysis_failure_is_3():
    assert errors.EXIT_ANALYSIS_FAILURE == 3


def test_analysis_error_is_an_exception():
    assert issubclass(errors.AnalysisError, Exception)


def test_analysis_error_carries_message():
    with pytest.raises(errors.AnalysisError, match="^forge coverage failed$"):
        raise errors.AnalysisError("forge coverage failed")
