# crap4sol

CRAP (Change Risk Anti-Patterns) quality gate for Foundry Solidity projects. Modeled on
[crap4java](https://github.com/unclebob/crap4java). See [spec.md](spec.md) for the full contract.

For each callable (function, modifier, constructor, `receive`, `fallback`, free function) it
combines line coverage from `forge coverage` with cyclomatic complexity from
[Slither](https://github.com/crytic/slither):

```
CRAP = CC² × (1 − coverage)³ + CC
```

It prints a table sorted worst-first and fails when the maximum CRAP exceeds the threshold `8.0`.

## Install

Requirements: Python ≥ 3.12, [Foundry](https://book.getfoundry.sh/) (`forge` on `PATH`).

From a checkout:

```sh
uv tool install .            # puts `crap4sol` on PATH
# or, without installing:
uv sync && uv run crap4sol --help
```

This installs `slither-analyzer` as a dependency.

## Usage

Run from the project root:

```sh
crap4sol                          # all .sol files under src/
crap4sol --changed                # changed/added/untracked .sol files under src/ (git status)
crap4sol src/Vault.sol pkg        # a file directly; a directory expands to <dir>/src/**/*.sol
crap4sol --coverage line          # coverage measure (default: line)
crap4sol --help
```

- Always excluded: anything under `lib/`, `test/`, `script/`, `node_modules/`, and `*.t.sol`,
  `*.s.sol` files.
- Files are grouped by module: the nearest ancestor holding `foundry.toml`, bounded by the
  project root. `forge coverage` and Slither run once per module.
- An empty selection prints `No Solidity files to analyze.` and exits `0`.
- `--coverage branch` is not implemented yet: it prints `Branch coverage not implemented yet.`
  to stderr and exits `1`.
- If `forge coverage` succeeds but writes no LCOV data, a warning is printed and that module's
  rows show `N/A` for coverage and CRAP.

Example output:

```
Function           Contract  Kind      CC    Cov%   CRAP
-----------------  --------  --------  --  ------  -----
classify(uint256)  Vault     function   5    0.0%  30.00
deposit(uint256)   Vault     function   1  100.0%   1.00
```

The table goes to stdout; warnings and errors go to stderr. Cov% rounds down and CRAP rounds up.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | success: empty selection, or max CRAP ≤ 8.0 (and the output was written) |
| 1 | usage error, including `--coverage branch` |
| 2 | CRAP threshold exceeded (max CRAP > 8.0); stderr `CRAP threshold exceeded: <max> > 8.0` |
| 3 | analysis failure: `forge coverage` failed (incl. failing tests), Slither/compile error, I/O error, `--changed` outside a git repo, unexpected internal error (e.g. analyzer crash), stdout not writable (closed pipe or fd, full disk), even for an empty selection, `--help` or a threshold breach |

The threshold is fixed at `8.0` and is not configurable.

## Limitations

- **Cyclomatic complexity** is Slither's CFG-based `E − N + 2`, clamped to ≥ 1. It counts
  `if/else`, loops, ternaries, `try/catch` clauses and early `return`/`break`/`continue`. It does
  **not** count short-circuit `&&` / `||`, `require` / `assert` / `revert` conditions, or modifier
  invocations at call sites. So a function guarded only by `require` scores CC 1.
- **via-IR**: `forge coverage` compiles without the optimizer and without via-IR. A project that
  only compiles with `via_ir = true` (e.g. "stack too deep" otherwise) makes `forge coverage`
  fail, and crap4sol exits `3`. crap4sol does not pass `--ir-minimum`.
- Line coverage only (branch coverage is planned for phase 2). No machine-readable output.
