import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { SearchIndex } from "../src/index.js";

interface Doc {
  id: string;
  title: string;
  body: string;
}

function makeIndex(): SearchIndex<Doc> {
  const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
  idx.add({ id: "1", title: "quick brown fox", body: "" });
  idx.add({ id: "2", title: "quick red brown fox", body: "" });
  idx.add({ id: "3", title: "lazy dog", body: "" });
  idx.add({ id: "4", title: "a b c", body: "" });
  return idx;
}

describe("Phrase queries", () => {
  test("exact adjacent phrase matches", () => {
    const idx = makeIndex();
    const results = idx.search({ phrase: "quick brown" });
    const ids = results.map((r) => r.id);
    assert.ok(ids.includes("1"));
  });

  test("phrase with intervening word does not match at slop 0", () => {
    const idx = makeIndex();
    const results = idx.search({ phrase: "quick brown" });
    const ids = results.map((r) => r.id);
    assert.ok(!ids.includes("2"));
  });

  test("phrase with slop matches when terms are close but not adjacent", () => {
    const idx = makeIndex();
    const results = idx.search({ phrase: "quick brown", slop: 1 });
    const ids = results.map((r) => r.id);
    assert.ok(ids.includes("2"));
  });

  test("string query with quoted phrase", () => {
    const idx = makeIndex();
    const results = idx.search('"quick brown"');
    const ids = results.map((r) => r.id);
    assert.ok(ids.includes("1"));
    assert.ok(!ids.includes("2"));
  });
});

describe("Boolean query parsing", () => {
  test("AND requires both terms", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    idx.add({ id: "1", title: "apple banana", body: "" });
    idx.add({ id: "2", title: "apple", body: "" });
    idx.add({ id: "3", title: "banana", body: "" });
    const results = idx.search("apple AND banana");
    const ids = results.map((r) => r.id).sort();
    assert.deepEqual(ids, ["1"]);
  });

  test("OR matches either term", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    idx.add({ id: "1", title: "apple", body: "" });
    idx.add({ id: "2", title: "banana", body: "" });
    idx.add({ id: "3", title: "cherry", body: "" });
    const results = idx.search("apple OR banana");
    const ids = results.map((r) => r.id).sort();
    assert.deepEqual(ids, ["1", "2"]);
  });

  test("default operator between bare terms is OR", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    idx.add({ id: "1", title: "apple", body: "" });
    idx.add({ id: "2", title: "banana", body: "" });
    const results = idx.search("apple banana");
    const ids = results.map((r) => r.id).sort();
    assert.deepEqual(ids, ["1", "2"]);
  });

  test("a AND b NOT c returns docs with both a,b and without c", () => {
    const idx = new SearchIndex<Doc>({
      fields: { title: { boost: 1 }, body: { boost: 1 } },
      stopwords: "none",
    });
    idx.add({ id: "1", title: "a b", body: "" });
    idx.add({ id: "2", title: "a b c", body: "" });
    idx.add({ id: "3", title: "a", body: "" });
    const results = idx.search("a AND b NOT c");
    const ids = results.map((r) => r.id).sort();
    assert.deepEqual(ids, ["1"]);
  });

  test("field prefix query title:foo restricts to that field", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    idx.add({ id: "1", title: "special", body: "other" });
    idx.add({ id: "2", title: "other", body: "special" });
    const results = idx.search("title:special");
    const ids = results.map((r) => r.id);
    assert.deepEqual(ids, ["1"]);
  });

  test("deeply nested AND/OR/NOT with parens", () => {
    const idx = new SearchIndex<Doc>({
      fields: { title: { boost: 1 }, body: { boost: 1 } },
      stopwords: "none",
    });
    idx.add({ id: "1", title: "a b", body: "" }); // matches (a AND b)
    idx.add({ id: "2", title: "c", body: "" }); // matches (c) but excluded by NOT d? no d present, matches
    idx.add({ id: "3", title: "c d", body: "" }); // has d, excluded
    idx.add({ id: "4", title: "z", body: "" }); // matches neither
    const results = idx.search("(a AND b) OR (c NOT d)");
    const ids = results.map((r) => r.id).sort();
    assert.deepEqual(ids, ["1", "2"]);
  });

  test("structured and/or/not queries", () => {
    const idx = new SearchIndex<Doc>({
      fields: { title: { boost: 1 }, body: { boost: 1 } },
      stopwords: "none",
    });
    idx.add({ id: "1", title: "a b", body: "" });
    idx.add({ id: "2", title: "a", body: "" });
    const results = idx.search({ and: [{ term: "a" }, { term: "b" }] });
    assert.deepEqual(
      results.map((r) => r.id),
      ["1"]
    );

    const orResults = idx.search({ or: [{ term: "a" }, { term: "b" }] });
    assert.deepEqual(
      orResults.map((r) => r.id).sort(),
      ["1", "2"]
    );

    const notResults = idx.search({ not: { term: "b" } });
    assert.deepEqual(
      notResults.map((r) => r.id).sort(),
      ["2"]
    );
  });
});

describe("Fuzzy queries", () => {
  test("colour matches color with maxEdits 1", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    idx.add({ id: "1", title: "color", body: "" });
    idx.add({ id: "2", title: "unrelated", body: "" });
    const results = idx.search({ fuzzy: "colour", maxEdits: 1 });
    const ids = results.map((r) => r.id);
    assert.ok(ids.includes("1"));
    assert.ok(!ids.includes("2"));
  });

  test("fuzzy query with edit distance equal to word length matches only within maxEdits 2", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    idx.add({ id: "1", title: "ab", body: "" });
    // "cd" is edit distance 2 from "ab" (both chars differ), word length 2
    const results1 = idx.search({ fuzzy: "cd", maxEdits: 1 });
    assert.equal(results1.some((r) => r.id === "1"), false);
    const results2 = idx.search({ fuzzy: "cd", maxEdits: 2 });
    assert.equal(results2.some((r) => r.id === "1"), true);
  });
});

describe("Prefix queries", () => {
  test("prefix matches terms starting with given prefix", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    idx.add({ id: "1", title: "running runner runs", body: "" });
    idx.add({ id: "2", title: "walking", body: "" });
    const results = idx.search({ prefix: "run" });
    const ids = results.map((r) => r.id);
    assert.deepEqual(ids, ["1"]);
  });
});

describe("Unicode handling", () => {
  test("café is found by query café and CAFÉ (case-insensitive)", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    idx.add({ id: "1", title: "café culture", body: "" });
    const r1 = idx.search("café");
    const r2 = idx.search("CAFÉ");
    assert.equal(r1.length, 1);
    assert.equal(r2.length, 1);
  });

  test("handles CJK and Arabic scripts", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    idx.add({ id: "1", title: "搜索 引擎", body: "" });
    idx.add({ id: "2", title: "بحث في الويب", body: "" });
    const r1 = idx.search("搜索");
    const r2 = idx.search("بحث");
    assert.equal(r1.length, 1);
    assert.equal(r2.length, 1);
  });

  test("unicode combining characters are handled", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    // "é" via combining mark (e + U+0301) vs precomposed é (U+00E9)
    const combining = "cafe\u0301";
    const precomposed = "caf\u00e9";
    idx.add({ id: "1", title: combining, body: "" });
    const results = idx.search(precomposed);
    assert.equal(results.length, 1);
  });

  test("naïve is tokenized and searchable", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    idx.add({ id: "1", title: "a naïve approach", body: "" });
    const results = idx.search("naïve");
    assert.equal(results.length, 1);
  });
});
