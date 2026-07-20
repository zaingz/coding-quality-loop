# Sudoku

A small, dependency-free browser Sudoku game. Pure HTML/CSS/ES modules; the
core logic is isolated in `sudoku.js` and unit-tested with Node's built-in test
runner.

## Run the app

Open `index.html` directly in a modern browser, or serve the folder statically:

```bash
npx --yes serve .
# then open the printed URL
```

(A static server is only needed if your browser blocks ES module loading from
`file://`.)

## Play

- Click a cell or move with the arrow keys.
- Type `1`-`9` to fill the selected cell; `Backspace`/`Delete`/`0` clears it.
- The on-screen keypad does the same.
- Given numbers are locked and shaded.
- Duplicate numbers in a row, column, or box are highlighted in red.
- **Check** validates the board, **Solve** reveals the answer, **Reset**
  restores the starting puzzle, **New puzzle** generates a fresh one.

## Test

```bash
node --test
```

Tests cover the solver, unique-solution puzzle generation, RNG determinism,
conflict detection, and solved/complete checks.

## Files

- `sudoku.js` — pure logic (no DOM): RNG, MRV backtracking solver, generator, conflict detection.
- `main.js` — UI controller (DOM wiring, keyboard, rendering).
- `index.html` / `styles.css` — markup and responsive styles.
- `sudoku.test.js` — deterministic `node:test` suite.
