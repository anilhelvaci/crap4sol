# crap4sol — development plan (spec phases 1 + 2)

## Context
`spec.md` (PR #2, draft) defines crap4sol: a CRAP quality gate for Foundry Solidity projects, written in Python on Slither.
The repo has only the spec. Goal: split the spec into small, independently reviewable tasks covering
**Phase 1** (line coverage, §4–§14) and **Phase 2** (branch coverage, §9.2).
Each task = tests first, then code, one commit / small PR on an `agent/<task-id>` branch, through `./agent-gh.sh`.
Pure core + thin adapters around `forge` / Slither, so most tests need no toolchain.

## Layout (target)
```
pyproject.toml            hatchling, script crap4sol = crap4sol.cli:main, deps slither-analyzer, dev pytest (uv)
src/crap4sol/  cli.py selection.py modules.py lcov.py coverage.py callables.py metrics.py report.py errors.py
tests/unit/  tests/integration/  tests/fixtures/foundry-sample/
```

---

## Milestone 0: Foundation
| ID | Task | Spec | Done when |
|----|------|------|-----------|
| T0.1 | Scaffold: pyproject, package, pytest config, `uv run pytest` green with 1 placeholder test | — | `uv run crap4sol` imports |
| T0.2 | `errors.py`: `AnalysisError`; exit-code constants 0/1/2/3 | §13 | unit test on constants |
| T0.3 | `metrics.py` data model: `Callable(contract, signature, kind, file, start_line, end_line, cc)`, `Metric(callable, coverage, crap)` | §3, §8 | dataclasses + kind enum |

## Milestone 1: Pure core (no toolchain)
| ID | Task | Spec | Done when |
|----|------|------|-----------|
| T1.1 | `crap(cc, cov)` formula | §10 | cov 0 / 0.5 / 1 cases |
| T1.2 | CC clamp `max(1, cc)` helper | §8.1 | cc 0 → 1 |
| T1.3 | LCOV parser: `SF`/`DA`/`end_of_record` → `{path: {line: hits}}`; ignore `FN*`, keep `BRDA` raw for P2 | §7.3 | multi-file sample parses |
| T1.4 | LCOV edge cases: missing file / empty → `None` | §7 | tests |
| T1.5 | SF path normalization (absolute + relative → module-relative) | §9.1 | both forms map equal |
| T1.6 | Line attribution: hit DA in [start,end] / DA in range | §9.1 | partial / full / zero |
| T1.7 | Attribution N/A: no DA in range, file absent → coverage & CRAP `None` | §9.1 | tests |
| T1.8 | Report sort: CRAP desc, N/A last, ties contract → signature | §11 | ordering tests |
| T1.9 | Report render: columns Function, Contract, Kind, CC, Cov%, CRAP; `N/A` | §11 | golden-string test |
| T1.10 | Threshold: max numeric (0.0 if none); `>8.0` → stderr `CRAP threshold exceeded: <max> > 8.0`, code 2 | §12 | boundary 8.0 not exceeded |

## Milestone 2: File selection + modules
| ID | Task | Spec | Done when |
|----|------|------|-----------|
| T2.1 | Default selection: `src/**/*.sol` | §5 | tmp_path tree test |
| T2.2 | Exclusions: `lib/ test/ script/ node_modules/`, `*.t.sol`, `*.s.sol` | §5 | tests |
| T2.3 | Explicit paths: file direct, dir → `<dir>/src/**`; dedupe + sort | §4, §5 | tests |
| T2.4 | `--changed`: parse `git status --porcelain` (M, A, ??, rename → new path), filter to `src/`, sort | §5 | parser test with injected output |
| T2.5 | `--changed` real git in tmp repo | §5 | integration-lite test |
| T2.6 | Module root: walk up to `foundry.toml`, bounded by project root, fallback root | §3, §6 | nested / none cases |
| T2.7 | Group files by module root | §6 | grouping test |

## Milestone 3: Adapters
| ID | Task | Spec | Done when |
|----|------|------|-----------|
| T3.1 | Coverage runner: delete stale `lcov.info`, run `forge coverage --report lcov --report-file …` in module cwd (subprocess injected) | §7 | fake-runner test checks argv/cwd |
| T3.2 | Runner errors: non-zero → `AnalysisError`; missing/empty lcov → stderr warning, module all N/A | §7, §14 | tests |
| T3.3 | Fixture project `tests/fixtures/foundry-sample` (see list below) | — | `forge test` passes there |
| T3.4 | Slither load `Slither(module_root)`; compile failure → `AnalysisError` | §8, §14 | `@pytest.mark.slither` |
| T3.5 | Collect `functions_declared` + `modifiers_declared` + `functions_top_level`, filter by file + declarer | §8 | no inherited dups |
| T3.6 | Exclusions: `not is_implemented`, `slitherConstructor*` | §8 | interface/abstract excluded |
| T3.7 | Kind mapping (function/modifier/constructor/receive/fallback/free) + overload-safe signature + `<file>` contract for free fns | §8 | tests |
| T3.8 | Line range from `source_mapping.lines`; CC via `slither.utils.code_complexity.compute_cyclomatic_complexity` | §8, §8.1 | CC values on fixture fns |
| T3.9 | Multiple compilation units: iterate all, dedupe by (file, signature) | §8 | fixture with 2 pragma versions |

## Milestone 4: CLI + end-to-end (Phase 1 complete)
| ID | Task | Spec | Done when |
|----|------|------|-----------|
| T4.1 | argparse: `--help` (0), bad args → usage (1), `--coverage line\|branch`, `--changed`, paths | §4 | tests |
| T4.2 | `--coverage branch` → `Branch coverage not implemented yet.` stderr, exit 1 | §4, §17 | test |
| T4.3 | Empty selection → `No Solidity files to analyze.`, exit 0 | §5 | test |
| T4.4 | Orchestration per module: coverage → callables → metrics → report → threshold | §6–§12 | fake adapters test |
| T4.5 | Error mapping: `AnalysisError` / `OSError` → stderr, exit 3 | §13, §14 | test |
| T4.6 | E2E on fixture: rows, order, exit 2; `--changed`; explicit path | §16 | `@pytest.mark.e2e` |
| T4.7 | README: install, usage, exit codes, CC limitations, via-IR note | — | reviewed |

Fixture contents (T3.3): low-CRAP covered fn, branchy uncovered fn (CRAP > 8), modifier, constructor,
receive, fallback, free fn, overloads, interface (excluded), inherited fn (no dup), `test/` + `*.t.sol` (excluded), `lib/` (excluded).

## Milestone 5: Phase 2: branch coverage
| ID | Task | Spec | Done when |
|----|------|------|-----------|
| T5.0 | **Decide** branch-less callable fallback (spec says TBD), e.g. fall back to line coverage or treat as 100%; update spec | §9.2 | spec PR merged |
| T5.1 | LCOV `BRDA` parse: `(line, block, branch, taken)`; `-` = 0 | §9.2 | tests |
| T5.2 | Branch attribution: taken / total BRDA in range | §9.2 | tests |
| T5.3 | Apply T5.0 fallback rule | §9.2 | tests |
| T5.4 | Coverage-mode strategy: `metrics` picks line vs branch attribution | §4 | both modes tested |
| T5.5 | CLI: remove branch rejection, wire `--coverage branch` | §4, §17 | test |
| T5.6 | E2E branch mode on fixture (verify forge emits BRDA for if/ternary/require) | §9.2 | `@pytest.mark.e2e` |
| T5.7 | Spec + README update: §17 phase 2 done, drop branch from out-of-scope | §2, §17 | reviewed |

## Dependencies
M0 → M1 → (M2 ∥ M3) → M4 → M5. Inside a milestone, tasks are mostly sequential by ID; T1.8–T1.10 need only T0.3/T1.1.

## Risks
- `forge coverage` with via-IR / stack-too-deep: may need `--ir-minimum`; P1 passes failure through (exit 3).
- Slither `source_mapping.lines` for modifiers / free fns: verify in T3.8.
- forge BRDA granularity (does `require` count as a branch?): verify in T5.6 before finalizing T5.0.

## Verification
- `uv run pytest` (unit, no toolchain).
- `uv run pytest -m "slither or e2e"` with forge + solc/slither installed.
- Manual: in `tests/fixtures/foundry-sample`: `uv run crap4sol; echo $?` → worst-first table, exit 2;
  `--help` → 0; `--coverage branch` → 1 (P1) / table (P2).
