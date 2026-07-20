import { test } from "node:test";
import assert from "node:assert/strict";
import { SearchIndex } from "../src/SearchIndex.js";

interface Doc {
  id: string;
  title: string;
  body: string;
}

test("edge-cases: introspection — docs(), terms(), docFrequency()", () => {
  const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
  idx.add({ id: "1", title: "alpha beta", body: "gamma" });
  idx.add({ id: "2", title: "alpha", body: "delta" });

  const allDocs = [...idx.docs()];
  assert.equal(allDocs.length, 2);

  const allTerms = new Set(idx.terms());
  assert.ok(allTerms.has("alpha"));
  assert.ok(allTerms.has("beta"));
  assert.ok(allTerms.has("gamma"));

  assert.equal(idx.docFrequency("alpha"), 2);
  assert.equal(idx.docFrequency("beta"), 1);
  assert.equal(idx.docFrequency("nonexistentterm"), 0);
});

test("edge-cases: custom idField is respected", () => {
  interface CustomDoc {
    uuid: string;
    title: string;
    body: string;
  }
  const idx = new SearchIndex<CustomDoc>({
    fields: { title: { boost: 1 }, body: { boost: 1 } },
    idField: "uuid",
  });
  idx.add({ uuid: "abc-123", title: "hello", body: "world" });
  assert.equal(idx.has("abc-123"), true);
  const results = idx.search({ term: "hello" });
  assert.equal(results[0]?.id, "abc-123");
});

test("edge-cases: custom tokenizer is respected", () => {
  const idx = new SearchIndex<Doc>({
    fields: { title: { boost: 1 }, body: { boost: 1 } },
    tokenizer: (text) => text.split(/[,;]+/).map((s) => s.trim().toLowerCase()).filter(Boolean),
  });
  idx.add({ id: "1", title: "red,green;blue", body: "x" });
  // With a comma/semicolon tokenizer, "red" is a whole token.
  const results = idx.search({ term: "red" });
  assert.equal(results.length, 1);
});

test("edge-cases: custom stemmer is respected", () => {
  const idx = new SearchIndex<Doc>({
    fields: { title: { boost: 1 }, body: { boost: 1 } },
    stemmer: (tok) => (tok.endsWith("s") ? tok.slice(0, -1) : tok),
  });
  idx.add({ id: "1", title: "running dogs", body: "x" });
  const results = idx.search({ term: "dog" }); // stemmed query should match "dogs" -> "dog"
  assert.equal(results.length, 1);
});

test("edge-cases: stopwords 'none' keeps stopwords indexed", () => {
  const idx = new SearchIndex<Doc>({
    fields: { title: { boost: 1 }, body: { boost: 1 } },
    stopwords: "none",
  });
  idx.add({ id: "1", title: "the cat sat", body: "x" });
  const results = idx.search({ term: "the" });
  assert.equal(results.length, 1);
});

test("edge-cases: custom stopwords set", () => {
  const idx = new SearchIndex<Doc>({
    fields: { title: { boost: 1 }, body: { boost: 1 } },
    stopwords: new Set(["custom"]),
  });
  idx.add({ id: "1", title: "custom keyword", body: "x" });
  assert.equal(idx.search({ term: "custom" }).length, 0);
  assert.equal(idx.search({ term: "keyword" }).length, 1);
});

test("edge-cases: snippet on field that doesn't contain the match term", () => {
  const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
  idx.add({ id: "1", title: "matchhere", body: "irrelevant content" });
  assert.doesNotThrow(() => idx.search({ term: "matchhere" }, { snippet: { field: "body", length: 20 } }));
});

test("edge-cases: fuzzy query where edit distance equals word length is a boundary, not an off-by-one bug", () => {
  const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
  idx.add({ id: "1", title: "xyz", body: "x" });
  // "abc" vs "xyz": distance 3 (all substituted), word length 3.
  assert.equal(idx.search({ fuzzy: "abc", maxEdits: 2 }).length, 0);
});
