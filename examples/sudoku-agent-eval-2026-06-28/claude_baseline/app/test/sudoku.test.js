import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  isValidPlacement,
  findConflicts,
  isSolved,
  isComplete,
  solve,
  countSolutions,
  generatePuzzle,
  generateSolved,
  makeRng,
  rowColToIndex,
  indexToRowCol,
  CELLS,
} from '../src/sudoku.js';

// A known valid complete solution.
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

test('index <-> row/col round trip', () => {
  for (let i = 0; i < CELLS; i++) {
    const [r, c] = indexToRowCol(i);
    assert.equal(rowColToIndex(r, c), i);
  }
});

test('a correct solution has no conflicts and is solved', () => {
  assert.equal(findConflicts(SOLVED).size, 0);
  assert.ok(isComplete(SOLVED));
  assert.ok(isSolved(SOLVED));
});

test('findConflicts detects a duplicate in a row', () => {
  const board = SOLVED.slice();
  board[1] = board[0]; // create duplicate in first row
  const conflicts = findConflicts(board);
  assert.ok(conflicts.has(0));
  assert.ok(conflicts.has(1));
});

test('isValidPlacement rejects row/col/box conflicts', () => {
  const board = new Array(CELLS).fill(0);
  board[rowColToIndex(0, 0)] = 5;
  assert.equal(isValidPlacement(board, rowColToIndex(0, 8), 5), false); // same row
  assert.equal(isValidPlacement(board, rowColToIndex(8, 0), 5), false); // same col
  assert.equal(isValidPlacement(board, rowColToIndex(1, 1), 5), false); // same box
  assert.equal(isValidPlacement(board, rowColToIndex(4, 4), 5), true); // unrelated
});

test('solve fills an empty board into a valid solution', () => {
  const board = new Array(CELLS).fill(0);
  assert.ok(solve(board, makeRng(123)));
  assert.ok(isSolved(board));
});

test('solve completes a partially solved board', () => {
  const board = SOLVED.slice();
  const cleared = [0, 10, 20, 30, 40];
  cleared.forEach((i) => (board[i] = 0));
  assert.ok(solve(board));
  assert.ok(isSolved(board));
  // The unique completion must match the original.
  cleared.forEach((i) => assert.equal(board[i], SOLVED[i]));
});

test('countSolutions returns 1 for a solved board', () => {
  assert.equal(countSolutions(SOLVED.slice(), 2), 1);
});

test('countSolutions caps at the limit for an empty board', () => {
  assert.equal(countSolutions(new Array(CELLS).fill(0), 2), 2);
});

test('generatePuzzle (deterministic) yields a unique-solution puzzle', () => {
  const rng = makeRng(42);
  const { puzzle, solution } = generatePuzzle('easy', rng);
  assert.equal(puzzle.length, CELLS);
  assert.ok(isSolved(solution));
  // Every given clue agrees with the solution.
  for (let i = 0; i < CELLS; i++) {
    if (puzzle[i] !== 0) assert.equal(puzzle[i], solution[i]);
  }
  // Unique solution.
  assert.equal(countSolutions(puzzle.slice(), 2), 1);
  // Solving the puzzle reproduces the solution.
  const solved = puzzle.slice();
  solve(solved);
  assert.deepEqual(solved, solution);
});

test('generatePuzzle is reproducible for a fixed seed', () => {
  const a = generatePuzzle('medium', makeRng(7)).puzzle;
  const b = generatePuzzle('medium', makeRng(7)).puzzle;
  assert.deepEqual(a, b);
});

test('generateSolved produces a valid full board', () => {
  assert.ok(isSolved(generateSolved(makeRng(9))));
});
