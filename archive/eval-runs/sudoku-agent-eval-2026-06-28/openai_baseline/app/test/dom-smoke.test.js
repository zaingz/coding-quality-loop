// Smoke test for the UI controller using a minimal hand-rolled DOM stub.
// No real browser or jsdom needed; it verifies app.js wires up without errors,
// builds 81 cells, generates a puzzle with locked givens, and accepts input.
import { test } from 'node:test';
import assert from 'node:assert/strict';

class FakeClassList {
  constructor() {
    this.set = new Set();
  }
  add(...c) {
    c.forEach((x) => this.set.add(x));
  }
  contains(c) {
    return this.set.has(c);
  }
}

class FakeElement {
  constructor(tag) {
    this.tagName = tag;
    this.children = [];
    this.dataset = {};
    this.attributes = {};
    this.listeners = {};
    this.classList = new FakeClassList();
    this._className = '';
    this.textContent = '';
    this.value = '';
    this.style = {};
  }
  set className(v) {
    this._className = v;
    this.classList = new FakeClassList();
    v.split(/\s+/).filter(Boolean).forEach((c) => this.classList.add(c));
  }
  get className() {
    return this._className;
  }
  appendChild(child) {
    this.children.push(child);
    return child;
  }
  set innerHTML(_) {
    this.children = [];
  }
  setAttribute(k, v) {
    this.attributes[k] = String(v);
  }
  getAttribute(k) {
    return this.attributes[k] ?? null;
  }
  addEventListener(type, fn) {
    (this.listeners[type] ||= []).push(fn);
  }
  dispatch(type, event = {}) {
    (this.listeners[type] || []).forEach((fn) => fn(event));
  }
  focus() {
    this.focused = true;
  }
  querySelectorAll() {
    return [];
  }
}

function buildDocument() {
  const byId = {
    board: new FakeElement('div'),
    status: new FakeElement('p'),
    difficulty: new FakeElement('select'),
    'new-game': new FakeElement('button'),
    reset: new FakeElement('button'),
    check: new FakeElement('button'),
    solve: new FakeElement('button'),
  };
  byId.difficulty.value = 'easy';

  return {
    getElementById: (id) => byId[id],
    createElement: (tag) => new FakeElement(tag),
    querySelectorAll: () => [],
    _byId: byId,
  };
}

test('app.js builds the board and starts a playable game', async () => {
  const doc = buildDocument();
  global.document = doc;

  await import('../src/app.js');

  const board = doc._byId.board;
  assert.equal(board.children.length, 81, 'renders 81 cells');

  const givenCount = board.children.filter((c) =>
    c.classList.contains('cell--given')
  ).length;
  assert.ok(givenCount > 0 && givenCount < 81, 'has locked givens but not all');

  // Status line should report the new puzzle.
  assert.match(doc._byId.status.textContent, /puzzle/i);

  // Find an empty (non-given) cell, click it, and type a digit.
  const emptyCell = board.children.find(
    (c) => !c.classList.contains('cell--given')
  );
  emptyCell.dispatch('click');
  board.dispatch('keydown', { key: '5', preventDefault() {} });
  assert.equal(emptyCell.textContent, '5', 'typed digit appears in the cell');

  // Backspace clears it.
  board.dispatch('keydown', { key: 'Backspace', preventDefault() {} });
  assert.equal(emptyCell.textContent, '', 'cleared after backspace');

  delete global.document;
});
