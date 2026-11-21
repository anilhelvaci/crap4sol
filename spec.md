> **Status: DRAFT** — under review, not yet approved. Modeled on
> [crap4java spec](https://github.com/unclebob/crap4java/blob/main/spec.md).

# crap4sol Specification

## 1. Purpose

`crap4sol` is a CRAP (Change Risk Anti-Patterns) metric analyzer for Solidity projects. It:

- discovers Solidity sources under `src/`,
- generates coverage with `forge coverage` once per Foundry project (module),
- computes cyclomatic complexity with Slither,
- combines both into CRAP scores,
- prints a table sorted worst-first,
- fails when the maximum CRAP score exceeds the threshold.

It is a quality gate, not a mutation or security tool.

Implementation: Python, built on [Slither](https://github.com/crytic/slither) (`slither-analyzer`).

## 2. Scope

In scope: CLI contract, source selection, module grouping, coverage generation, callable parsing,
CRAP computation, report ordering, exit codes.

Out of scope: Hardhat/Truffle/other non-Foundry builds, non-`.sol` files, machine-readable output,
CLI-configurable threshold, branch coverage implementation in phase 1 (see §17).

## 3. Terminology

- **Project root**: directory the tool is invoked from.
- **Module root**: nearest ancestor of an analyzed file containing `foundry.toml`, bounded by the
  project root. If none, the project root.
- **Callable**: a scored unit — function, modifier, constructor, `receive`, `fallback`, or free
  (file-level) function.
- **Callable metric**: one report row: identity, kind, complexity, coverage, CRAP.
- **Coverage N/A**: no usable coverage data for the callable.

## 4. CLI

```
crap4sol [--coverage line|branch]
crap4sol [--coverage line|branch] --changed
crap4sol [--coverage line|branch] <path...>
crap4sol --help
```

- No args: analyze all `.sol` files under `src/`.
- `--changed`: analyze changed `.sol` files under `src/`.
- `<path...>`: a file is analyzed directly; a directory expands to `.sol` files under its `src/` subtree.
- `--coverage line|branch`: coverage measure. Default `line`.
  - Phase 1: `branch` prints `Branch coverage not implemented yet.` to stderr and exits `1`.
- `--help`: print usage, exit `0`.
- Argument parse failure: print usage, exit `1`.

## 5. File selection

- Default: all `.sol` files under `<project-root>/src/**`.
- `--changed`: `git status --porcelain`; take modified, added, untracked `.sol` files under
  `<project-root>/src/`; sort by path.
- Explicit paths: files used directly; directories expand to `.sol` under `<dir>/src/**`.
  Dedupe, sort by path.
- Always excluded: anything under `lib/`, `test/`, `script/`, `node_modules/`; files matching
  `*.t.sol`, `*.s.sol`.
- Empty selection: print `No Solidity files to analyze.`, exit `0`.

## 6. Module grouping

- Group selected files by module root before coverage runs.
- For each file, walk up from its directory until `foundry.toml` is found or the walk leaves the
  project root; fallback = project root.
- Coverage generation and Slither analysis run once per module group.

## 7. Coverage pipeline (per module)

1. Delete stale `<module>/lcov.info`.
2. In module root run: `forge coverage --report lcov --report-file <module>/lcov.info`.
3. Parse LCOV.
4. Analyze the module's selected files.

- `forge coverage` non-zero exit (incl. failing tests) → fail fast (exit `3`).
- `lcov.info` missing or empty after a successful run → warning to stderr, all of that module's
  callables get Coverage N/A. Not fatal by itself.

## 8. Callable parsing (Slither)

- Load `Slither(<module-root>)` (crytic-compile, Foundry platform). No separate solc invocation.
- For each selected file collect:
  - `contract.functions_declared` — regular functions, constructor, `receive`, `fallback`;
  - `contract.modifiers_declared`;
  - compilation unit `functions_top_level` — free functions.
- Keep only callables whose source file is the selected file and whose declarer is that contract
  (no duplicate rows for inherited callables).
- Exclude:
  - unimplemented callables (no body: interface members, abstract declarations);
  - Slither-synthesized functions (e.g. `slitherConstructorVariables`,
    `slitherConstructorConstantVariables`).
- Identity: contract name (or `<file>` for free functions) + full signature (overload-safe) +
  source line range.
- Kind: `function | modifier | constructor | receive | fallback | free`.

### 8.1 Cyclomatic complexity

- CC = Slither `compute_cyclomatic_complexity(callable)` over its CFG (`E − N + 2`), clamped `≥ 1`.
- Counted (via CFG): `if/else`, `for`, `while`, `do-while`, ternary, `try/catch` clauses, early
  `return`/`break`/`continue` paths.
- Known limitation (not counted): short-circuit `&&`/`||`, `require`/`assert`/`revert` conditions,
  modifier invocations at call sites.

## 9. Coverage attribution

### 9.1 Line (phase 1)

- Normalize each LCOV `SF:` path to module-relative.
- Callable range = start/end lines from Slither `source_mapping`.
- coverage = (DA lines in range with hits > 0) / (DA lines in range).
- No DA lines in range, or file absent from LCOV → Coverage N/A, CRAP N/A.
- Solidity has no nested callables, so ranges don't overlap.

### 9.2 Branch (phase 2, not implemented)

- coverage = taken `BRDA` entries in range / total `BRDA` entries in range.
- Fallback when a callable has no branches: TBD.

## 10. CRAP formula

```
CRAP = CC² × (1 − coverage)³ + CC
```

`coverage` ∈ [0.0, 1.0].

## 11. Report

- Table columns: Function (signature), Contract, Kind, CC, Cov% (or `N/A`), CRAP (or `N/A`).
- Sort: CRAP descending; N/A rows after all numeric rows; ties by contract, then signature.

## 12. Threshold

- Threshold `8.0`. Take max numeric CRAP.
- Max > 8.0 → stderr `CRAP threshold exceeded: <max> > 8.0`, exit `2`.
- No numeric CRAP → max = `0.0`, not exceeded.

## 13. Exit codes

| Code | Meaning |
|------|---------|
| 0 | success (incl. empty selection, all ≤ threshold) |
| 1 | CLI usage error (incl. `--coverage branch` in phase 1) |
| 2 | CRAP threshold exceeded |
| 3 | analysis failure: `forge`, Slither/compile, or I/O error |

(Code `3` is an addition; the Java spec leaves the fail-fast code unspecified.)

## 14. Error handling

- Fail fast: invalid CLI usage, `forge coverage` failure, Slither/compilation failure, unreadable
  source file.
- Missing/empty LCOV: warning only.

## 15. Non-goals

- CLI-configurable threshold
- non-Foundry builds
- discovery outside `src/` rules
- mutation analysis, gas analysis, security detectors
- machine-readable output

## 16. Conformance

An implementation conforms if it meets §4–§14 for Foundry-built Solidity projects.

## 17. Phases

- **Phase 1**: everything above with line coverage. `--coverage` flag parsed; `branch` rejected
  (exit `1`).
- **Phase 2**: implement branch coverage (§9.2).
