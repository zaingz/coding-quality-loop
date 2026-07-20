# Validation Contract

Written before implementation.

## Goal

A playable, accessible, dependency-free browser Sudoku app with deterministically tested core logic.

## Done When (Acceptance Criteria -> Proof)

| # | Acceptance criterion | Check that proves it | Type |
|---|---|---|---|
| 1 | New puzzle of chosen difficulty renders a 9x9 board | Test: `generatePuzzle(difficulty, rng)` returns 81-cell board + valid full solution; UI: `index.html` has 81 cells built by `ui.js` | unit + manual |
| 2 | Select cell + enter 1-9; given cells locked | Test: `isGiven` mask marks clues; UI handler rejects edits on given cells | unit + manual |
| 3 | Clear cell, reset, check, reveal/solve actions | Test: `solve()` solves any valid board; UI buttons wired to clear/reset/check/solve | unit + manual |
| 4 | Given cells visually distinct | Manual/static: `.given` CSS class styling distinct from user entries | manual |
| 5 | Duplicate row/col/box detected, app stays usable | Test: `findConflicts(board)` returns exact conflicting coordinates; entering a dup does not throw | unit + manual |
| 6 | Generator yields unique-solution puzzles; fallback bank with solutions | Test: `countSolutions()==1` for generated puzzles; built-in puzzles each solve to their stated solution | unit |
| 7 | Keyboard nav + ARIA + focus | Static: arrow/digit/delete key handlers; `aria-label`/`role` attrs; `:focus-visible` styles | manual |
| 8 | Core logic deterministically tested | `node --test` exits 0, all tests pass; generator seeded RNG => deterministic | unit |

## Must Not Change (Non-Goals / Invariants)

- No external dependencies introduced.
- Core logic module stays DOM-free (testable in Node).

## Regression Risks

- Generator could produce non-unique or unsolvable puzzles -> guarded by `countSolutions==1` test and solver test.
- Conflict detection false positives on empty cells -> guarded by explicit empty-cell test.

## Required Evidence Before Ship

- `cd app && node --test` output showing pass count.
- `node --check` on each source file.
- Static review notes mapping UI handlers to AC2/3/4/7.

## Risk Boundaries Touched

- [ ] auth / authorization
- [ ] secrets / credentials
- [ ] payments / billing
- [ ] PII / data privacy
- [ ] migrations / schema
- [ ] upload / download
- [ ] network calls
- [ ] shell / process execution
- [ ] dependency changes

No risk boundary touched -> no security_reviewer pass required.
