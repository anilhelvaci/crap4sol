"""Exit codes (spec §13) and the analysis error type."""

EXIT_SUCCESS = 0
EXIT_USAGE = 1
EXIT_THRESHOLD_EXCEEDED = 2
EXIT_ANALYSIS_FAILURE = 3


class AnalysisError(Exception):
    """A toolchain step (forge, Slither, coverage) failed; maps to EXIT_ANALYSIS_FAILURE."""
