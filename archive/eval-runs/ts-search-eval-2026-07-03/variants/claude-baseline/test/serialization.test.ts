import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { SearchIndex } from "../src/index.js";

interface Doc {
  id: string;
  title: string;
  body: string;
}

describe("Serialization", () => {
  test("toJSON/fromJSON roundtrip gives an equivalent index", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 3 }, body: { boost: 1 } } });
    idx.add({ id: "1", title: "quick brown fox", body: "the lazy dog sleeps" });
    idx.add({ id: "2", title: "café culture", body: "unicode test 搜索" });
    idx.add({ id: "3", title: "another doc", body: "with more words words words" });

    const snapshot = idx.toJSON();
    const json = JSON.stringify(snapshot);
    const parsed = JSON.parse(json);
    const restored = SearchIndex.fromJSON<Doc>(parsed);

    assert.equal(restored.size, idx.size);
    assert.equal(restored.has("1"), true);
    assert.equal(restored.has("2"), true);

    const originalResults = idx.search("fox");
    const restoredResults = restored.search("fox");
    assert.deepEqual(
      restoredResults.map((r) => r.id),
      originalResults.map((r) => r.id)
    );
    assert.ok(Math.abs((restoredResults[0]?.score ?? 0) - (originalResults[0]?.score ?? 0)) < 1e-9);

    // Unicode search still works after roundtrip
    const cafeResults = restored.search("café");
    assert.equal(cafeResults.length, 1);
    assert.equal(cafeResults[0]?.id, "2");

    // docFrequency matches
    assert.equal(restored.docFrequency("words"), idx.docFrequency("words"));

    // terms() sets match
    const originalTerms = new Set(idx.terms());
    const restoredTerms = new Set(restored.terms());
    assert.deepEqual(restoredTerms, originalTerms);
  });

  test("fromJSON with custom tokenizer/stopwords re-supplied works", () => {
    const idx = new SearchIndex<Doc>({
      fields: { title: { boost: 1 }, body: { boost: 1 } },
      stopwords: "none",
    });
    idx.add({ id: "1", title: "the cat sat", body: "" });
    const snapshot = JSON.parse(JSON.stringify(idx.toJSON()));
    const restored = SearchIndex.fromJSON<Doc>(snapshot, { stopwords: "none" });
    // "the" should be searchable since stopwords were 'none'
    const results = restored.search("the");
    assert.equal(results.length, 1);
  });

  test("mutations still work correctly after restoring from snapshot", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    idx.add({ id: "1", title: "original", body: "" });
    const restored = SearchIndex.fromJSON<Doc>(JSON.parse(JSON.stringify(idx.toJSON())));
    restored.add({ id: "2", title: "new doc", body: "" });
    assert.equal(restored.size, 2);
    restored.remove("1");
    assert.equal(restored.size, 1);
    assert.equal(restored.has("1"), false);
  });
});
