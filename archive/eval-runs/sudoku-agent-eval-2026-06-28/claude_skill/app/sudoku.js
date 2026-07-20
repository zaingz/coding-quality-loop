// Pure, DOM-free Sudoku core logic. Reused by the browser UI and by node:test.
// A board is a length-81 array of integers; 0 means empty, 1-9 a filled value.

export const SIZE = 9;
export const BOX = 3;
export const CELLS = SIZE * SIZE;

export const rowOf = (i) => Math.floor(i / SIZE);
export const colOf = (i) => i % SIZE;
export const boxOf = (i) => Math.floor(rowOf(i) / BOX) * BOX + Math.floor(colOf(i) / BOX);

export function emptyBoard() {
  return new Array(CELLS).fill(0);
}

export function cloneBoard(board) {
  return board.slice();
}

// Mulberry32: small, fast, deterministic seeded PRNG so generation is testable.
export function makeRng(seed) {
  let a = seed >>> 0;
  return function next() {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffled(arr, rng) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// Can `val` (1-9) legally go at index `i`, ignoring whatever currently sits there?
export function isValidPlacement(board, i, val) {
  if (val === 0) return true;
  const r = rowOf(i);
  const c = colOf(i);
  const br = Math.floor(r / BOX) * BOX;
  const bc = Math.floor(c / BOX) * BOX;
  for (let k = 0; k < SIZE; k++) {
    const rowIdx = r * SIZE + k;
    if (rowIdx !== i && board[rowIdx] === val) return false;
    const colIdx = k * SIZE + c;
    if (colIdx !== i && board[colIdx] === val) return false;
  }
  for (let dr = 0; dr < BOX; dr++) {
    for (let dc = 0; dc < BOX; dc++) {
      const idx = (br + dr) * SIZE + (bc + dc);
      if (idx !== i && board[idx] === val) return false;
    }
  }
  return true;
}

// Set of cell indices that duplicate another filled value in their row/col/box.
export function findConflicts(board) {
  const conflicts = new Set();
  const scan = (indices) => {
    const seen = new Map();
    for (const i of indices) {
      const v = board[i];
      if (v === 0) continue;
      if (seen.has(v)) {
        conflicts.add(i);
        conflicts.add(seen.get(v));
      } else {
        seen.set(v, i);
      }
    }
  };
  for (let u = 0; u < SIZE; u++) {
    const row = [];
    const col = [];
    const box = [];
    for (let k = 0; k < SIZE; k++) {
      row.push(u * SIZE + k);
      col.push(k * SIZE + u);
      const br = Math.floor(u / BOX) * BOX;
      const bc = (u % BOX) * BOX;
      box.push((br + Math.floor(k / BOX)) * SIZE + (bc + (k % BOX)));
    }
    scan(row);
    scan(col);
    scan(box);
  }
  return conflicts;
}

export function isComplete(board) {
  return board.every((v) => v !== 0) && findConflicts(board).size === 0;
}

// Backtracking solver. With `rng`, candidate order is shuffled (used for generation).
// Fills `board` in place when a solution exists. Returns true if solved.
export function solve(board, rng = null) {
  let best = -1;
  let bestCands = null;
  for (let i = 0; i < CELLS; i++) {
    if (board[i] !== 0) continue;
    const cands = [];
    for (let v = 1; v <= SIZE; v++) if (isValidPlacement(board, i, v)) cands.push(v);
    if (cands.length === 0) return false; // dead end
    if (bestCands === null || cands.length < bestCands.length) {
      best = i;
      bestCands = cands;
      if (cands.length === 1) break; // can't do better than forced
    }
  }
  if (best === -1) return true; // no empties left -> solved
  const order = rng ? shuffled(bestCands, rng) : bestCands;
  for (const v of order) {
    board[best] = v;
    if (solve(board, rng)) return true;
    board[best] = 0;
  }
  return false;
}

// Count solutions up to `limit` (default 2 -> enough to test uniqueness).
export function countSolutions(board, limit = 2) {
  const work = cloneBoard(board);
  let count = 0;
  const recurse = () => {
    let idx = -1;
    let cands = null;
    for (let i = 0; i < CELLS; i++) {
      if (work[i] !== 0) continue;
      const c = [];
      for (let v = 1; v <= SIZE; v++) if (isValidPlacement(work, i, v)) c.push(v);
      if (c.length === 0) return;
      if (cands === null || c.length < cands.length) {
        idx = i;
        cands = c;
      }
    }
    if (idx === -1) {
      count++;
      return;
    }
    for (const v of cands) {
      work[idx] = v;
      recurse();
      work[idx] = 0;
      if (count >= limit) return;
    }
  };
  recurse();
  return count;
}

export function generateSolution(rng) {
  const board = emptyBoard();
  solve(board, rng);
  return board;
}

const DIFFICULTY_CLUES = { easy: 40, medium: 32, hard: 28 };

// Generate a puzzle with a UNIQUE solution by digging cells from a full grid.
// Returns { puzzle, solution, given } where given is a boolean mask of clues.
export function generatePuzzle(difficulty = "medium", seed) {
  const rng = makeRng(typeof seed === "number" ? seed : Math.floor(Math.random() * 2 ** 31));
  const solution = generateSolution(rng);
  const puzzle = cloneBoard(solution);
  const targetClues = DIFFICULTY_CLUES[difficulty] ?? DIFFICULTY_CLUES.medium;
  const order = shuffled(
    Array.from({ length: CELLS }, (_, i) => i),
    rng,
  );
  let clues = CELLS;
  for (const i of order) {
    if (clues <= targetClues) break;
    const backup = puzzle[i];
    if (backup === 0) continue;
    puzzle[i] = 0;
    // Keep the dig only if the puzzle still has exactly one solution.
    if (countSolutions(puzzle, 2) !== 1) {
      puzzle[i] = backup;
    } else {
      clues--;
    }
  }
  const given = puzzle.map((v) => v !== 0);
  return { puzzle, solution, given, difficulty };
}

// Deterministic fallback bank (one fully-solvable puzzle + its solution).
export const BUILT_IN_PUZZLES = [
  {
    difficulty: "easy",
    puzzle: [
      5, 3, 0, 0, 7, 0, 0, 0, 0,
      6, 0, 0, 1, 9, 5, 0, 0, 0,
      0, 9, 8, 0, 0, 0, 0, 6, 0,
      8, 0, 0, 0, 6, 0, 0, 0, 3,
      4, 0, 0, 8, 0, 3, 0, 0, 1,
      7, 0, 0, 0, 2, 0, 0, 0, 6,
      0, 6, 0, 0, 0, 0, 2, 8, 0,
      0, 0, 0, 4, 1, 9, 0, 0, 5,
      0, 0, 0, 0, 8, 0, 0, 7, 9,
    ],
    solution: [
      5, 3, 4, 6, 7, 8, 9, 1, 2,
      6, 7, 2, 1, 9, 5, 3, 4, 8,
      1, 9, 8, 3, 4, 2, 5, 6, 7,
      8, 5, 9, 7, 6, 1, 4, 2, 3,
      4, 2, 6, 8, 5, 3, 7, 9, 1,
      7, 1, 3, 9, 2, 4, 8, 5, 6,
      9, 6, 1, 5, 3, 7, 2, 8, 4,
      2, 8, 7, 4, 1, 9, 6, 3, 5,
      3, 4, 5, 2, 8, 6, 1, 7, 9,
    ],
  },
];
