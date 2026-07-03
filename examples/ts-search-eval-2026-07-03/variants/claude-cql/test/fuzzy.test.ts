import { test } from "node:test";
import assert from "node:assert/strict";
import { SearchIndex } from "../src/SearchIndex.js";
import { levenshteinDistance } from "../src/levenshtein.js";

interface Doc {
  id: string;
  title: string;
  body: string;
}

test("fuzzy: levenshteinDistance basic cases", () => {
  assert.equal(levenshteinDistance("", ""), 0);
  assert.equal(levenshteinDistance("abc", "abc"), 0);
  assert.equal(levenshteinDistance("", "abc"), 3);
  assert.equal(levenshteinDistance("kitten", "sitting"), 3);
  assert.equal(levenshteinDistance("colour", "color"), 1);
});

test("fuzzy: 'colour' query with maxEdits 1 matches indexed 'color'", () => {
  const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
  idx.add({ id: "1", title: "color", body: "the color of the sky" });
  const results = idx.search({ fuzzy: "colour", field: "title", maxEdits: 1 });
  assert.deepEqual(results.map((r) => r.id), ["1"]);
});

test("fuzzy: query via boolean string form", () => {
  const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
  idx.add({ id: "1", title: "color", body: "x" });
  idx.add({ id: "2", title: "unrelated", body: "y" });
  const results = idx.search({ fuzzy: "colour", maxEdits: 1 });
  assert.deepEqual(results.map((r) => r.id), ["1"]);
});

test("fuzzy: distance beyond maxEdits does not match", () => {
  const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
  idx.add({ id: "1", title: "completely different word", body: "x" });
  const results = idx.search({ fuzzy: "colour", maxEdits: 2 });
  assert.deepEqual(results, []);
});
