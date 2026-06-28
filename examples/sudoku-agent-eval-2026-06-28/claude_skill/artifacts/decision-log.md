# Decision Log

| # | Decision | Why (alternatives rejected) | Reversible? |
|---|---|---|---|
| 1 | Vanilla ES modules, zero deps | Single-screen game; framework/bundler unjustified at complexity-brake rungs 4-5 (stdlib/native). Keeps app openable via `file://`. | yes |
| 2 | Core logic in DOM-free `sudoku.js` | Lets `node:test` exercise logic without jsdom; UI reuses same module. | yes |
| 3 | Seeded Mulberry32 RNG, optional seed on `generatePuzzle` | Makes generation deterministic so uniqueness/solvability tests are stable; production calls omit seed for randomness. | yes |
| 4 | Generator = full-solve then dig with uniqueness check (`countSolutions(...,2)===1`) | Guarantees a unique solution; simpler and adequate vs. constraint-propagation graders. | yes |
| 5 | Keep a built-in puzzle bank as deterministic fallback | Requirement asks for robust built-in puzzles + solutions; also a safety net if generation is ever constrained. | yes |
| 6 | `node --check` for ui.js instead of headless DOM test | No jsdom/browser-automation available; UI verified by syntax check + static review (limitation documented). | n/a |
