import { test } from "node:test";
import assert from "node:assert/strict";
import { SearchIndex } from "../src/SearchIndex.js";

interface Doc {
  id: string;
  title: string;
  body: string;
}

function makeIndex(): SearchIndex<Doc> {
  const idx = new SearchIndex<Doc>({ fields: { title: { boost: 3 }, body: { boost: 1 } } });
  idx.addAll([
    { id: "1", title: "apple banana", body: "fruit salad" },
    { id: "2", title: "apple only", body: "no other fruit" },
    { id: "3", title: "banana only", body: "no other fruit" },
    { id: "4", title: "carrot vegetable", body: "not a fruit" },
    { id: "5", title: "apple banana carrot", body: "everything" },
  ]);
  return idx;
}

test("query-parser: boolean AND NOT — 'apple AND banana NOT carrot'", () => {
  const idx = makeIndex();
  const results = idx.search("apple AND banana NOT carrot");
  const ids = results.map((r) => r.id).sort();
  // doc1 has apple+banana, no carrot. doc5 has apple+banana+carrot (excluded).
  assert.deepEqual(ids, ["1"]);
});

test("query-parser: default operator is OR", () => {
  const idx = makeIndex();
  const results = idx.search("apple carrot");
  const ids = results.map((r) => r.id).sort();
  // any doc containing apple OR carrot: 1,2,4,5
  assert.deepEqual(ids, ["1", "2", "4", "5"]);
});

test("query-parser: quoted phrase inside boolean string", () => {
  const idx = makeIndex();
  const results = idx.search('"apple banana"');
  const ids = results.map((r) => r.id).sort();
  // Both doc1 ("apple banana") and doc5 ("apple banana carrot") contain the
  // adjacent phrase "apple banana" at slop 0.
  assert.deepEqual(ids, ["1", "5"]);
});

test("query-parser: field prefix restricts search to a field", () => {
  const idx = makeIndex();
  const results = idx.search("title:carrot");
  const ids = results.map((r) => r.id).sort();
  assert.deepEqual(ids, ["4", "5"]);
  const noneInBody = idx.search("body:carrot");
  assert.deepEqual(noneInBody, []);
});

test("query-parser: explicit precedence NOT > AND > OR", () => {
  const idx = makeIndex();
  // "carrot OR apple AND banana NOT carrot" => carrot OR (apple AND banana AND NOT carrot)
  // apple AND banana NOT carrot => doc1 only. OR carrot => docs with carrot: 4,5. Union: 1,4,5
  const results = idx.search("carrot OR apple AND banana NOT carrot");
  const ids = results.map((r) => r.id).sort();
  assert.deepEqual(ids, ["1", "4", "5"]);
});

test("query-parser: deeply nested AND/OR/NOT with parens", () => {
  const idx = makeIndex();
  const results = idx.search("(apple AND banana) OR (carrot AND NOT apple)");
  const ids = results.map((r) => r.id).sort();
  // apple AND banana: 1, 5. carrot AND NOT apple: 4. Union: 1,4,5
  assert.deepEqual(ids, ["1", "4", "5"]);
});

test("query-parser: empty query returns empty results", () => {
  const idx = makeIndex();
  assert.deepEqual(idx.search(""), []);
});

test("query-parser: whitespace-only query returns empty results", () => {
  const idx = makeIndex();
  assert.deepEqual(idx.search("   \t  "), []);
});

test("query-parser: all-stopword query returns empty results without throwing", () => {
  const idx = makeIndex();
  assert.doesNotThrow(() => idx.search("the and of"));
  assert.deepEqual(idx.search("the and of"), []);
});

test("query-parser: structured term query", () => {
  const idx = makeIndex();
  const results = idx.search({ term: "apple" });
  const ids = results.map((r) => r.id).sort();
  assert.deepEqual(ids, ["1", "2", "5"]);
});

test("query-parser: structured and/or/not composition, nested", () => {
  const idx = makeIndex();
  const q = {
    or: [
      { and: [{ term: "apple" }, { term: "banana" }] },
      { not: { term: "apple" } },
    ],
  };
  const results = idx.search(q);
  const ids = results.map((r) => r.id).sort();
  // apple AND banana: 1,5. NOT apple: 3,4. Union: 1,3,4,5
  assert.deepEqual(ids, ["1", "3", "4", "5"]);
});

test("query-parser: prefix query matches indexed tokens by prefix", () => {
  const idx = makeIndex();
  const results = idx.search({ prefix: "car" });
  const ids = results.map((r) => r.id).sort();
  assert.deepEqual(ids, ["4", "5"]);
});

test("query-parser: field boost with nonexistent field name does not throw", () => {
  const idx = makeIndex();
  assert.doesNotThrow(() => idx.search("apple", { boostFields: { doesNotExist: 5 } }));
});
