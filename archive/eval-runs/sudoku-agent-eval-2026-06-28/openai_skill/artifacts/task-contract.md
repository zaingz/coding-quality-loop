# Task Contract

## Goal

Build a complete, playable, local browser Sudoku application with a clean responsive UI and deterministic tests for the core logic.

## Acceptance Criteria

- AC1: User can start a new puzzle (new game button) that produces a valid Sudoku with a unique solution.
- AC2: User can select a cell (mouse + keyboard) and input digits 1-9.
- AC3: User can clear a selected cell.
- AC4: User can reset the puzzle back to its initial givens.
- AC5: User can check the current solution (correct / incorrect / incomplete feedback).
- AC6: User can reveal/solve the puzzle (fills the full correct solution).
- AC7: Given (clue) cells are locked (not editable) and visually distinct.
- AC8: Invalid duplicate entries in the same row/column/box are detected and highlighted, without breaking the app.
- AC9: A puzzle generator (or built-in puzzle set) provides puzzles with complete, correct solutions.
- AC10: Keyboard support (arrows to move, 1-9 to enter, Backspace/Delete to clear) and basic accessibility labels/focus states.
- AC11: Deterministic automated tests cover core Sudoku logic (solver, generator uniqueness, conflict detection, solved check) and pass.

## Constraints

- Minimal dependencies; prefer the standard library / native platform features.
- Runs locally in a browser by opening a file or simple static serve; no backend.
- Simple, maintainable code following plain ES modules.
- App under `.../openai_skill/app`; artifacts under `.../openai_skill/artifacts`.
- Do not push, publish, or open a PR.

## Non-Goals

- No multiplayer, persistence to a server, accounts, or timers/scoring leaderboards.
- No build toolchain/framework (React/Vue/bundler) unless strictly required.
- No difficulty-rating engine beyond a simple clue-count based difficulty.

## Assumptions

- Modern evergreen browser with ES module support (acceptable for local evaluation).
- Node.js (v20) available for running the deterministic test suite (`node --test`).
- "Deterministic tests" means seeded generation so results are reproducible.

## Risk Tier

low

## Verification Plan

- Run `node --test` in the app folder; all core-logic tests pass.
- Manual/static reasoning over DOM wiring (no browser automation tool available in this environment) — documented as a limitation.

## Escalation Conditions

- None expected: no secrets, no network, no auth, no destructive operations. Escalate only if a required browser/test runtime is unavailable.
