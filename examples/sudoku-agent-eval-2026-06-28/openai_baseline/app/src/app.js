import {
  SIZE,
  EMPTY,
  rowColToIndex,
  indexToRowCol,
  cloneBoard,
  findConflicts,
  isSolved,
  isComplete,
  generatePuzzle,
  solve,
} from './sudoku.js';

const boardEl = document.getElementById('board');
const statusEl = document.getElementById('status');
const difficultyEl = document.getElementById('difficulty');

const state = {
  puzzle: [], // the original givens (immutable per game)
  current: [], // the player's working board
  solution: [], // the full solution for the current puzzle
  selected: null, // selected flat index, or null
  cells: [], // cached cell DOM elements by index
};

function buildGrid() {
  boardEl.innerHTML = '';
  state.cells = [];
  for (let index = 0; index < SIZE * SIZE; index++) {
    const { row, col } = indexToRowCol(index);
    const cell = document.createElement('button');
    cell.type = 'button';
    cell.className = 'cell';
    cell.dataset.index = String(index);
    cell.dataset.row = String(row);
    cell.dataset.col = String(col);
    cell.setAttribute('role', 'gridcell');
    cell.setAttribute('tabindex', index === 0 ? '0' : '-1');
    cell.addEventListener('click', () => selectCell(index));
    boardEl.appendChild(cell);
    state.cells[index] = cell;
  }
}

function isGiven(index) {
  return state.puzzle[index] !== EMPTY;
}

function selectCell(index) {
  state.selected = index;
  state.cells[index].focus();
  render();
}

function setStatus(message, kind = '') {
  statusEl.textContent = message;
  statusEl.className = 'status' + (kind ? ` status--${kind}` : '');
}

function newGame() {
  const difficulty = difficultyEl.value;
  const { puzzle, solution } = generatePuzzle(difficulty);
  state.puzzle = puzzle;
  state.current = cloneBoard(puzzle);
  state.solution = solution;
  state.selected = firstEmptyIndex();
  setStatus('New puzzle ready. Good luck!');
  render();
}

function firstEmptyIndex() {
  const idx = state.puzzle.indexOf(EMPTY);
  return idx === -1 ? 0 : idx;
}

function resetGame() {
  state.current = cloneBoard(state.puzzle);
  state.selected = firstEmptyIndex();
  setStatus('Board reset to its starting clues.');
  render();
}

function setValue(value) {
  const index = state.selected;
  if (index === null || isGiven(index)) return;
  state.current[index] = value;
  setStatus('');
  render();
}

function checkSolution() {
  const conflicts = findConflicts(state.current);
  if (conflicts.size > 0) {
    setStatus('There are conflicting entries. Check the highlighted cells.', 'error');
  } else if (!isComplete(state.current)) {
    setStatus('No conflicts so far. Keep going!', 'success');
  } else if (isSolved(state.current)) {
    setStatus('Solved! Well done.', 'success');
  }
  render();
}

function revealSolution() {
  const solved = state.solution.length ? state.solution : solve(state.current);
  if (!solved) {
    setStatus('This board cannot be solved.', 'error');
    return;
  }
  state.current = cloneBoard(solved);
  setStatus('Solution revealed.', 'success');
  render();
}

function moveSelection(dRow, dCol) {
  if (state.selected === null) {
    selectCell(firstEmptyIndex());
    return;
  }
  const { row, col } = indexToRowCol(state.selected);
  const nextRow = (row + dRow + SIZE) % SIZE;
  const nextCol = (col + dCol + SIZE) % SIZE;
  selectCell(rowColToIndex(nextRow, nextCol));
}

function render() {
  const conflicts = findConflicts(state.current);
  const selected = state.selected;
  const selectedValue = selected !== null ? state.current[selected] : EMPTY;
  let selRow = -1;
  let selCol = -1;
  if (selected !== null) {
    ({ row: selRow, col: selCol } = indexToRowCol(selected));
  }

  for (let index = 0; index < SIZE * SIZE; index++) {
    const cell = state.cells[index];
    const value = state.current[index];
    const { row, col } = indexToRowCol(index);
    cell.textContent = value === EMPTY ? '' : String(value);

    const classes = ['cell'];
    if (isGiven(index)) classes.push('cell--given');

    if (selected !== null && index !== selected) {
      const sameBox =
        Math.floor(row / 3) === Math.floor(selRow / 3) &&
        Math.floor(col / 3) === Math.floor(selCol / 3);
      if (row === selRow || col === selCol || sameBox) classes.push('cell--peer');
      if (value !== EMPTY && value === selectedValue) classes.push('cell--same');
    }

    if (conflicts.has(index)) classes.push('cell--error');
    if (index === selected) classes.push('cell--selected');

    cell.className = classes.join(' ');

    const label = `Row ${row + 1}, column ${col + 1}, ${
      value === EMPTY ? 'empty' : value
    }${isGiven(index) ? ', given' : ''}`;
    cell.setAttribute('aria-label', label);
    cell.setAttribute('aria-selected', index === selected ? 'true' : 'false');
    cell.setAttribute('tabindex', index === selected ? '0' : '-1');
  }
}

function handleKeydown(event) {
  switch (event.key) {
    case 'ArrowUp':
      event.preventDefault();
      moveSelection(-1, 0);
      break;
    case 'ArrowDown':
      event.preventDefault();
      moveSelection(1, 0);
      break;
    case 'ArrowLeft':
      event.preventDefault();
      moveSelection(0, -1);
      break;
    case 'ArrowRight':
      event.preventDefault();
      moveSelection(0, 1);
      break;
    case 'Backspace':
    case 'Delete':
    case '0':
      event.preventDefault();
      setValue(EMPTY);
      break;
    default:
      if (/^[1-9]$/.test(event.key)) {
        event.preventDefault();
        setValue(Number(event.key));
      }
  }
}

function wireControls() {
  document.getElementById('new-game').addEventListener('click', newGame);
  document.getElementById('reset').addEventListener('click', resetGame);
  document.getElementById('check').addEventListener('click', checkSolution);
  document.getElementById('solve').addEventListener('click', revealSolution);
  difficultyEl.addEventListener('change', newGame);

  document.querySelectorAll('.keypad button').forEach((btn) => {
    btn.addEventListener('click', () => {
      const digit = Number(btn.dataset.digit);
      setValue(digit);
      if (state.selected !== null) state.cells[state.selected].focus();
    });
  });

  boardEl.addEventListener('keydown', handleKeydown);
}

buildGrid();
wireControls();
newGame();
