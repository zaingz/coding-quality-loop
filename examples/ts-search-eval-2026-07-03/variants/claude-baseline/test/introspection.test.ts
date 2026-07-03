import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { SearchIndex } from "../src/index.js";

interface Doc {
  id: string;
  title: string;
  body: string;
}

describe("Introspection", () => {
  test("terms() lists unique terms across the index", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    idx.add({ id: "1", title: "apple banana", body: "" });
    idx.add({ id: "2", title: "banana cherry", body: "" });
    const terms = new Set(idx.terms());
    assert.ok(terms.has("apple"));
    assert.ok(terms.has("banana"));
    assert.ok(terms.has("cherry"));
  });

  test("docFrequency counts distinct docs containing the term", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    idx.add({ id: "1", title: "shared term", body: "" });
    idx.add({ id: "2", title: "shared term", body: "" });
    idx.add({ id: "3", title: "other", body: "" });
    assert.equal(idx.docFrequency("shared"), 2);
    assert.equal(idx.docFrequency("term"), 2);
    assert.equal(idx.docFrequency("nonexistent"), 0);
  });
});

describe("No global state between instances", () => {
  test("two SearchIndex instances do not interfere", () => {
    const idx1 = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    const idx2 = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    idx1.add({ id: "1", title: "only in idx1", body: "" });
    idx2.add({ id: "1", title: "only in idx2", body: "" });

    assert.equal(idx1.search("idx1").length, 1);
    assert.equal(idx1.search("idx2").length, 0);
    assert.equal(idx2.search("idx2").length, 1);
    assert.equal(idx2.search("idx1").length, 0);
  });
});

describe("Determinism", () => {
  test("same input produces same output across repeated searches", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 2 }, body: { boost: 1 } } });
    idx.add({ id: "1", title: "alpha beta", body: "gamma" });
    idx.add({ id: "2", title: "beta gamma", body: "alpha" });
    idx.add({ id: "3", title: "gamma alpha", body: "beta" });

    const r1 = idx.search("alpha beta gamma");
    const r2 = idx.search("alpha beta gamma");
    assert.deepEqual(
      r1.map((r) => ({ id: r.id, score: r.score })),
      r2.map((r) => ({ id: r.id, score: r.score }))
    );
  });
});
