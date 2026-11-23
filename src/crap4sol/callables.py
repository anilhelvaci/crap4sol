"""Callable collection via Slither (spec §8)."""

from collections.abc import Iterable, Iterator
from pathlib import Path

from slither import Slither
from slither.core.declarations import Modifier
from slither.core.declarations.function import FunctionType
from slither.utils.code_complexity import compute_cyclomatic_complexity

from crap4sol.errors import AnalysisError
from crap4sol.lcov import normalize_sf
from crap4sol.metrics import Callable, Kind, clamp_cc

_SYNTHESIZED = (FunctionType.CONSTRUCTOR_VARIABLES, FunctionType.CONSTRUCTOR_CONSTANT_VARIABLES)


def _load_slither(root: Path):
    if not root.is_dir():
        raise AnalysisError(f"Slither failed for module {root}: not a directory")
    try:
        return Slither(str(root))
    except Exception as exc:  # crytic-compile/Slither raise assorted error types
        raise AnalysisError(f"Slither failed for module {root}: {exc}") from exc


def _kind(fn) -> Kind:
    if isinstance(fn, Modifier):
        return Kind.MODIFIER
    return {
        FunctionType.CONSTRUCTOR: Kind.CONSTRUCTOR,
        FunctionType.RECEIVE: Kind.RECEIVE,
        FunctionType.FALLBACK: Kind.FALLBACK,
    }.get(fn.function_type, Kind.FUNCTION)


def _candidates(slither) -> Iterator[tuple[object, str | None]]:
    """(callable, declaring contract name or None for free functions) per compilation unit."""
    for cu in slither.compilation_units:
        for contract in cu.contracts:
            for fn in [*contract.functions_declared, *contract.modifiers_declared]:
                if fn.contract_declarer == contract:
                    yield fn, contract.name
        for fn in cu.functions_top_level:
            yield fn, None


def collect_callables(module_root: Path, files: Iterable[Path]) -> list[Callable]:
    """Implemented callables declared in the selected files, one row each (spec §8)."""
    root = Path(module_root).absolute()
    selected = {Path(f).resolve() for f in files}
    if not selected:
        return []
    slither = _load_slither(root)

    out: dict[tuple, Callable] = {}
    for fn, contract in _candidates(slither):
        if not fn.is_implemented or fn.function_type in _SYNTHESIZED:
            continue
        abspath = fn.source_mapping.filename.absolute
        if Path(abspath).resolve() not in selected:
            continue
        # key by the in-module path Slither saw (not the symlink target): same as LCOV SF
        rel = normalize_sf(abspath, root)
        if Path(rel).is_absolute():
            raise AnalysisError(f"{abspath}: source file outside module {root}")
        lines = fn.source_mapping.lines
        c = Callable(
            contract=contract if contract is not None else rel,
            signature=fn.full_name,
            kind=_kind(fn) if contract is not None else Kind.FREE,
            file=rel,
            start_line=lines[0],
            end_line=lines[-1],
            cc=clamp_cc(compute_cyclomatic_complexity(fn)),
        )
        # several compilation units can see the same declaration
        out.setdefault((c.file, c.contract, c.signature, c.start_line), c)
    return list(out.values())
