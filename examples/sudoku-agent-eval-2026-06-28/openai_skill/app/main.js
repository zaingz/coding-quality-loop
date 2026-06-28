import {
  SIZE,
  CELLS,
  rowOf,
  colOf,
  boxOf,
  indexOf,
  generatePuzzle,
  solve,
  findConflicts,
  isComplete,
  isSolved,
} from './sudoku.js';

const boardEl = document.getElementById('board');
const statusEl = document.getElementById('status');
const difficultyEl = document.getElementById('difficulty');

const state = {
  puzzle: [], // starting givens (0 = empty)
  solution: [], // the unique solution
  givens: [], // boolean[] locked cells
  board: [], // current player board
  selected: null, // selected cell index or null
  cells: [], // cell DOM nodes by index
};

function setStatus(message, kind = '') {
  statusEl.textContent = message;
  statusEl.className = `status${kind ? ` ${kind}` : ''}`;
}

function buildGrid() {
  boardEl.replaceChildren();
  state.cells = [];
  for (let index = 0; index < CELLS; index++) {
    const cell = document.createElement('button');
    cell.type = 'button';
    cell.className = 'cell';
    cell.dataset.index = String(index);
    cell.dataset.row = String(rowOf(index));
    cell.dataset.col = String(colOf(index));
    cell.setAttribute('role', 'gridcell');
    cell.addEventListener('click', () => selectCell(index));
    boardEl.appendChild(cell);
    state.cells.push(cell);
  }
}

function startGame() {
  const difficulty = difficultyEl.value;
  const seed = Math.floor(Math.random() * 0xffffffff);
  const { puzzle, solution, givens } = generatePuzzle(seed, difficulty);
  state.puzzle = puzzle;
  state.solution = solution;
  state.givens = givens;
  state.board = puzzle.slice();
  state.selected = null;
  render();
  setStatus('New puzzle ready. Good luck!');
}

function selectCell(index) {
  state.selected = index;
  render();
  state.cells[index].focus();
}

function inputDigit(value) {
  const index = state.selected;
  if (index === null || state.givens[index]) return;
  state.board[index] = value;
  render();
  evaluateProgress();
}

function clearCell() {
  const index = state.selected;
  if (index === null || state.givens[index]) return;
  state.board[index] = 0;
  render();
}

function resetPuzzle() {
  state.board = state.puzzle.slice();
  render();
  setStatus('Puzzle reset to the starting position.');
}

function revealSolution() {
  state.board = state.solution.slice();
  render();
  setStatus('Solved puzzle revealed.', 'ok');
}

function checkSolution() {
  const conflicts = findConflicts(state.board);
  if (!isComplete(state.board)) {
    setStatus(
      conflicts.size > 0
        ? 'Not done yet — and there are conflicting cells (highlighted).'
        : 'Looking good so far. Keep filling in cells.',
      conflicts.size > 0 ? 'error' : '',
    );
    return;
  }
  if (isSolved(state.board, state.solution)) {
    setStatus('Solved! Every cell is correct.', 'ok');
  } else {
    setStatus('All filled, but something is incorrect.', 'error');
  }
}

function evaluateProgress() {
  if (isComplete(state.board) && findConflicts(state.board).size === 0) {
    if (isSolved(state.board, state.solution)) {
      setStatus('Solved! Every cell is correct.', 'ok');
    }
  }
}

function render() {
  const conflicts = findConflicts(state.board);
  const selected = state.selected;
  const selRow = selected === null ? -1 : rowOf(selected);
  const selCol = selected === null ? -1 : colOf(selected);
  const selBox = selected === null ? -1 : boxOf(selected);

  for (let index = 0; index < CELLS; index++) {
    const cell = state.cells[index];
    const value = state.board[index];
    cell.textContent = value === 0 ? '' : String(value);

    const isGiven = state.givens[index];
    const isPeer =
      selected !== null &&
      index !== selected &&
      (rowOf(index) === selRow || colOf(index) === selCol || boxOf(index) === selBox);

    cell.classList.toggle('given', isGiven);
    cell.classList.toggle('selected', index === selected);
    cell.classList.toggle('peer', isPeer);
    cell.classList.toggle('conflict', conflicts.has(index));

    const label = `Row ${rowOf(index) + 1}, column ${colOf(index) + 1}, ${
      value === 0 ? 'empty' : `value ${value}`
    }${isGiven ? ', given' : ''}`;
    cell.setAttribute('aria-label', label);
    cell.setAttribute('aria-readonly', isGiven ? 'true' : 'false');
    cell.tabIndex = index === (selected ?? 0) ? 0 : -1;
  }
}

function moveSelection(dRow, dCol) {
  const current = state.selected ?? 0;
  const row = Math.min(SIZE - 1, Math.max(0, rowOf(current) + dRow));
  const col = Math.min(SIZE - 1, Math.max(0, colOf(current) + dCol));
  selectCell(indexOf(row, col));
}

function onKeyDown(event) {
  const key = event.key;
  if (key >= '1' && key <= '9') {
    inputDigit(Number(key));
    event.preventDefault();
    return;
  }
  if (key === 'Backspace' || key === 'Delete' || key === '0') {
    clearCell();
    event.preventDefault();
    return;
  }
  const moves = {
    ArrowUp: [-1, 0],
    ArrowDown: [1, 0],
    ArrowLeft: [0, -1],
    ArrowRight: [0, 1],
  };
  if (moves[key]) {
    moveSelection(moves[key][0], moves[key][1]);
    event.preventDefault();
  }
}

function init() {
  buildGrid();
  document.getElementById('new-game').addEventListener('click', startGame);
  document.getElementById('check').addEventListener('click', checkSolution);
  document.getElementById('reveal').addEventListener('click', revealSolution);
  document.getElementById('reset').addEventListener('click', resetPuzzle);
  document.getElementById('clear').addEventListener('click', clearCell);
  for (const key of document.querySelectorAll('.keypad__key')) {
    key.addEventListener('click', () => inputDigit(Number(key.dataset.digit)));
  }
  boardEl.addEventListener('keydown', onKeyDown);
  startGame();
}

init();
