# Validation Contract

Written before implementation. The validator checks the diff against this, not against implementer confidence.

## Goal

Build a playable, accessible local browser Sudoku app with deterministic core-logic tests.

## Done When (Acceptance Criteria → Proof)

| # | Acceptance criterion | Check that proves it | Type |
|---|---|---|---|
| 1 | New puzzle has a unique solution | Test: `generatePuzzle(seed)` -> `countSolutions(puzzle, 2) === 1` for several seeds | unit |
| 2 | Solver solves any solvable board correctly | Test: `solve(puzzle)` equals known `solution`; result passes full-validity check | unit |
| 3 | Conflict detection finds row/col/box duplicates | Test: crafted boards -> `findConflicts` returns exactly the expected conflicting indices | unit |
| 4 | Empty/clear and given-cell rules | Test: givens set is non-empty and consistent; `applyValue` rejects editing a given (logic-level) | unit |
| 5 | Solved check distinguishes complete-correct vs incomplete vs wrong | Test: `isSolved` true only for full correct board; false for incomplete and for filled-but-wrong | unit |
| 6 | RNG is deterministic | Test: same seed -> identical solved board and puzzle | unit |
| 7 | UI supports select, digit input, clear, reset, check, reveal, new game | Manual/static review of `main.js` event handlers + DOM (no browser automation available) | manual |
| 8 | Given cells locked & visually distinct; conflicts highlighted | Static review of CSS classes (`.given`, `.conflict`) + handler logic | manual |
| 9 | Keyboard + a11y (arrows, 1-9, Backspace; ARIA labels, focus states) | Static review of keydown handler, `aria-label`, `:focus-visible` CSS | manual |

## Must Not Change (Non-Goals / Invariants)

- No server, no network calls, no external dependencies introduced.
- `sudoku.js` stays DOM-free so it is importable under Node.

## Regression Risks

- Generator could emit a puzzle with multiple solutions → guarded by uniqueness test (AC1).
- Generator could be non-deterministic → guarded by RNG determinism test (AC6).
- Conflict highlighting could mark valid cells → guarded by conflict test (AC3).

## Required Evidence Before Ship

- `cd app && node --test` output showing all tests pass (capture counts).
- Completion record with file list and minimality decision.

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

No risk boundaries touched → no `security_reviewer` pass required (low-risk, offline, no deps).
