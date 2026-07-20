# Task Contract

## Goal

Build a complete, local, dependency-free browser Sudoku application that is playable, accessible, and backed by deterministically tested core logic.

## Acceptance Criteria

- AC1: User can start a new puzzle (with selectable difficulty), and the board renders 9x9.
- AC2: User can select a cell (mouse or keyboard) and input digits 1-9; given cells are locked and cannot be edited.
- AC3: User can clear a cell, reset the puzzle to its starting state, check the current solution, and reveal/solve the puzzle.
- AC4: Given (clue) cells are visually distinct from user-entered cells.
- AC5: Duplicate entries in a row/column/box are detected and highlighted without breaking the app; play continues.
- AC6: A puzzle generator produces puzzles with a unique, complete solution; built-in puzzles also exist as deterministic fallback.
- AC7: Full keyboard support (arrow navigation, digit entry, delete/backspace) and ARIA labels + visible focus states.
- AC8: Core Sudoku logic (solver, validity, conflict detection, generator uniqueness) has deterministic, passing tests.

## Constraints

- No runtime/build dependencies; vanilla HTML/CSS/JS (ES modules). Tests may use Node's built-in `node:test` runner (no third-party deps).
- App must run locally by opening `index.html` in a browser (no server build step required).
- Simple, maintainable, minimal code.

## Non-Goals

- No backend, accounts, persistence to a server, multiplayer, or timer leaderboards.
- No CSS/JS frameworks or bundlers.
- No deployment / PR / publishing.

## Assumptions

- Modern evergreen browser supporting ES modules.
- Node 20+ available for running tests (confirmed: v20.20.1).
- "Local" means file-served static assets.

## Risk Tier

low

## Verification Plan

- Run `node --test` in the app dir; all core-logic tests pass deterministically.
- Manual/static review of UI wiring against acceptance criteria (no browser automation available in this environment — documented as a limitation).

## Escalation Conditions

- None expected: no secrets, no migrations, no network, no auth. Escalate only if a required capability (Node) were missing.
