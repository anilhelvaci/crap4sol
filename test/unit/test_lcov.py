"""T1.3-T1.5: LCOV parsing (spec §7.3), missing/empty LCOV (§7), SF normalization (§9.1)."""

import pytest

from crap4sol.errors import AnalysisError
from crap4sol.lcov import (
    FileCoverage,
    load_lcov,
    normalize_report,
    normalize_sf,
    parse_lcov,
)

SAMPLE = """\
TN:
SF:src/Vault.sol
FN:10,Vault.deposit
FNDA:3,Vault.deposit
FNF:1
FNH:1
DA:10,3
DA:11,3
DA:14,0
BRDA:11,0,0,3
BRDA:11,0,1,-
BRF:2
BRH:1
LF:3
LH:2
end_of_record
TN:
SF:src/lib/Math.sol
DA:5,1
DA:6,0
LF:2
LH:1
end_of_record
"""


def test_parse_maps_each_sf_record_to_its_da_hits():
    report = parse_lcov(SAMPLE)
    assert {path: fc.lines for path, fc in report.items()} == {
        "src/Vault.sol": {10: 3, 11: 3, 14: 0},
        "src/lib/Math.sol": {5: 1, 6: 0},
    }


def test_parse_returns_file_coverage_values():
    assert isinstance(parse_lcov(SAMPLE)["src/Vault.sol"], FileCoverage)


def test_parse_keeps_zero_hit_da_lines():
    assert parse_lcov(SAMPLE)["src/lib/Math.sol"].lines[6] == 0


def test_parse_ignores_fn_and_summary_records_in_lines():
    assert set(parse_lcov(SAMPLE)["src/Vault.sol"].lines) == {10, 11, 14}


def test_parse_keeps_brda_payloads_raw():
    assert parse_lcov(SAMPLE)["src/Vault.sol"].brda == ["11,0,0,3", "11,0,1,-"]


def test_parse_file_without_brda_has_empty_brda():
    assert parse_lcov(SAMPLE)["src/lib/Math.sol"].brda == []


def test_load_lcov_missing_file_is_none(tmp_path):
    assert load_lcov(tmp_path / "lcov.info") is None


def test_load_lcov_empty_file_is_none(tmp_path):
    p = tmp_path / "lcov.info"
    p.write_text("")
    assert load_lcov(p) is None


def test_load_lcov_reads_and_parses_existing_file(tmp_path):
    p = tmp_path / "lcov.info"
    p.write_text(SAMPLE)
    assert load_lcov(p) == parse_lcov(SAMPLE)


def test_normalize_absolute_sf_to_module_relative(tmp_path):
    assert normalize_sf(str(tmp_path / "src" / "Vault.sol"), tmp_path) == "src/Vault.sol"


def test_normalize_keeps_relative_sf(tmp_path):
    assert normalize_sf("src/Vault.sol", tmp_path) == "src/Vault.sol"


def test_normalize_strips_leading_dot_slash(tmp_path):
    assert normalize_sf("./src/Vault.sol", tmp_path) == "src/Vault.sol"


def test_normalize_absolute_and_relative_forms_are_equal(tmp_path):
    assert normalize_sf(str(tmp_path / "src/Vault.sol"), tmp_path) == normalize_sf(
        "src/Vault.sol", tmp_path
    )


# --- hardening (review follow-ups on f139354) ---

def test_parse_sums_duplicate_da_lines_in_one_record():
    text = "SF:src/A.sol\nDA:5,3\nDA:5,0\nend_of_record\n"
    assert parse_lcov(text)["src/A.sol"].lines == {5: 3}


def test_parse_merges_repeated_sf_records_by_summing_hits():
    text = (
        "SF:src/A.sol\nDA:5,2\nDA:6,0\nend_of_record\n"
        "SF:src/A.sol\nDA:5,1\nDA:7,4\nend_of_record\n"
    )
    assert parse_lcov(text)["src/A.sol"].lines == {5: 3, 6: 0, 7: 4}


def test_parse_accepts_da_checksum_field():
    text = "SF:src/A.sol\nDA:5,2,abc123\nend_of_record\n"
    assert parse_lcov(text)["src/A.sol"].lines == {5: 2}


def test_parse_ignores_da_before_any_sf():
    text = "DA:1,1\nSF:src/A.sol\nDA:5,2\nend_of_record\n"
    assert parse_lcov(text) == {"src/A.sol": FileCoverage(lines={5: 2})}


def test_parse_da_missing_hits_raises_analysis_error():
    with pytest.raises(AnalysisError, match="DA:10,"):
        parse_lcov("SF:src/A.sol\nDA:10,\nend_of_record\n")


def test_parse_da_non_numeric_line_raises_analysis_error():
    with pytest.raises(AnalysisError, match="DA:x,1"):
        parse_lcov("SF:src/A.sol\nDA:x,1\nend_of_record\n")


