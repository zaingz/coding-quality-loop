// Core Sudoku logic: pure, dependency-free, and importable for tests.
// A board is a flat array of 81 numbers; 0 represents an empty cell.

export const SIZE = 9;
export const BOX = 3;
export const CELLS = SIZE * SIZE;

export function indexToRowCol(index) {
  return [Math.floor(index / SIZE), index % SIZE];
}

export function rowColToIndex(row, col) {
  return row * SIZE + col;
}

// Returns true if `value` (1-9) may be placed at `index` without conflicting
// with the existing entries in its row, column, or 3x3 box.
export function isValidPlacement(board, index, value) {
  const [row, col] = indexToRowCol(index);
  for (let i = 0; i < SIZE; i++) {
    if (board[rowColToIndex(row, i)] === value && rowColToIndex(row, i) !== index) return false;
    if (board[rowColToIndex(i, col)] === value && rowColToIndex(i, col) !== index) return false;
  }
  const boxRow = Math.floor(row / BOX) * BOX;
  const boxCol = Math.floor(col / BOX) * BOX;
  for (let r = boxRow; r < boxRow + BOX; r++) {
    for (let c = boxCol; c < boxCol + BOX; c++) {
      const idx = rowColToIndex(r, c);
      if (board[idx] === value && idx !== index) return false;
    }
  }
  return true;
}

// Returns a Set of indices that participate in a duplicate conflict
// (same value appearing more than once in a row, column, or box).
export function findConflicts(board) {
  const conflicts = new Set();
  const groups = [];
  for (let r = 0; r < SIZE; r++) groups.push(Array.from({ length: SIZE }, (_, c) => rowColToIndex(r, c)));
  for (let c = 0; c < SIZE; c++) groups.push(Array.from({ length: SIZE }, (_, r) => rowColToIndex(r, c)));
  for (let br = 0; br < SIZE; br += BOX) {
    for (let bc = 0; bc < SIZE; bc += BOX) {
      const box = [];
      for (let r = br; r < br + BOX; r++) {
        for (let c = bc; c < bc + BOX; c++) box.push(rowColToIndex(r, c));
      }
      groups.push(box);
    }
  }
  for (const group of groups) {
    const seen = new Map();
    for (const idx of group) {
      const v = board[idx];
      if (v === 0) continue;
      if (!seen.has(v)) seen.set(v, []);
      seen.get(v).push(idx);
    }
    for (const indices of seen.values()) {
      if (indices.length > 1) indices.forEach((i) => conflicts.add(i));
    }
  }
  return conflicts;
}

export function isComplete(board) {
  return board.every((v) => v !== 0);
}

export function isSolved(board) {
  return isComplete(board) && findConflicts(board).size === 0;
}

function shuffle(array, rng) {
  for (let i = array.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [array[i], array[j]] = [array[j], array[i]];
  }
  return array;
}

// Backtracking solver. Returns true if a solution was found (board mutated).
// Tries candidate values in a randomized order so it can also generate puzzles.
export function solve(board, rng = Math.random) {
  const empty = board.indexOf(0);
  if (empty === -1) return true;
  const candidates = shuffle([1, 2, 3, 4, 5, 6, 7, 8, 9], rng);
  for (const value of candidates) {
    if (isValidPlacement(board, empty, value)) {
      board[empty] = value;
      if (solve(board, rng)) return true;
      board[empty] = 0;
    }
  }
  return false;
}

// Counts solutions up to `limit` (used to verify a unique solution).
export function countSolutions(board, limit = 2) {
  const empty = board.indexOf(0);
  if (empty === -1) return 1;
  let count = 0;
  for (let value = 1; value <= SIZE; value++) {
    if (isValidPlacement(board, empty, value)) {
      board[empty] = value;
      count += countSolutions(board, limit);
      board[empty] = 0;
      if (count >= limit) return count;
    }
  }
  return count;
}

// Simple mulberry32 PRNG so generation can be made deterministic in tests.
export function makeRng(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function generateSolved(rng = Math.random) {
  const board = new Array(CELLS).fill(0);
  solve(board, rng);
  return board;
}

const DIFFICULTY_CLUES = { easy: 42, medium: 34, hard: 28 };

// Generates a puzzle with a unique solution by removing values from a solved
// board while preserving uniqueness. Returns { puzzle, solution }.
export function generatePuzzle(difficulty = 'medium', rng = Math.random) {
  const solution = generateSolved(rng);
  const puzzle = solution.slice();
  const targetClues = DIFFICULTY_CLUES[difficulty] ?? DIFFICULTY_CLUES.medium;
  const order = shuffle([...Array(CELLS).keys()], rng);
  let clues = CELLS;
  for (const idx of order) {
    if (clues <= targetClues) break;
    const backup = puzzle[idx];
    if (backup === 0) continue;
    puzzle[idx] = 0;
    const copy = puzzle.slice();
    if (countSolutions(copy, 2) !== 1) {
      puzzle[idx] = backup; // removal broke uniqueness; keep the clue
    } else {
      clues--;
    }
  }
  return { puzzle, solution };
}

export function cloneBoard(board) {
  return board.slice();
}
