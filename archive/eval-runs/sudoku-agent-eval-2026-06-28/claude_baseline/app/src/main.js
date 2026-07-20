import {
  SIZE,
  CELLS,
  indexToRowCol,
  rowColToIndex,
  findConflicts,
  isComplete,
  generatePuzzle,
  cloneBoard,
} from './sudoku.js';

const boardEl = document.getElementById('board');
const statusEl = document.getElementById('status');
const difficultyEl = document.getElementById('difficulty');

const state = {
  puzzle: new Array(CELLS).fill(0), // the starting givens (0 = blank)
  solution: new Array(CELLS).fill(0), // the full solution
  current: new Array(CELLS).fill(0), // the player's working board
  selected: null, // selected cell index or null
};

const cells = [];

function buildGrid() {
  boardEl.innerHTML = '';
  cells.length = 0;
  for (let i = 0; i < CELLS; i++) {
    const [row, col] = indexToRowCol(i);
    const cell = document.createElement('button');
    cell.type = 'button';
    cell.className = 'cell';
    cell.dataset.index = String(i);
    cell.dataset.row = String(row);
    cell.dataset.col = String(col);
    cell.setAttribute('role', 'gridcell');
    cell.tabIndex = -1;
    cell.addEventListener('click', () => selectCell(i));
    boardEl.appendChild(cell);
    cells.push(cell);
  }
}

function setStatus(message, kind = '') {
  statusEl.textContent = message;
  statusEl.className = 'status' + (kind ? ` status--${kind}` : '');
}

function isGiven(index) {
  return state.puzzle[index] !== 0;
}

function arePeers(a, b) {
  const [ra, ca] = indexToRowCol(a);
  const [rb, cb] = indexToRowCol(b);
  if (ra === rb || ca === cb) return true;
  const sameBox =
    Math.floor(ra / 3) === Math.floor(rb / 3) && Math.floor(ca / 3) === Math.floor(cb / 3);
  return sameBox;
}

function render() {
  const conflicts = findConflicts(state.current);
  for (let i = 0; i < CELLS; i++) {
    const cell = cells[i];
    const value = state.current[i];
    cell.textContent = value === 0 ? '' : String(value);

    cell.classList.toggle('cell--given', isGiven(i));
    cell.classList.toggle('cell--conflict', conflicts.has(i));

    const selected = state.selected === i;
    cell.classList.toggle('cell--selected', selected);
    cell.classList.toggle(
      'cell--peer',
      state.selected !== null && !selected && arePeers(state.selected, i),
    );

    const [row, col] = indexToRowCol(i);
    const label = value === 0 ? 'empty' : `value ${value}`;
    cell.setAttribute(
      'aria-label',
      `Row ${row + 1}, column ${col + 1}, ${isGiven(i) ? 'given ' : ''}${label}`,
    );
    cell.setAttribute('aria-selected', selected ? 'true' : 'false');
    cell.tabIndex = selected ? 0 : -1;
  }
  if (state.selected === null && cells[0]) cells[0].tabIndex = 0;
}

function selectCell(index) {
  state.selected = index;
  render();
  cells[index].focus();
}

function setDigit(value) {
  const index = state.selected;
  if (index === null || isGiven(index)) return;
  state.current[index] = value;
  render();
  if (value !== 0 && isComplete(state.current)) {
    if (findConflicts(state.current).size === 0) {
      setStatus('Solved! Nicely done.', 'ok');
    } else {
      setStatus('Board is full but has conflicts.', 'error');
    }
  } else {
    setStatus('Select a cell and enter digits 1–9.');
  }
}

function newGame() {
  setStatus('Generating puzzle…');
  // Defer so the status paints before the (synchronous) generation runs.
  requestAnimationFrame(() => {
    const { puzzle, solution } = generatePuzzle(difficultyEl.value);
    state.puzzle = puzzle;
    state.solution = solution;
    state.current = cloneBoard(puzzle);
    state.selected = null;
    render();
    setStatus('New puzzle ready. Good luck!');
  });
}

function resetPuzzle() {
  state.current = cloneBoard(state.puzzle);
  render();
  setStatus('Puzzle reset to its starting position.');
}

function checkSolution() {
  const conflicts = findConflicts(state.current);
  if (conflicts.size > 0) {
    setStatus(`Found ${conflicts.size} cell(s) in conflict.`, 'error');
  } else if (!isComplete(state.current)) {
    setStatus('No conflicts so far — keep going!', 'ok');
  } else {
    setStatus('Solved! Every cell is correct.', 'ok');
  }
}

function revealSolution() {
  state.current = cloneBoard(state.solution);
  render();
  setStatus('Solution revealed.');
}

function moveSelection(dRow, dCol) {
  if (state.selected === null) {
    selectCell(0);
    return;
  }
  let [row, col] = indexToRowCol(state.selected);
  row = (row + dRow + SIZE) % SIZE;
  col = (col + dCol + SIZE) % SIZE;
  selectCell(rowColToIndex(row, col));
}

function onKeyDown(event) {
  const key = event.key;
  if (key >= '1' && key <= '9') {
    setDigit(Number(key));
    event.preventDefault();
  } else if (key === '0' || key === 'Backspace' || key === 'Delete') {
    setDigit(0);
    event.preventDefault();
  } else if (key === 'ArrowUp') {
    moveSelection(-1, 0);
    event.preventDefault();
  } else if (key === 'ArrowDown') {
    moveSelection(1, 0);
    event.preventDefault();
  } else if (key === 'ArrowLeft') {
    moveSelection(0, -1);
    event.preventDefault();
  } else if (key === 'ArrowRight') {
    moveSelection(0, 1);
    event.preventDefault();
  }
}

function wireControls() {
  document.getElementById('new-game').addEventListener('click', newGame);
  document.getElementById('check').addEventListener('click', checkSolution);
  document.getElementById('reset').addEventListener('click', resetPuzzle);
  document.getElementById('solve').addEventListener('click', revealSolution);
  document.querySelectorAll('.pad__btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      setDigit(Number(btn.dataset.digit));
      if (state.selected !== null) cells[state.selected].focus();
    });
  });
  boardEl.addEventListener('keydown', onKeyDown);
}

buildGrid();
wireControls();
newGame();
