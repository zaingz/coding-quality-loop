// Core Sudoku logic. Pure functions, no DOM. Usable in browser and Node.

export const SIZE = 9;
export const BOX = 3;
export const EMPTY = 0;

// A board is a flat array of 81 integers (0 = empty, 1-9 = filled).

export function indexToRowCol(index) {
  return { row: Math.floor(index / SIZE), col: index % SIZE };
}

export function rowColToIndex(row, col) {
  return row * SIZE + col;
}

export function cloneBoard(board) {
  return board.slice();
}

export function emptyBoard() {
  return new Array(SIZE * SIZE).fill(EMPTY);
}

// Returns true if placing `value` at (row,col) breaks no Sudoku constraint.
// Ignores the cell itself so it can validate already-placed values.
export function isPlacementValid(board, row, col, value) {
  if (value === EMPTY) return true;
  for (let i = 0; i < SIZE; i++) {
    if (i !== col && board[rowColToIndex(row, i)] === value) return false;
    if (i !== row && board[rowColToIndex(i, col)] === value) return false;
  }
  const boxRow = Math.floor(row / BOX) * BOX;
  const boxCol = Math.floor(col / BOX) * BOX;
  for (let r = boxRow; r < boxRow + BOX; r++) {
    for (let c = boxCol; c < boxCol + BOX; c++) {
      if ((r !== row || c !== col) && board[rowColToIndex(r, c)] === value) {
        return false;
      }
    }
  }
  return true;
}

// Returns a Set of flat indices that participate in a duplicate conflict.
export function findConflicts(board) {
  const conflicts = new Set();
  for (let row = 0; row < SIZE; row++) {
    for (let col = 0; col < SIZE; col++) {
      const idx = rowColToIndex(row, col);
      const value = board[idx];
      if (value !== EMPTY && !isPlacementValid(board, row, col, value)) {
        conflicts.add(idx);
      }
    }
  }
  return conflicts;
}

export function isComplete(board) {
  return board.every((v) => v !== EMPTY);
}

export function isSolved(board) {
  return isComplete(board) && findConflicts(board).size === 0;
}

// Deterministic PRNG (mulberry32) so puzzle generation can be seeded for tests.
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

function shuffled(array, rng) {
  const a = array.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// Fills an empty board with a valid complete solution via backtracking.
export function fillSolution(board, rng = Math.random) {
  const idx = board.indexOf(EMPTY);
  if (idx === -1) return true;
  const { row, col } = indexToRowCol(idx);
  const candidates = shuffled([1, 2, 3, 4, 5, 6, 7, 8, 9], rng);
  for (const value of candidates) {
    if (isPlacementValid(board, row, col, value)) {
      board[idx] = value;
      if (fillSolution(board, rng)) return true;
      board[idx] = EMPTY;
    }
  }
  return false;
}

// Counts solutions up to `limit`. Used to guarantee puzzle uniqueness.
export function countSolutions(board, limit = 2) {
  const work = cloneBoard(board);
  let count = 0;

  function recurse() {
    if (count >= limit) return;
    const idx = work.indexOf(EMPTY);
    if (idx === -1) {
      count++;
      return;
    }
    const { row, col } = indexToRowCol(idx);
    for (let value = 1; value <= SIZE; value++) {
      if (isPlacementValid(work, row, col, value)) {
        work[idx] = value;
        recurse();
        work[idx] = EMPTY;
        if (count >= limit) return;
      }
    }
  }

  recurse();
  return count;
}

export function solve(board) {
  const work = cloneBoard(board);
  return fillSolution(work) ? work : null;
}

const DIFFICULTY_CLUES = {
  easy: 45,
  medium: 36,
  hard: 30,
};

// Generates { puzzle, solution }. Removes cells while preserving a unique
// solution. `clues` is the target number of filled cells.
export function generatePuzzle(difficulty = 'medium', seed) {
  const rng = seed === undefined ? Math.random : makeRng(seed);
  const solution = emptyBoard();
  fillSolution(solution, rng);

  const puzzle = cloneBoard(solution);
  const targetClues = DIFFICULTY_CLUES[difficulty] ?? DIFFICULTY_CLUES.medium;
  const order = shuffled(
    Array.from({ length: SIZE * SIZE }, (_, i) => i),
    rng
  );

  let filled = SIZE * SIZE;
  for (const idx of order) {
    if (filled <= targetClues) break;
    const backup = puzzle[idx];
    if (backup === EMPTY) continue;
    puzzle[idx] = EMPTY;
    if (countSolutions(puzzle, 2) !== 1) {
      puzzle[idx] = backup; // removal broke uniqueness; keep the clue
    } else {
      filled--;
    }
  }

  return { puzzle, solution, difficulty };
}

export const DIFFICULTIES = Object.keys(DIFFICULTY_CLUES);
