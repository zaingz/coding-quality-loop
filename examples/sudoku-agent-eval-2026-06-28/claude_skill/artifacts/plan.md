# Plan

## Approach (one paragraph)

Build a vanilla ES-module app. Complexity brake: rung 4/5 (stdlib + native platform) — use native DOM, CSS grid, and Node's built-in `node:test`; no framework, bundler, or runtime dependency is justified for a single-screen Sudoku. Core logic is a pure, DOM-free module (`sudoku.js`) so it is unit-testable in Node and reused by the browser controller (`ui.js`). A seeded RNG makes generation deterministic for tests. Lower rungs (no change / reuse existing) are impossible — greenfield dir; higher rungs (new deps/services) are unjustified.

## Files / Modules to Change

- `app/sudoku.js` — pure logic: board helpers, `isValidPlacement`, `findConflicts`, `solve`, `countSolutions`, `generatePuzzle`, seeded RNG, built-in puzzle bank.
- `app/ui.js` — DOM controller: render board, selection, keyboard, buttons, conflict highlight, status messages.
- `app/index.html` — shell + controls + ARIA structure.
- `app/styles.css` — responsive grid, given/selected/conflict/focus styles.
- `app/sudoku.test.js` — deterministic `node:test` suite.
- `app/package.json` — `"test": "node --test"`, type module.
- `app/README.md` — how to run/test.

## Implementation Slices

1. Core logic + tests (`sudoku.js`, `sudoku.test.js`); verify `node --test`.
2. UI controller + HTML + CSS (`ui.js`, `index.html`, `styles.css`).
3. Docs + package.json; final verify.

## Verification Commands

- `cd app && node --test`
- `node --check sudoku.js ui.js`

## Risks and Rollback

- Risks: generator performance / uniqueness; mitigated by digger with uniqueness check + bank fallback.
- Rollback: delete `app/` dir; greenfield, no external impact.

## Non-Goals

- No backend, persistence, frameworks, deployment, or PR.
