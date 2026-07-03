import { test } from "node:test";
import assert from "node:assert/strict";
import { SearchIndex } from "../src/SearchIndex.js";

interface Doc {
  id: string;
  title: string;
  body: string;
  tags?: string[];
}

function makeIndex(): SearchIndex<Doc> {
  return new SearchIndex<Doc>({
    fields: { title: { boost: 3 }, body: { boost: 1 }, tags: { boost: 2 } },
  });
}

test("crud: add/has/size", () => {
  const idx = makeIndex();
  assert.equal(idx.size, 0);
  idx.add({ id: "1", title: "Hello", body: "World" });
  assert.equal(idx.size, 1);
  assert.equal(idx.has("1"), true);
  assert.equal(idx.has("2"), false);
});

test("crud: addAll batch add", () => {
  const idx = makeIndex();
  idx.addAll([
    { id: "1", title: "One", body: "first doc" },
    { id: "2", title: "Two", body: "second doc" },
  ]);
  assert.equal(idx.size, 2);
});

test("crud: add with existing id upserts, not duplicates", () => {
  const idx = makeIndex();
  idx.add({ id: "1", title: "Original", body: "text" });
  idx.add({ id: "1", title: "Replaced", body: "new text" });
  assert.equal(idx.size, 1);
  const results = idx.search({ term: "replaced" });
  assert.equal(results.length, 1);
  assert.equal(results[0]?.doc.title, "Replaced");
  const stale = idx.search({ term: "original" });
  assert.equal(stale.length, 0);
});

test("crud: remove deletes doc and cleans orphaned postings", () => {
  const idx = makeIndex();
  idx.add({ id: "1", title: "Unique Zebra Term", body: "body one" });
  idx.add({ id: "2", title: "Other doc", body: "body two" });
  assert.equal(idx.docFrequency("zebra"), 1);
  idx.remove("1");
  assert.equal(idx.has("1"), false);
  assert.equal(idx.size, 1);
  // Orphaned term "zebra" (unique to doc 1) must be fully gone.
  assert.equal(idx.docFrequency("zebra"), 0);
  assert.equal([...idx.terms()].includes("zebra"), false);
});

test("crud: remove mid-search-session changes subsequent results", () => {
  const idx = makeIndex();
  idx.add({ id: "1", title: "Removable Item", body: "content" });
  idx.add({ id: "2", title: "Stable Item", body: "content" });
  const before = idx.search({ term: "removable" });
  assert.equal(before.length, 1);
  idx.remove("1");
  const after = idx.search({ term: "removable" });
  assert.equal(after.length, 0);
});

test("crud: update reindexes only the changed field", () => {
  const idx = makeIndex();
  idx.add({ id: "1", title: "StableTitleWord", body: "originalbodyword" });
  idx.update("1", { body: "newbodyword" });

  // Unchanged field (title) still matches.
  const titleMatch = idx.search({ term: "stabletitleword" });
  assert.equal(titleMatch.length, 1);

  // Old body term no longer matches; new body term does.
  const oldBody = idx.search({ term: "originalbodyword" });
  assert.equal(oldBody.length, 0);
  const newBody = idx.search({ term: "newbodyword" });
  assert.equal(newBody.length, 1);
});

test("crud: schema-safety — missing declared field is fine", () => {
  const idx = makeIndex();
  assert.doesNotThrow(() => idx.add({ id: "1", title: "Only title", body: "" }));
  assert.equal(idx.size, 1);
});

test("crud: schema-safety — undeclared field is silently ignored", () => {
  // Constructed directly with the extended doc type (no unsafe cast needed)
  // so the "extra" field is a genuinely undeclared field relative to
  // `fields: { title, body, tags }`.
  type ExtendedDoc = Doc & { extra?: string };
  const idx2 = new SearchIndex<ExtendedDoc>({
    fields: { title: { boost: 3 }, body: { boost: 1 }, tags: { boost: 2 } },
  });
  assert.doesNotThrow(() =>
    idx2.add({ id: "1", title: "Title", body: "Body", extra: "should not be searchable" }),
  );
  const results = idx2.search({ term: "should" });
  assert.equal(results.length, 0);
});

test("crud: docs() iterates all live docs, not removed ones", () => {
  const idx = makeIndex();
  idx.add({ id: "1", title: "A", body: "a" });
  idx.add({ id: "2", title: "B", body: "b" });
  idx.remove("1");
  const all = [...idx.docs()];
  assert.equal(all.length, 1);
  assert.equal(all[0]?.id, "2");
});

test("crud: two SearchIndex instances do not interfere (no global state)", () => {
  const a = makeIndex();
  const b = makeIndex();
  a.add({ id: "1", title: "OnlyInA", body: "x" });
  assert.equal(a.size, 1);
  assert.equal(b.size, 0);
  assert.equal(b.search({ term: "onlyina" }).length, 0);
});
