import { test } from "node:test";
import assert from "node:assert/strict";
import { defaultTokenizer } from "../src/tokenizer.js";

test("tokenizer: splits ASCII words and lowercases", () => {
  assert.deepEqual(defaultTokenizer("Hello World"), ["hello", "world"]);
});

test("tokenizer: handles unicode letters (café, naïve, 搜索, بحث)", () => {
  assert.deepEqual(defaultTokenizer("café"), ["café"]);
  assert.deepEqual(defaultTokenizer("naïve"), ["naïve"]);
  assert.deepEqual(defaultTokenizer("搜索"), ["搜索"]);
  assert.deepEqual(defaultTokenizer("بحث"), ["بحث"]);
});

test("tokenizer: numbers are included as tokens", () => {
  assert.deepEqual(defaultTokenizer("item42 costs 100"), ["item42", "costs", "100"]);
});

test("tokenizer: empty and whitespace-only strings yield no tokens", () => {
  assert.deepEqual(defaultTokenizer(""), []);
  assert.deepEqual(defaultTokenizer("   \t\n  "), []);
});

test("tokenizer: combining character sequences normalize like precomposed", () => {
  const precomposed = "caf\u00e9"; // café with precomposed é
  const combining = "cafe\u0301"; // café with e + combining acute
  assert.deepEqual(defaultTokenizer(precomposed), defaultTokenizer(combining));
});
