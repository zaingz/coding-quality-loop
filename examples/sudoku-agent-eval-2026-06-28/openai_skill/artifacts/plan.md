# Plan

## Approach (one paragraph)

Build a vanilla HTML/CSS/ES-module app with zero runtime/build dependencies. Core Sudoku logic lives in a DOM-free module (`sudoku.js`) so it is unit-testable under Node's built-in `node:test`. The UI (`main.js`) is a thin controller that renders a 9x9 grid, tracks selection/state, and calls the core module. Determinism comes from a seeded `mulberry32` RNG, giving a real generator (unique-solution backtracking) that is also reproducible for tests — satisfying both "generator" and "deterministic tests" without a built-in static puzzle table.

### Complexity Brake (rung chosen)

Rung 8 (minimal new code) is required because the folder is greenfield — there is nothing to reuse or delete. Lower rungs rejected: no existing code (rungs 1-3 N/A); the algorithm needs custom backtracking (no stdlib primitive); native platform features (CSS grid, ARIA, `node:test`) ARE used instead of frameworks/test libs. No new dependency, framework, bundler, or service is added — justification: a static page + built-in test runner fully covers the requirements.

## Files / Modules to Change

- `app/sudoku.js` — pure logic: RNG, solver, solution generator, puzzle generator (unique-solution removal), conflict detection, solved/complete checks, cell index helpers.
- `app/main.js` — UI controller: render grid, selection, input/clear/reset/check/reveal/new, conflict + status rendering, keyboard handling.
- `app/index.html` — structure, controls, status live region, module script.
- `app/styles.css` — responsive grid, given/selected/conflict styles, focus-visible.
- `app/sudoku.test.js` — deterministic tests for all core functions.
- `app/package.json` — `"type": "module"`, `test` script.
- `app/README.md` — how to run + test.

## Implementation Slices (each reviewable, testable, revertible)

1. Core logic module `sudoku.js`.
2. Deterministic tests `sudoku.test.js`; run `node --test`.
3. UI: `index.html` + `styles.css` + `main.js`.
4. `package.json` + `README.md`; final verify.

## Verification Commands

- `cd app && node --test`

## Risks and Rollback

- Risks: generator emitting non-unique puzzles (guarded by uniqueness test); slow generation (bounded by clue floor + attempt cap).
- Rollback: delete the `app/` folder; no external state touched.

## Non-Goals

- No framework, bundler, backend, persistence, or scoring system.
