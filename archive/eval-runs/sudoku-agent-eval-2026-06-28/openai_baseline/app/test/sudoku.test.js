import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  SIZE,
  EMPTY,
  emptyBoard,
  rowColToIndex,
  isPlacementValid,
  findConflicts,
  isComplete,
  isSolved,
  fillSolution,
  countSolutions,
  solve,
  generatePuzzle,
  makeRng,
  DIFFICULTIES,
} from '../src/sudoku.js';

const SOLVED = [
  5, 3, 4, 6, 7, 8, 9, 1, 2,
  6, 7, 2, 1, 9, 5, 3, 4, 8,
  1, 9, 8, 3, 4, 2, 5, 6, 7,
  8, 5, 9, 7, 6, 1, 4, 2, 3,
  4, 2, 6, 8, 5, 3, 7, 9, 1,
  7, 1, 3, 9, 2, 4, 8, 5, 6,
  9, 6, 1, 5, 3, 7, 2, 8, 4,
  2, 8, 7, 4, 1, 9, 6, 3, 5,
  3, 4, 5, 2, 8, 6, 1, 7, 9,
];

test('a known valid grid is reported solved', () => {
  assert.equal(isSolved(SOLVED), true);
  assert.equal(isComplete(SOLVED), true);
  assert.equal(findConflicts(SOLVED).size, 0);
});

test('isPlacementValid rejects row, column, and box duplicates', () => {
  const board = emptyBoard();
  board[rowColToIndex(0, 0)] = 5;
  assert.equal(isPlacementValid(board, 0, 8, 5), false, 'row duplicate');
  assert.equal(isPlacementValid(board, 8, 0, 5), false, 'column duplicate');
  assert.equal(isPlacementValid(board, 1, 1, 5), false, 'box duplicate');
  assert.equal(isPlacementValid(board, 4, 4, 5), true, 'unrelated cell ok');
});

test('isPlacementValid ignores the target cell itself', () => {
  const board = SOLVED.slice();
  // The value already at (0,0) is 5; re-validating it must pass.
  assert.equal(isPlacementValid(board, 0, 0, SOLVED[0]), true);
});

test('findConflicts pinpoints duplicate cells', () => {
  const board = emptyBoard();
  board[rowColToIndex(0, 0)] = 7;
  board[rowColToIndex(0, 5)] = 7; // same row conflict
  const conflicts = findConflicts(board);
  assert.equal(conflicts.has(rowColToIndex(0, 0)), true);
  assert.equal(conflicts.has(rowColToIndex(0, 5)), true);
  assert.equal(conflicts.size, 2);
});

test('a board with a conflict is not solved even if complete', () => {
  const board = SOLVED.slice();
  // Introduce a duplicate by overwriting a cell with a conflicting value.
  board[rowColToIndex(0, 1)] = 5; // (0,0) already 5 -> row conflict
  assert.equal(isComplete(board), true);
  assert.equal(isSolved(board), false);
});

test('solve completes a puzzle and matches constraints', () => {
  const { puzzle } = generatePuzzle('easy', 12345);
  const solved = solve(puzzle);
  assert.notEqual(solved, null);
  assert.equal(isSolved(solved), true);
  // The solution must agree with all given clues.
  for (let i = 0; i < puzzle.length; i++) {
    if (puzzle[i] !== EMPTY) assert.equal(solved[i], puzzle[i]);
  }
});

test('fillSolution produces a valid complete grid', () => {
  const board = emptyBoard();
  const ok = fillSolution(board, makeRng(99));
  assert.equal(ok, true);
  assert.equal(isSolved(board), true);
});

test('generatePuzzle is deterministic for a fixed seed', () => {
  const a = generatePuzzle('medium', 2024);
  const b = generatePuzzle('medium', 2024);
  assert.deepEqual(a.puzzle, b.puzzle);
  assert.deepEqual(a.solution, b.solution);
});

test('generated puzzles have exactly one solution', () => {
  for (const difficulty of DIFFICULTIES) {
    const { puzzle, solution } = generatePuzzle(difficulty, 777);
    assert.equal(countSolutions(puzzle, 2), 1, `${difficulty} unique`);
    assert.equal(isSolved(solution), true, `${difficulty} solution valid`);
    // Puzzle must be a subset of its solution.
    for (let i = 0; i < puzzle.length; i++) {
      if (puzzle[i] !== EMPTY) assert.equal(puzzle[i], solution[i]);
    }
  }
});

test('generated puzzle has fewer clues than a full grid', () => {
  const { puzzle } = generatePuzzle('hard', 555);
  const clues = puzzle.filter((v) => v !== EMPTY).length;
  assert.ok(clues < SIZE * SIZE, 'cells were removed');
  assert.ok(clues >= 17, 'keeps at least the theoretical minimum');
});

test('countSolutions detects multiple solutions on an empty-ish board', () => {
  const board = emptyBoard();
  assert.ok(countSolutions(board, 2) >= 2);
});
