import { test } from "node:test";
import assert from "node:assert/strict";
import {
  SIZE,
  CELLS,
  emptyBoard,
  isValidPlacement,
  findConflicts,
  solve,
  countSolutions,
  generatePuzzle,
  generateSolution,
  makeRng,
  isComplete,
  rowOf,
  colOf,
  boxOf,
  BUILT_IN_PUZZLES,
} from "./sudoku.js";

function isFullValid(board) {
  return board.length === CELLS && board.every((v) => v >= 1 && v <= 9) && findConflicts(board).size === 0;
}

test("index helpers map cells correctly", () => {
  assert.equal(rowOf(0), 0);
  assert.equal(colOf(0), 0);
  assert.equal(boxOf(0), 0);
  assert.equal(boxOf(80), 8);
  assert.equal(boxOf(40), 4); // center
  assert.equal(rowOf(80), 8);
  assert.equal(colOf(80), 8);
});

test("isValidPlacement enforces row, col, and box", () => {
  const b = emptyBoard();
  b[0] = 5; // row 0, col 0
  assert.equal(isValidPlacement(b, 1, 5), false); // same row
  assert.equal(isValidPlacement(b, 9, 5), false); // same col
  assert.equal(isValidPlacement(b, 10, 5), false); // same box
  assert.equal(isValidPlacement(b, 13, 5), true); // unrelated
  // ignores the cell's own current value
  assert.equal(isValidPlacement(b, 0, 5), true);
});

test("findConflicts detects duplicates and ignores empties", () => {
  const b = emptyBoard();
  assert.equal(findConflicts(b).size, 0);
  b[0] = 7;
  b[1] = 7; // duplicate in row 0
  const c = findConflicts(b);
  assert.ok(c.has(0) && c.has(1));
  // a single valid value produces no conflict
  const b2 = emptyBoard();
  b2[40] = 9;
  assert.equal(findConflicts(b2).size, 0);
});

test("solve completes the built-in puzzle to its known solution", () => {
  const { puzzle, solution } = BUILT_IN_PUZZLES[0];
  const work = puzzle.slice();
  assert.equal(solve(work), true);
  assert.deepEqual(work, solution);
});

test("built-in puzzles each have a unique solution", () => {
  for (const p of BUILT_IN_PUZZLES) {
    assert.equal(countSolutions(p.puzzle, 2), 1);
    assert.ok(isFullValid(p.solution));
  }
});

test("generateSolution yields a complete valid grid (seeded => deterministic)", () => {
  const a = generateSolution(makeRng(123));
  const b = generateSolution(makeRng(123));
  assert.ok(isFullValid(a));
  assert.deepEqual(a, b); // determinism
});

test("generatePuzzle is deterministic, unique, and solvable per difficulty", () => {
  for (const difficulty of ["easy", "medium", "hard"]) {
    const r1 = generatePuzzle(difficulty, 42);
    const r2 = generatePuzzle(difficulty, 42);
    assert.deepEqual(r1.puzzle, r2.puzzle, `${difficulty} deterministic`);
    // unique solution
    assert.equal(countSolutions(r1.puzzle, 2), 1, `${difficulty} unique`);
    // solving the puzzle reproduces the stored solution
    const work = r1.puzzle.slice();
    assert.equal(solve(work), true);
    assert.deepEqual(work, r1.solution, `${difficulty} solution matches`);
    // given mask matches non-empty cells, and clues are a subset of solution
    for (let i = 0; i < CELLS; i++) {
      assert.equal(r1.given[i], r1.puzzle[i] !== 0);
      if (r1.given[i]) assert.equal(r1.puzzle[i], r1.solution[i]);
    }
  }
});

test("harder difficulty has fewer or equal clues than easier", () => {
  const easy = generatePuzzle("easy", 7).puzzle.filter((v) => v !== 0).length;
  const hard = generatePuzzle("hard", 7).puzzle.filter((v) => v !== 0).length;
  assert.ok(hard <= easy, `hard(${hard}) <= easy(${easy})`);
});

test("isComplete is true only for a fully solved valid board", () => {
  const { puzzle, solution } = BUILT_IN_PUZZLES[0];
  assert.equal(isComplete(puzzle), false);
  assert.equal(isComplete(solution), true);
  const broken = solution.slice();
  broken[0] = broken[0] === 1 ? 2 : 1; // introduce a duplicate
  assert.equal(isComplete(broken), false);
});