def test_load_lcov_whitespace_only_file_is_none(tmp_path):
    p = tmp_path / "lcov.info"
    p.write_text("  \n\n\t\n")
    assert load_lcov(p) is None


def test_normalize_collapses_dotdot_in_absolute_sf(tmp_path):
    sf = str(tmp_path / "lib" / ".." / "src" / "A.sol")
    assert normalize_sf(sf, tmp_path) == "src/A.sol"


def test_normalize_collapses_dotdot_in_relative_sf(tmp_path):
    assert normalize_sf("lib/../src/A.sol", tmp_path) == "src/A.sol"


# --- review follow-ups on 53f68b2 ---


def test_parse_da_without_hits_field_raises_analysis_error():
    with pytest.raises(AnalysisError, match="DA:10"):
        parse_lcov("SF:src/A.sol\nDA:10\nend_of_record\n")


def test_parse_da_negative_hits_raises_analysis_error():
    with pytest.raises(AnalysisError, match="DA:5,-3"):
        parse_lcov("SF:src/A.sol\nDA:5,3\nDA:5,-3\nend_of_record\n")


def test_parse_da_line_zero_raises_analysis_error():
    with pytest.raises(AnalysisError, match="DA:0,1"):
        parse_lcov("SF:src/A.sol\nDA:0,1\nend_of_record\n")


def test_parse_malformed_da_error_names_sf():
    with pytest.raises(AnalysisError, match="src/A.sol"):
        parse_lcov("SF:src/A.sol\nDA:x,1\nend_of_record\n")


def test_load_lcov_malformed_da_error_names_lcov_path(tmp_path):
    p = tmp_path / "lcov.info"
    p.write_text("SF:src/A.sol\nDA:x,1\nend_of_record\n")
    with pytest.raises(AnalysisError, match=str(p)):
        load_lcov(p)


def test_normalize_report_rekeys_absolute_sf_to_module_relative(tmp_path):
    report = {str(tmp_path / "src/A.sol"): FileCoverage(lines={5: 1})}
    assert normalize_report(report, tmp_path) == {"src/A.sol": FileCoverage(lines={5: 1})}


def test_normalize_report_sums_hits_when_abs_and_rel_sf_collide(tmp_path):
    report = {
        str(tmp_path / "src/A.sol"): FileCoverage(lines={5: 1, 6: 0}, brda=["5,0,0,1"]),
        "./src/A.sol": FileCoverage(lines={5: 2, 7: 3}, brda=["5,0,1,-"]),
    }
    assert normalize_report(report, tmp_path) == {
        "src/A.sol": FileCoverage(lines={5: 3, 6: 0, 7: 3}, brda=["5,0,0,1", "5,0,1,-"])
    }


def test_normalize_report_keeps_distinct_files_apart(tmp_path):
    report = {"src/A.sol": FileCoverage(lines={1: 1}), "src/B.sol": FileCoverage(lines={1: 0})}
    assert normalize_report(report, tmp_path) == report


# --- review follow-ups on be1ffaf: I/O errors are analysis failures (spec §13, §14) ---


def test_load_lcov_non_utf8_file_raises_analysis_error(tmp_path):
    p = tmp_path / "lcov.info"
    p.write_bytes(b"SF:src/A.sol\nDA:1,1\n\xff\xfe\nend_of_record\n")
    with pytest.raises(AnalysisError, match=str(p)):
        load_lcov(p)


def test_load_lcov_read_oserror_raises_analysis_error(tmp_path, monkeypatch):
    p = tmp_path / "lcov.info"
    p.write_text("SF:src/A.sol\nDA:1,1\nend_of_record\n")

    def boom(*args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(type(p), "read_text", boom)
    with pytest.raises(AnalysisError, match=str(p)):
        load_lcov(p)


def test_load_lcov_strips_utf8_bom_so_first_sf_is_kept(tmp_path):
    p = tmp_path / "lcov.info"
    p.write_bytes(b"\xef\xbb\xbfSF:src/A.sol\nDA:1,1\nend_of_record\n")
    assert load_lcov(p) == {"src/A.sol": FileCoverage(lines={1: 1})}


def test_load_lcov_bom_only_file_is_none(tmp_path):
    p = tmp_path / "lcov.info"
    p.write_bytes(b"\xef\xbb\xbf")
    assert load_lcov(p) is None


def test_load_lcov_bom_and_whitespace_file_is_none(tmp_path):
    p = tmp_path / "lcov.info"
    p.write_bytes(b"\xef\xbb\xbf \n\t\n")
    assert load_lcov(p) is None


def test_load_lcov_utf16_file_raises_analysis_error(tmp_path):
    p = tmp_path / "lcov.info"
    p.write_bytes("SF:src/A.sol\nDA:1,1\nend_of_record\n".encode("utf-16"))
    with pytest.raises(AnalysisError, match=str(p)):
        load_lcov(p)
