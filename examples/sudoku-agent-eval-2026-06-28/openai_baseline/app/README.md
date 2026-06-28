# Sudoku

A playable, local browser Sudoku game with a unique-solution puzzle generator.
Zero runtime dependencies — plain HTML, CSS, and ES modules.

## Run

```bash
node server.js        # then open http://localhost:8080
# or: PORT=3000 node server.js
```

A tiny static server is included because ES modules must be loaded over HTTP
(the `file://` protocol blocks module imports).

## Test

```bash
node --test           # or: npm test
```

## Features

- New puzzle with Easy / Medium / Hard difficulty (generator guarantees a
  unique solution).
- Click or arrow-key navigation; type `1`-`9` to fill, `Backspace`/`Delete`/`0`
  or the Erase button to clear.
- Given cells are locked and visually distinct.
- Live duplicate detection across rows, columns, and 3×3 boxes (highlighted, app
  stays usable).
- Reset to starting clues, Check progress, and reveal the full Solution.
- Keyboard support, ARIA grid roles, per-cell labels, and visible focus states.

## Layout

- `index.html` — markup and control layout
- `styles.css` — responsive styling
- `src/sudoku.js` — pure game logic (validation, generator, solver)
- `src/app.js` — UI controller / DOM wiring
- `server.js` — minimal static file server
- `test/` — deterministic Node tests (core logic + DOM smoke test)
