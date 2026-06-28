// Pure Sudoku core logic. No DOM access here so it can run under Node for tests.

export const SIZE = 9;
export const BOX = 3;
export const CELLS = SIZE * SIZE; // 81

export function rowOf(index) {
  return Math.floor(index / SIZE);
}

export function colOf(index) {
  return index % SIZE;
}

export function boxOf(index) {
  return Math.floor(rowOf(index) / BOX) * BOX + Math.floor(colOf(index) / BOX);
}

export function indexOf(row, col) {
  return row * SIZE + col;
}

export function createEmptyBoard() {
  return new Array(CELLS).fill(0);
}

export function cloneBoard(board) {
  return board.slice();
}

// Deterministic PRNG (mulberry32). Returns a function producing floats in [0, 1).
export function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Returns true if placing `value` at `index` breaks no row/col/box rule.
// Ignores the cell itself; treats 0 elsewhere as empty.
export function isSafe(board, index, value) {
  const row = rowOf(index);
  const col = colOf(index);
  const boxRow = Math.floor(row / BOX) * BOX;
  const boxCol = Math.floor(col / BOX) * BOX;

  for (let i = 0; i < SIZE; i++) {
    if (board[indexOf(row, i)] === value && indexOf(row, i) !== index) return false;
    if (board[indexOf(i, col)] === value && indexOf(i, col) !== index) return false;
  }
  for (let r = 0; r < BOX; r++) {
    for (let c = 0; c < BOX; c++) {
      const idx = indexOf(boxRow + r, boxCol + c);
      if (board[idx] === value && idx !== index) return false;
    }
  }
  return true;
}

// Returns a Set of indices of filled cells that duplicate another filled cell
// in the same row, column, or box. Empty cells are never conflicts.
export function findConflicts(board) {
  const conflicts = new Set();
  for (let index = 0; index < CELLS; index++) {
    const value = board[index];
    if (value === 0) continue;
    if (!isSafe(board, index, value)) conflicts.add(index);
  }
  return conflicts;
}

// Returns the empty cell with the fewest legal candidates (MRV heuristic),
// along with those candidate values. Returns null when the board is full.
// MRV keeps backtracking and uniqueness counting fast on sparse boards.
function selectCell(board) {
  let best = null;
  for (let index = 0; index < CELLS; index++) {
    if (board[index] !== 0) continue;
    const candidates = [];
    for (let value = 1; value <= SIZE; value++) {
      if (isSafe(board, index, value)) candidates.push(value);
    }
    if (candidates.length === 0) return { index, candidates }; // dead end
    if (best === null || candidates.length < best.candidates.length) {
      best = { index, candidates };
      if (candidates.length === 1) break;
    }
  }
  return best;
}

// Solve in place using MRV backtracking. Returns the solved board or null if unsolvable.
// `rng` optionally randomizes candidate order (used by the generator).
export function solve(board, rng = null) {
  if (findConflicts(board).size > 0) return null; // contradictory givens
  const work = cloneBoard(board);
  if (solveInPlace(work, rng)) return work;
  return null;
}

function shuffle(values, rng) {
  for (let i = values.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [values[i], values[j]] = [values[j], values[i]];
  }
  return values;
}

function solveInPlace(board, rng) {
  const cell = selectCell(board);
  if (cell === null) return true;
  if (cell.candidates.length === 0) return false;
  const values = rng ? shuffle(cell.candidates.slice(), rng) : cell.candidates;
  for (const value of values) {
    board[cell.index] = value;
    if (solveInPlace(board, rng)) return true;
    board[cell.index] = 0;
  }
  return false;
}

// Counts solutions up to `limit` (default 2 — enough to test uniqueness).
export function countSolutions(board, limit = 2) {
  const work = cloneBoard(board);
  let count = 0;
  const recurse = () => {
    const cell = selectCell(work);
    if (cell === null) {
      count++;
      return;
    }
    for (const value of cell.candidates) {
      work[cell.index] = value;
      recurse();
      work[cell.index] = 0;
      if (count >= limit) return;
    }
  };
  recurse();
  return count;
}

// Generates a fully solved valid board using randomized backtracking.
export function generateSolvedBoard(rng) {
  const board = createEmptyBoard();
  solveInPlace(board, rng);
  return board;
}

const DIFFICULTY_CLUES = {
  easy: 45,
  medium: 36,
  hard: 30,
};

// Generates a puzzle with a unique solution.
// Returns { puzzle, solution, givens } where givens is a boolean[] of locked cells.
// Deterministic for a given seed.
export function generatePuzzle(seed = Date.now(), difficulty = 'medium') {
  const rng = mulberry32(seed);
  const solution = generateSolvedBoard(rng);
  const puzzle = cloneBoard(solution);
  const targetClues = DIFFICULTY_CLUES[difficulty] ?? DIFFICULTY_CLUES.medium;

  const order = [];
  for (let i = 0; i < CELLS; i++) order.push(i);
  for (let i = order.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [order[i], order[j]] = [order[j], order[i]];
  }

  let clues = CELLS;
  for (const index of order) {
    if (clues <= targetClues) break;
    const saved = puzzle[index];
    if (saved === 0) continue;
    puzzle[index] = 0;
    if (countSolutions(puzzle, 2) === 1) {
      clues--;
    } else {
      puzzle[index] = saved; // removal broke uniqueness; keep the clue
    }
  }

  const givens = puzzle.map((v) => v !== 0);
  return { puzzle, solution, givens };
}

export function isComplete(board) {
  return board.every((v) => v !== 0);
}

// True only when the board is fully filled and matches the given solution.
export function isSolved(board, solution) {
  for (let i = 0; i < CELLS; i++) {
    if (board[i] === 0 || board[i] !== solution[i]) return false;
  }
  return true;
}

// True when a fully-filled board satisfies all Sudoku rules (no solution needed).
export function isValidSolution(board) {
  return isComplete(board) && findConflicts(board).size === 0;
}
