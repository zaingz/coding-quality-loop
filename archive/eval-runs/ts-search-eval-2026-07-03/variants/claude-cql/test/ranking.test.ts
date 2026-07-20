import { test } from "node:test";
import assert from "node:assert/strict";
import { SearchIndex } from "../src/SearchIndex.js";

interface Doc {
  id: string;
  title: string;
  body: string;
}

test("ranking: BM25 sanity — title match ranks higher than body match when title boosted", () => {
  const idx = new SearchIndex<Doc>({ fields: { title: { boost: 3 }, body: { boost: 1 } } });
  idx.add({ id: "titleDoc", title: "unicorn special term", body: "generic filler content here" });
  idx.add({ id: "bodyDoc", title: "generic filler content", body: "unicorn special term appears here" });

  const results = idx.search({ term: "unicorn" });
  assert.equal(results.length, 2);
  assert.equal(results[0]?.id, "titleDoc");
});

test("ranking: results sorted by score desc, then id asc for ties", () => {
  const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
  idx.add({ id: "b", title: "same words here", body: "x" });
  idx.add({ id: "a", title: "same words here", body: "x" });
  idx.add({ id: "c", title: "same words here", body: "x" });
  const results = idx.search({ term: "same" });
  const ids = results.map((r) => r.id);
  assert.deepEqual(ids, ["a", "b", "c"]);
});

test("ranking: phrase query — exact adjacency matches, non-adjacent does not (slop 0)", () => {
  const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
  idx.add({ id: "1", title: "t", body: "the quick brown fox jumps" });
  idx.add({ id: "2", title: "t", body: "the quick red brown fox jumps" });
  const results = idx.search({ phrase: "quick brown" });
  const ids = results.map((r) => r.id);
  assert.deepEqual(ids, ["1"]);
});

test("ranking: phrase proximity — closer term positions rank higher", () => {
  const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
  // doc "close": alpha beta adjacent-ish with slop; doc "far": bigger gap.
  idx.add({ id: "close", title: "t", body: "alpha beta gamma delta epsilon" });
  idx.add({ id: "far", title: "t", body: "alpha zeta eta theta iota kappa lambda mu nu beta" });
  const results = idx.search({ phrase: "alpha beta", slop: 10 });
  const ids = results.map((r) => r.id);
  assert.equal(ids[0], "close");
});

test("ranking: search options — limit and offset paginate results", () => {
  const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
  for (let i = 0; i < 5; i++) {
    idx.add({ id: `d${i}`, title: "shared", body: "shared" });
  }
  const page1 = idx.search({ term: "shared" }, { limit: 2, offset: 0 });
  const page2 = idx.search({ term: "shared" }, { limit: 2, offset: 2 });
  assert.equal(page1.length, 2);
  assert.equal(page2.length, 2);
  assert.notDeepEqual(page1.map((r) => r.id), page2.map((r) => r.id));
});

test("ranking: filter post-filters after ranking", () => {
  const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
  idx.add({ id: "1", title: "keep", body: "match" });
  idx.add({ id: "2", title: "drop", body: "match" });
  const results = idx.search({ term: "match" }, { filter: (doc) => doc.title === "keep" });
  assert.deepEqual(results.map((r) => r.id), ["1"]);
});

test("ranking: boostFields override changes ranking order", () => {
  const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
  idx.add({ id: "titleHeavy", title: "keyword keyword keyword", body: "other" });
  idx.add({ id: "bodyHeavy", title: "other", body: "keyword keyword keyword" });
  const normal = idx.search({ term: "keyword" });
  const boosted = idx.search({ term: "keyword" }, { boostFields: { body: 10 } });
  assert.equal(boosted[0]?.id, "bodyHeavy");
  assert.ok(normal.length === 2 && boosted.length === 2);
});

test("ranking: determinism — same query twice yields identical results", () => {
  const idx = new SearchIndex<Doc>({ fields: { title: { boost: 2 }, body: { boost: 1 } } });
  idx.add({ id: "1", title: "determinism test alpha", body: "beta gamma" });
  idx.add({ id: "2", title: "determinism test beta", body: "alpha gamma" });
  const first = idx.search({ term: "determinism" });
  const second = idx.search({ term: "determinism" });
  assert.deepEqual(first, second);
});

test("ranking: fuzzy query with edit distance equal to word length", () => {
  const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
  idx.add({ id: "1", title: "ab", body: "text" });
  // "cd" vs "ab": edit distance 2, equal to word length 2, maxEdits 2 should match.
  const results = idx.search({ fuzzy: "cd", maxEdits: 2 });
  assert.deepEqual(results.map((r) => r.id), ["1"]);
  // maxEdits 1 should not match (distance is 2 > 1).
  const noMatch = idx.search({ fuzzy: "cd", maxEdits: 1 });
  assert.deepEqual(noMatch, []);
});

test("ranking: empty index search returns empty array", () => {
  const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
  assert.deepEqual(idx.search({ term: "anything" }), []);
  assert.deepEqual(idx.search("anything"), []);
});

test("ranking: extremely long document (100 KB body) indexes and is searchable", () => {
  const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
  const word = "lorem ";
  const longBody = word.repeat(20000) + "uniquemarker"; // > 100KB
  assert.ok(longBody.length > 100_000);
  idx.add({ id: "big", title: "t", body: longBody });
  const results = idx.search({ term: "uniquemarker" });
  assert.deepEqual(results.map((r) => r.id), ["big"]);
});
