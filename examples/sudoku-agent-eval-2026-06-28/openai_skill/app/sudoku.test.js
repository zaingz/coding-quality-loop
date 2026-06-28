import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  SIZE,
  CELLS,
  rowOf,
  colOf,
  boxOf,
  indexOf,
  mulberry32,
  isSafe,
  findConflicts,
  solve,
  countSolutions,
  generateSolvedBoard,
  generatePuzzle,
  isComplete,
  isSolved,
  isValidSolution,
} from './sudoku.js';

const SEEDS = [1, 7, 42, 123, 2024];

test('index helpers map row/col/box correctly', () => {
  assert.equal(rowOf(0), 0);
  assert.equal(colOf(0), 0);
  assert.equal(boxOf(0), 0);
  assert.equal(rowOf(80), 8);
  assert.equal(colOf(80), 8);
  assert.equal(boxOf(80), 8);
  assert.equal(boxOf(indexOf(4, 4)), 4); // center box
  assert.equal(boxOf(indexOf(0, 8)), 2);
  assert.equal(boxOf(indexOf(8, 0)), 6);
});

test('mulberry32 is deterministic for a seed and differs across seeds', () => {
  const a = mulberry32(42);
  const b = mulberry32(42);
  const seqA = [a(), a(), a()];
  const seqB = [b(), b(), b()];
  assert.deepEqual(seqA, seqB);
  const c = mulberry32(43);
  assert.notDeepEqual(seqA, [c(), c(), c()]);
});

test('generateSolvedBoard produces a full, rule-valid board', () => {
  for (const seed of SEEDS) {
    const board = generateSolvedBoard(mulberry32(seed));
    assert.ok(isComplete(board), `seed ${seed} board complete`);
    assert.equal(findConflicts(board).size, 0, `seed ${seed} no conflicts`);
    assert.ok(isValidSolution(board));
  }
});

test('generateSolvedBoard is deterministic per seed', () => {
  const first = generateSolvedBoard(mulberry32(123));
  const second = generateSolvedBoard(mulberry32(123));
  assert.deepEqual(first, second);
});

test('generatePuzzle yields a uniquely solvable puzzle whose solution is correct', () => {
  for (const seed of SEEDS) {
    const { puzzle, solution, givens } = generatePuzzle(seed, 'medium');
    assert.equal(puzzle.length, CELLS);
    assert.equal(countSolutions(puzzle, 2), 1, `seed ${seed} unique solution`);
    assert.ok(isValidSolution(solution), `seed ${seed} solution valid`);
    // every given matches the solution and is non-zero
    for (let i = 0; i < CELLS; i++) {
      if (givens[i]) {
        assert.notEqual(puzzle[i], 0);
        assert.equal(puzzle[i], solution[i]);
      } else {
        assert.equal(puzzle[i], 0);
      }
    }
    const clueCount = givens.filter(Boolean).length;
    assert.ok(clueCount >= 17, `seed ${seed} has a sane clue count (${clueCount})`);
    assert.ok(clueCount < CELLS, `seed ${seed} actually removed cells`);
  }
});

test('generatePuzzle is deterministic per seed', () => {
  const a = generatePuzzle(2024, 'medium');
  const b = generatePuzzle(2024, 'medium');
  assert.deepEqual(a.puzzle, b.puzzle);
  assert.deepEqual(a.solution, b.solution);
});

test('difficulty affects clue count (easy strictly keeps more clues than hard)', () => {
  for (const seed of SEEDS) {
    const easy = generatePuzzle(seed, 'easy').givens.filter(Boolean).length;
    const hard = generatePuzzle(seed, 'hard').givens.filter(Boolean).length;
    // easy targets 45 clues, hard targets 30; allow slack for uniqueness retention
    assert.ok(easy >= 40, `seed ${seed}: easy clues ${easy} >= 40`);
    assert.ok(hard <= 35, `seed ${seed}: hard clues ${hard} <= 35`);
    assert.ok(easy > hard, `seed ${seed}: easy(${easy}) > hard(${hard})`);
  }
});

test('solve recovers the unique solution of a generated puzzle', () => {
  for (const seed of SEEDS) {
    const { puzzle, solution } = generatePuzzle(seed, 'hard');
    const solved = solve(puzzle);
    assert.ok(solved, `seed ${seed} solvable`);
    assert.deepEqual(solved, solution, `seed ${seed} matches solution`);
  }
});

test('solve does not mutate the input board', () => {
  const { puzzle } = generatePuzzle(7, 'medium');
  const copy = puzzle.slice();
  solve(puzzle);
  assert.deepEqual(puzzle, copy);
});

test('solve returns null for an unsolvable board', () => {
  const board = new Array(CELLS).fill(0);
  board[0] = 5;
  board[1] = 5; // duplicate in the same row => unsolvable
  assert.equal(solve(board), null);
});

test('findConflicts detects row duplicates', () => {
  const board = new Array(CELLS).fill(0);
  board[indexOf(0, 0)] = 4;
  board[indexOf(0, 5)] = 4;
  const conflicts = findConflicts(board);
  assert.deepEqual([...conflicts].sort((a, b) => a - b), [indexOf(0, 0), indexOf(0, 5)]);
});

test('findConflicts detects column duplicates', () => {
  const board = new Array(CELLS).fill(0);
  board[indexOf(0, 2)] = 8;
  board[indexOf(6, 2)] = 8;
  const conflicts = findConflicts(board);
  assert.ok(conflicts.has(indexOf(0, 2)) && conflicts.has(indexOf(6, 2)));
  assert.equal(conflicts.size, 2);
});

test('findConflicts detects box duplicates', () => {
  const board = new Array(CELLS).fill(0);
  board[indexOf(0, 0)] = 3;
  board[indexOf(1, 1)] = 3; // same top-left box
  const conflicts = findConflicts(board);
  assert.ok(conflicts.has(indexOf(0, 0)) && conflicts.has(indexOf(1, 1)));
});

test('findConflicts returns empty for a valid solution and ignores empty cells', () => {
  const solution = generateSolvedBoard(mulberry32(5));
  assert.equal(findConflicts(solution).size, 0);
  const empty = new Array(CELLS).fill(0);
  assert.equal(findConflicts(empty).size, 0);
});

test('isSafe respects row/col/box and ignores the cell itself', () => {
  const board = new Array(CELLS).fill(0);
  board[indexOf(0, 0)] = 7;
  assert.equal(isSafe(board, indexOf(0, 4), 7), false); // same row
  assert.equal(isSafe(board, indexOf(4, 0), 7), false); // same col
  assert.equal(isSafe(board, indexOf(2, 2), 7), false); // same box
  assert.equal(isSafe(board, indexOf(4, 4), 7), true);
  assert.equal(isSafe(board, indexOf(0, 0), 7), true); // ignores itself
});

test('isSolved is true only for full correct board', () => {
  const { puzzle, solution } = generatePuzzle(11, 'medium');
  assert.equal(isSolved(puzzle, solution), false); // incomplete
  assert.equal(isSolved(solution, solution), true); // correct

  const wrong = solution.slice();
  // swap two cells to make it filled-but-wrong while staying full
  const i = 0;
  let j = 1;
  while (solution[j] === solution[i]) j++;
  [wrong[i], wrong[j]] = [wrong[j], wrong[i]];
  assert.equal(isComplete(wrong), true);
  assert.equal(isSolved(wrong, solution), false);
});

test('SIZE invariant', () => {
  assert.equal(SIZE, 9);
  assert.equal(CELLS, 81);
});
