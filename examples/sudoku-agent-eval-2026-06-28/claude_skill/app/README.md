# Sudoku

A small, dependency-free browser Sudoku game with deterministically tested core logic.

## Run

Open `index.html` in any modern browser. No build step or server is required
(it uses native ES modules loaded from local files).

If your browser blocks `file://` module loading, serve the folder statically:

```bash
python3 -m http.server 8000   # then open http://localhost:8000
```

## Play

- Click a cell or use **arrow keys** to move.
- Type **1-9** to fill, **Backspace/Delete/0** to clear. A number pad is also provided.
- **Given** clue cells are locked and shown in bold.
- Duplicate digits in a row, column, or box are highlighted in red as you play.
- **New puzzle** generates a fresh puzzle (Easy/Medium/Hard); **Reset** restores the
  starting clues; **Check** validates the current board; **Reveal solution** fills the answer.

## Test

Core logic (`sudoku.js`) is pure and DOM-free, tested with Node's built-in runner:

```bash
node --test
```

## Files

- `sudoku.js` — core logic: solver, validity, conflict detection, unique-solution generator, puzzle bank.
- `ui.js` — DOM controller (rendering, selection, keyboard, buttons).
- `index.html`, `styles.css` — markup and responsive styling.
- `sudoku.test.js` — deterministic test suite.
