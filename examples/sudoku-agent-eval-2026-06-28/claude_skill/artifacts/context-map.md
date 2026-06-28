# Context Map

Findings, not a repository dump.

## Goal Restated

Build a standalone browser Sudoku app + tested core logic under `claude_skill/app`.

## Entry Points

- `app/index.html` — page shell, loads styles and `ui.js` as a module.
- `app/ui.js:init` — DOM wiring / controller, imports core logic.
- `app/sudoku.js` — pure core logic (no DOM): solver, validity, conflicts, generator, puzzle bank.
- `app/sudoku.test.js` — `node:test` suite over `sudoku.js`.

## Affected Surfaces

- APIs / contracts: internal ES module API of `sudoku.js` (consumed by `ui.js` and tests).
- DB / schema / migrations: none.
- UI: full new single-page UI.
- Jobs / queues / schedules: none.
- Auth / security: none (no input crosses a trust boundary; purely client-side).
- External integrations: none.

## Callers / Consumers Likely Affected

- None pre-existing — greenfield directory.

## Existing Patterns and Helpers to Reuse

- None in target dir (greenfield). Reuse platform primitives: native DOM, CSS grid, `node:test`/`node:assert` (stdlib), no external deps.

## Tests Covering (or That Should Cover) This

- `app/sudoku.test.js` via `node --test`.

## Likely Files to Edit

- `app/index.html`, `app/styles.css`, `app/sudoku.js`, `app/ui.js`, `app/sudoku.test.js`, `app/package.json`, `app/README.md`.

## Likely Verification Commands

- `cd app && node --test`
- `node --check` on each JS file for syntax.
