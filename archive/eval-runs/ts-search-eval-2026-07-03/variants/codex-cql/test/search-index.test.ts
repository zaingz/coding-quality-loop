import assert from "node:assert/strict";
import test from "node:test";
import { SearchIndex, type SearchDocument } from "../src/index.js";

type Doc = SearchDocument & { id: string; title?: string; body?: string | undefined; tags?: string[]; year?: number };

function makeIndex(): SearchIndex<Doc> {
  return new SearchIndex<Doc>({ fields: { title: { boost: 3 }, body: { boost: 1 }, tags: { boost: 2 }, year: { boost: 1 } } });
}

test("BM25 ranking respects field boosts and stable id ties", () => {
  const index = makeIndex();
  index.addAll([
    { id: "b", title: "other", body: "alpha" },
    { id: "a", title: "alpha", body: "other" },
    { id: "c", title: "other", body: "alpha" }
  ]);
  const results = index.search("alpha", { limit: 10 });
  assert.equal(results[0]?.id, "a");
  assert.deepEqual(results.slice(1).map((row) => row.id), ["b", "c"]);
});

test("phrase query exactness and slop proximity", () => {
  const index = makeIndex();
  index.addAll([
    { id: "1", title: "", body: "quick brown fox" },
    { id: "2", title: "", body: "quick red brown fox" }
  ]);
  assert.deepEqual(index.search('"quick brown"', { limit: 10 }).map((row) => row.id), ["1"]);
  const slopResults = index.search({ phrase: "quick brown", slop: 1 }, { limit: 10 });
  assert.deepEqual(slopResults.map((row) => row.id), ["1", "2"]);
  assert.ok((slopResults[0]?.score ?? 0) > (slopResults[1]?.score ?? 0));
});

test("fuzzy query matches edit distance one and handles large relative edits", () => {
  const index = makeIndex();
  index.addAll([{ id: "1", title: "color", body: "" }, { id: "2", title: "shape", body: "" }]);
  assert.deepEqual(index.search({ fuzzy: "colour", maxEdits: 1 }, { limit: 10 }).map((row) => row.id), ["1"]);
  assert.deepEqual(index.search({ fuzzy: "x", maxEdits: 1 }, { limit: 10 }).map((row) => row.id), []);
});

test("boolean parser handles AND, implicit NOT, default OR, and field prefixes", () => {
  const index = makeIndex();
  index.addAll([
    { id: "1", title: "alpha", body: "a b" },
    { id: "2", title: "beta", body: "a b c" },
    { id: "3", title: "alpha", body: "a" },
    { id: "4", title: "gamma", body: "b" }
  ]);
  assert.deepEqual(index.search("a AND b NOT c", { limit: 10 }).map((row) => row.id), ["1"]);
  assert.deepEqual(index.search("title:alpha", { limit: 10 }).map((row) => row.id), ["1", "3"]);
  assert.deepEqual(index.search("alpha gamma", { limit: 10 }).map((row) => row.id).sort(), ["1", "3", "4"]);
});

test("structured nested boolean queries work", () => {
  const index = makeIndex();
  index.addAll([
    { id: "1", title: "red blue", body: "plain" },
    { id: "2", title: "red", body: "green" },
    { id: "3", title: "blue", body: "green" }
  ]);
  const results = index.search({ and: [{ or: [{ term: "red" }, { term: "blue" }] }, { not: { term: "plain" } }] }, { limit: 10 });
  assert.deepEqual(results.map((row) => row.id), ["2", "3"]);
});

test("unicode tokenizer is case-insensitive and normalizes combining marks", () => {
  const index = makeIndex();
  index.addAll([
    { id: "1", title: "Café", body: "naïve 搜索 بحث" },
    { id: "2", title: "cafe\u0301", body: "other" }
  ]);
  assert.deepEqual(index.search("CAFÉ", { limit: 10 }).map((row) => row.id), ["1", "2"]);
  assert.deepEqual(index.search("搜索", { limit: 10 }).map((row) => row.id), ["1"]);
  assert.deepEqual(index.search("بحث", { limit: 10 }).map((row) => row.id), ["1"]);
});

test("remove deletes documents and orphan postings", () => {
  const index = makeIndex();
  index.add({ id: "1", title: "orphan", body: "remove me" });
  assert.equal(index.docFrequency("orphan"), 1);
  assert.equal(index.remove("1"), true);
  assert.equal(index.has("1"), false);
  assert.equal(index.docFrequency("orphan"), 0);
  assert.deepEqual([...index.terms()], []);
});

test("upsert replaces old postings", () => {
  const index = makeIndex();
  index.add({ id: "1", title: "old", body: "" });
  index.add({ id: "1", title: "new", body: "" });
  assert.deepEqual(index.search("old"), []);
  assert.deepEqual(index.search("new").map((row) => row.id), ["1"]);
  assert.equal(index.size, 1);
});

test("serialization roundtrip preserves equivalent results", () => {
  const index = makeIndex();
  index.addAll([{ id: "1", title: "hello", body: "world", tags: ["tag"] }, { id: "2", title: "other", body: "world" }]);
  const restored = SearchIndex.fromJSON<Doc>(index.toJSON());
  assert.deepEqual(restored.search("world", { limit: 10 }).map((row) => row.id), index.search("world", { limit: 10 }).map((row) => row.id));
  assert.deepEqual([...restored.docs()].map((entry) => entry.id), ["1", "2"]);
});

test("snippet highlights matches and handles nonmatching requested field", () => {
  const index = makeIndex();
  index.add({ id: "1", title: "intro", body: "the quick brown fox jumps over the lazy dog" });
  const bodySnippet = index.search("brown", { snippet: { field: "body", length: 20 } })[0]?.snippet;
  assert.match(bodySnippet ?? "", /<mark>brown<\/mark>/u);
  const titleSnippet = index.search("brown", { snippet: { field: "title", length: 20 } })[0]?.snippet;
  assert.equal(titleSnippet, "intro");
});

test("update reindexes changed declared fields and ignores undeclared fields", () => {
  const index = makeIndex();
  index.add({ id: "1", title: "keep", body: "old", tags: ["x"], year: 2024, extra: "ignored" });
  assert.equal(index.update("1", { body: "new" }), true);
  assert.deepEqual(index.search("old"), []);
  assert.deepEqual(index.search("new").map((row) => row.id), ["1"]);
  assert.deepEqual(index.search("keep").map((row) => row.id), ["1"]);
  assert.deepEqual(index.search("ignored"), []);
});

test("empty, whitespace, all-stopword, missing fields, filters, pagination, prefix, and nonexistent boosts are safe", () => {
  const index = makeIndex();
  assert.deepEqual(index.search(""), []);
  assert.deepEqual(index.search("   "), []);
  index.addAll([{ id: "1", title: "prefixable", body: undefined }, { id: "2", title: "prefixology", year: 2025 }]);
  assert.deepEqual(index.search("the and of"), []);
  assert.deepEqual(index.search({ prefix: "prefix" }, { limit: 10 }).map((row) => row.id), ["1", "2"]);
  assert.deepEqual(index.search("prefixable", { boostFields: { nope: 99 }, filter: (doc) => doc.id === "1" }).map((row) => row.id), ["1"]);
  assert.deepEqual(index.search({ prefix: "prefix" }, { offset: 1, limit: 1 }).map((row) => row.id), ["2"]);
});

test("very long documents can be indexed", () => {
  const index = makeIndex();
  const long = `${"filler ".repeat(20000)} needle`;
  index.add({ id: "1", title: "long", body: long });
  assert.deepEqual(index.search("needle").map((row) => row.id), ["1"]);
});
