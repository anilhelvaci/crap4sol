"""T0.3: callable/metric data model (spec §3, §8)."""

import dataclasses

from crap4sol.metrics import Callable, Kind, Metric


def make_callable(**overrides):
    fields = dict(
        contract="Vault",
        signature="deposit(uint256)",
        kind=Kind.FUNCTION,
        file="src/Vault.sol",
        start_line=10,
        end_line=20,
        cc=3,
    )
    fields.update(overrides)
    return Callable(**fields)


def test_kind_has_exactly_the_six_spec_kinds():
    assert {k.value for k in Kind} == {
        "function",
        "modifier",
        "constructor",
        "receive",
        "fallback",
        "free",
    }


def test_kind_members_map_to_spec_strings():
    assert Kind.FUNCTION.value == "function"
    assert Kind.MODIFIER.value == "modifier"
    assert Kind.CONSTRUCTOR.value == "constructor"
    assert Kind.RECEIVE.value == "receive"
    assert Kind.FALLBACK.value == "fallback"
    assert Kind.FREE.value == "free"


def test_callable_is_dataclass_with_spec_fields_in_order():
    assert dataclasses.is_dataclass(Callable)
    assert [f.name for f in dataclasses.fields(Callable)] == [
        "contract",
        "signature",
        "kind",
        "file",
        "start_line",
        "end_line",
        "cc",
    ]


def test_callable_keeps_constructor_values():
    c = make_callable()
    assert (c.contract, c.signature, c.kind, c.file, c.start_line, c.end_line, c.cc) == (
        "Vault",
        "deposit(uint256)",
        Kind.FUNCTION,
        "src/Vault.sol",
        10,
        20,
        3,
    )


def test_callables_with_same_fields_are_equal():
    assert make_callable() == make_callable()


def test_overloads_differ_by_signature():
    assert make_callable(signature="deposit(uint256)") != make_callable(
        signature="deposit(uint256,address)"
    )


def test_metric_is_dataclass_with_spec_fields_in_order():
    assert dataclasses.is_dataclass(Metric)
    assert [f.name for f in dataclasses.fields(Metric)] == ["callable", "coverage", "crap"]


def test_metric_holds_numeric_coverage_and_crap():
    c = make_callable()
    m = Metric(callable=c, coverage=0.5, crap=4.125)
    assert (m.callable, m.coverage, m.crap) == (c, 0.5, 4.125)


def test_metric_represents_coverage_na_as_none():
    m = Metric(callable=make_callable(), coverage=None, crap=None)
    assert m.coverage is None
    assert m.crap is None
