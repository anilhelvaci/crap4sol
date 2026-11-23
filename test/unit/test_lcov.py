"""T1.3-T1.5: LCOV parsing (spec §7.3), missing/empty LCOV (§7), SF normalization (§9.1)."""

from crap4sol.lcov import FileCoverage, load_lcov, normalize_sf, parse_lcov

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
