import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { SearchIndex } from "../src/index.js";

interface Doc {
  id: string;
  title: string;
  body: string;
  tags?: string[];
}

function makeIndex(): SearchIndex<Doc> {
  return new SearchIndex<Doc>({
    fields: {
      title: { boost: 3 },
      body: { boost: 1 },
      tags: { boost: 2 },
    },
  });
}

describe("Index construction & basic mutation", () => {
  test("empty index has size 0", () => {
    const idx = makeIndex();
    assert.equal(idx.size, 0);
  });

  test("add and has()", () => {
    const idx = makeIndex();
    idx.add({ id: "1", title: "Hello world", body: "some body text" });
    assert.equal(idx.size, 1);
    assert.equal(idx.has("1"), true);
    assert.equal(idx.has("2"), false);
  });

  test("addAll batch add", () => {
    const idx = makeIndex();
    idx.addAll([
      { id: "1", title: "a", body: "b" },
      { id: "2", title: "c", body: "d" },
    ]);
    assert.equal(idx.size, 2);
  });

  test("upsert: adding doc with existing id replaces it", () => {
    const idx = makeIndex();
    idx.add({ id: "1", title: "first version", body: "" });
    idx.add({ id: "1", title: "second version", body: "" });
    assert.equal(idx.size, 1);
    const results = idx.search("first");
    assert.equal(results.length, 0);
    const results2 = idx.search("second");
    assert.equal(results2.length, 1);
  });

  test("missing declared field is fine (empty)", () => {
    const idx = makeIndex();
    assert.doesNotThrow(() => idx.add({ id: "1", title: "only title" } as Doc));
    assert.equal(idx.size, 1);
  });

  test("undeclared field is silently ignored", () => {
    const idx = makeIndex();
    const doc = { id: "1", title: "hello", body: "world", extra: "ignored" } as Doc & {
      extra: string;
    };
    assert.doesNotThrow(() => idx.add(doc));
    const results = idx.search("ignored");
    assert.equal(results.length, 0);
  });

  test("remove deletes doc and cleans orphaned postings", () => {
    const idx = makeIndex();
    idx.add({ id: "1", title: "unique-term-xyz", body: "" });
    assert.equal(idx.docFrequency("unique-term-xyz"), 1);
    idx.remove("1");
    assert.equal(idx.has("1"), false);
    assert.equal(idx.size, 0);
    assert.equal(idx.docFrequency("unique-term-xyz"), 0);
    // internal terms() should not include orphaned term
    const terms = Array.from(idx.terms());
    assert.equal(terms.includes("unique-term-xyz"), false);
  });

  test("remove is safe for a mid-search-session doc", () => {
    const idx = makeIndex();
    idx.add({ id: "1", title: "apple", body: "" });
    idx.add({ id: "2", title: "apple", body: "" });
    const before = idx.search("apple");
    assert.equal(before.length, 2);
    idx.remove("1");
    const after = idx.search("apple");
    assert.equal(after.length, 1);
    assert.equal(after[0]?.id, "2");
  });

  test("update reindexes only changed field", () => {
    const idx = makeIndex();
    idx.add({ id: "1", title: "zeta-titleword", body: "alpha-bodyword" });
    idx.update("1", { body: "gamma-newbodyword" });

    // title unaffected
    assert.equal(idx.search("zeta-titleword").length, 1);
    // old body term fully gone (distinct vocabulary from title, so no cross-field overlap)
    assert.equal(idx.search("alpha-bodyword").length, 0);
    assert.equal(idx.docFrequency("alpha"), 0);
    assert.equal(idx.docFrequency("bodyword"), 0);
    // new body term present
    assert.equal(idx.search("gamma-newbodyword").length, 1);
  });

  test("update throws for nonexistent id", () => {
    const idx = makeIndex();
    assert.throws(() => idx.update("missing", { title: "x" }));
  });

  test("index.docs() iterates all live docs", () => {
    const idx = makeIndex();
    idx.add({ id: "1", title: "a", body: "" });
    idx.add({ id: "2", title: "b", body: "" });
    const all = Array.from(idx.docs());
    assert.equal(all.length, 2);
    const ids = all.map((d) => d.id).sort();
    assert.deepEqual(ids, ["1", "2"]);
  });
});

describe("Empty / whitespace query handling", () => {
  test("empty index, any query returns empty results", () => {
    const idx = makeIndex();
    assert.deepEqual(idx.search("hello"), []);
  });

  test("empty string query returns empty results", () => {
    const idx = makeIndex();
    idx.add({ id: "1", title: "hello", body: "" });
    assert.deepEqual(idx.search(""), []);
  });

  test("whitespace-only query returns empty results", () => {
    const idx = makeIndex();
    idx.add({ id: "1", title: "hello", body: "" });
    assert.deepEqual(idx.search("   \t  "), []);
  });

  test("query with all-stopword terms returns empty results", () => {
    const idx = makeIndex();
    idx.add({ id: "1", title: "the quick fox", body: "" });
    const results = idx.search("the a of");
    assert.deepEqual(results, []);
  });
});

describe("Long documents", () => {
  test("handles a 100KB body without error", () => {
    const idx = makeIndex();
    const word = "lorem ";
    const longBody = word.repeat(Math.ceil((100 * 1024) / word.length));
    assert.doesNotThrow(() => idx.add({ id: "1", title: "big doc", body: longBody }));
    const results = idx.search("lorem");
    assert.equal(results.length, 1);
  });
});
