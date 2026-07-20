import { test } from "node:test";
import assert from "node:assert/strict";
import { SearchIndex } from "../src/SearchIndex.js";

interface Doc {
  id: string;
  title: string;
  body: string;
  tags: string[];
}

function makeIndex(): SearchIndex<Doc> {
  const idx = new SearchIndex<Doc>({ fields: { title: { boost: 3 }, body: { boost: 1 }, tags: { boost: 2 } } });
  idx.addAll([
    { id: "1", title: "apple pie recipe", body: "delicious dessert with apples", tags: ["food", "dessert"] },
    { id: "2", title: "banana bread", body: "moist bread with bananas", tags: ["food", "baking"] },
    { id: "3", title: "car engine repair", body: "fixing the engine of your car", tags: ["auto"] },
  ]);
  return idx;
}

test("serialization: toJSON produces a plain-JSON snapshot", () => {
  const idx = makeIndex();
  const snap = idx.toJSON();
  assert.doesNotThrow(() => JSON.parse(JSON.stringify(snap)));
  assert.equal(snap.version, 1);
  assert.equal(snap.idField, "id");
});

test("serialization: fromJSON(toJSON()) round trip gives equivalent search results", () => {
  const idx = makeIndex();
  const snap = idx.toJSON();
  const restored = SearchIndex.fromJSON<Doc>(snap);

  assert.equal(restored.size, idx.size);

  const queries: (string | { term: string })[] = ["apple", "bread AND car", { term: "engine" }];
  for (const q of queries) {
    const original = idx.search(q as never);
    const roundTripped = restored.search(q as never);
    assert.deepEqual(
      roundTripped.map((r) => ({ id: r.id, score: r.score })),
      original.map((r) => ({ id: r.id, score: r.score })),
    );
  }
});

test("serialization: fromJSON via JSON.stringify/parse (true serialization boundary)", () => {
  const idx = makeIndex();
  const text = JSON.stringify(idx.toJSON());
  const parsed = JSON.parse(text);
  const restored = SearchIndex.fromJSON<Doc>(parsed);
  const results = restored.search({ term: "apple" });
  assert.deepEqual(results.map((r) => r.id), ["1"]);
});

test("serialization: restored index supports further mutation", () => {
  const idx = makeIndex();
  const restored = SearchIndex.fromJSON<Doc>(idx.toJSON());
  restored.add({ id: "4", title: "new doc", body: "fresh content", tags: [] });
  assert.equal(restored.size, 4);
  assert.equal(idx.size, 3); // original unaffected
});
