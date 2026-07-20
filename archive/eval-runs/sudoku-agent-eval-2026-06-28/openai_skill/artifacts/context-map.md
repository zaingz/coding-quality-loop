# Context Map

Findings, not a repository dump. This is a greenfield app in an empty target folder.

## Goal Restated

Build a local browser Sudoku app + deterministic core-logic tests, zero runtime dependencies.

## Entry Points

- `app/index.html` — page the user opens; loads CSS and `main.js` (module).
- `app/main.js:init` — DOM wiring / UI controller (browser only).
- `app/sudoku.js` — pure core logic (browser + Node test import), no DOM.
- `app/sudoku.test.js` — Node `node:test` suite importing `sudoku.js`.

## Affected Surfaces

- APIs / contracts: none external. Internal module API of `sudoku.js` (pure functions).
- DB / schema / migrations: none.
- UI: full new Sudoku grid, controls, status region.
- Jobs / queues / schedules: none.
- Auth / security: none (no network, no storage of secrets).
- External integrations: none.

## Callers / Consumers Likely Affected

- None pre-existing — greenfield folder.

## Existing Patterns and Helpers to Reuse

- Native platform: `<table>`/CSS grid for board, CSS `:focus-visible`, ARIA roles.
- Standard library: Node built-in `node:test` + `node:assert` (no Jest/Mocha).
- No third-party packages required.

## Tests Covering (or That Should Cover) This

- `app/sudoku.test.js` via `node --test` — solver correctness, unique-solution generation, conflict detection, solved/complete checks, RNG determinism.

## Likely Files to Edit

- `app/index.html`, `app/styles.css`, `app/sudoku.js`, `app/main.js`, `app/sudoku.test.js`, `app/package.json`, `app/README.md`.

## Likely Verification Commands

- `cd app && node --test`
- `node -e "import('./sudoku.js')..."` smoke checks if needed.
