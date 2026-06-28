import {
  SIZE,
  CELLS,
  rowOf,
  colOf,
  boxOf,
  findConflicts,
  generatePuzzle,
  isComplete,
  cloneBoard,
} from "./sudoku.js";

const boardEl = document.getElementById("board");
const statusEl = document.getElementById("status");
const difficultyEl = document.getElementById("difficulty");

const state = {
  puzzle: [],   // current values shown to the user
  solution: [], // the full solution
  given: [],    // boolean clue mask
  selected: -1,
  revealed: false,
};

const cells = [];

function buildGrid() {
  boardEl.innerHTML = "";
  cells.length = 0;
  for (let i = 0; i < CELLS; i++) {
    const cell = document.createElement("div");
    cell.className = "cell";
    cell.dataset.index = String(i);
    cell.dataset.row = String(rowOf(i));
    cell.dataset.col = String(colOf(i));
    cell.setAttribute("role", "gridcell");
    cell.tabIndex = -1;
    cell.addEventListener("click", () => select(i));
    boardEl.appendChild(cell);
    cells.push(cell);
  }
}

function setStatus(msg, kind = "") {
  statusEl.textContent = msg;
  statusEl.className = "status" + (kind ? " " + kind : "");
}

function newGame() {
  const difficulty = difficultyEl.value;
  const result = generatePuzzle(difficulty);
  state.puzzle = cloneBoard(result.puzzle);
  state.solution = result.solution;
  state.given = result.given;
  state.startPuzzle = cloneBoard(result.puzzle);
  state.revealed = false;
  state.selected = -1;
  setStatus(`New ${difficulty} puzzle. Good luck!`);
  render();
  select(state.given.findIndex((g) => !g));
}

function select(i) {
  if (i < 0 || i >= CELLS) return;
  state.selected = i;
  render();
  cells[i].focus();
}

function setValue(i, val) {
  if (i < 0 || state.given[i] || state.revealed) return;
  state.puzzle[i] = val;
  render();
  checkWin();
}

function checkWin() {
  if (isComplete(state.puzzle)) {
    setStatus("Solved! Well done.", "ok");
  }
}

function render() {
  const conflicts = findConflicts(state.puzzle);
  const sel = state.selected;
  const selRow = sel >= 0 ? rowOf(sel) : -1;
  const selCol = sel >= 0 ? colOf(sel) : -1;
  const selBox = sel >= 0 ? boxOf(sel) : -1;

  for (let i = 0; i < CELLS; i++) {
    const cell = cells[i];
    const v = state.puzzle[i];
    cell.textContent = v === 0 ? "" : String(v);

    const classes = ["cell"];
    if (state.given[i]) classes.push("given");
    if (i === sel) classes.push("selected");
    else if (
      sel >= 0 &&
      (rowOf(i) === selRow || colOf(i) === selCol || boxOf(i) === selBox)
    ) {
      classes.push("peer");
    }
    if (conflicts.has(i)) classes.push("conflict");
    cell.className = classes.join(" ");

    const label = `row ${rowOf(i) + 1} column ${colOf(i) + 1}, ${
      v === 0 ? "empty" : v
    }${state.given[i] ? ", given" : ""}`;
    cell.setAttribute("aria-label", label);
    cell.setAttribute("aria-selected", i === sel ? "true" : "false");
    cell.tabIndex = i === sel ? 0 : -1;
  }
}

function move(dr, dc) {
  if (state.selected < 0) {
    select(0);
    return;
  }
  const r = Math.min(SIZE - 1, Math.max(0, rowOf(state.selected) + dr));
  const c = Math.min(SIZE - 1, Math.max(0, colOf(state.selected) + dc));
  select(r * SIZE + c);
}

function onKeyDown(e) {
  switch (e.key) {
    case "ArrowUp": move(-1, 0); e.preventDefault(); break;
    case "ArrowDown": move(1, 0); e.preventDefault(); break;
    case "ArrowLeft": move(0, -1); e.preventDefault(); break;
    case "ArrowRight": move(0, 1); e.preventDefault(); break;
    case "Backspace":
    case "Delete":
    case "0":
      setValue(state.selected, 0);
      e.preventDefault();
      break;
    default:
      if (/^[1-9]$/.test(e.key)) {
        setValue(state.selected, Number(e.key));
        e.preventDefault();
      }
  }
}

function resetPuzzle() {
  if (!state.startPuzzle) return;
  state.puzzle = cloneBoard(state.startPuzzle);
  state.revealed = false;
  setStatus("Puzzle reset.");
  render();
}

function checkSolution() {
  const filled = state.puzzle.every((v) => v !== 0);
  const conflicts = findConflicts(state.puzzle);
  if (!filled) {
    setStatus(
      conflicts.size > 0
        ? `${conflicts.size} cell(s) conflict; board incomplete.`
        : "No conflicts so far, but the board is incomplete.",
      conflicts.size > 0 ? "err" : "",
    );
  } else if (conflicts.size === 0) {
    setStatus("Solved! Well done.", "ok");
  } else {
    setStatus(`${conflicts.size} conflicting cell(s).`, "err");
  }
}

function solvePuzzle() {
  state.puzzle = cloneBoard(state.solution);
  state.revealed = true;
  setStatus("Solution revealed.");
  render();
}

function init() {
  buildGrid();
  document.getElementById("new-game").addEventListener("click", newGame);
  document.getElementById("reset").addEventListener("click", resetPuzzle);
  document.getElementById("check").addEventListener("click", checkSolution);
  document.getElementById("solve").addEventListener("click", solvePuzzle);
  boardEl.addEventListener("keydown", onKeyDown);
  document.querySelectorAll(".pad button").forEach((btn) => {
    btn.addEventListener("click", () =>
      setValue(state.selected, Number(btn.dataset.digit)),
    );
  });
  newGame();
}

init();
