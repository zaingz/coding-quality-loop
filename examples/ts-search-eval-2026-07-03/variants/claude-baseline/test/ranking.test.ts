import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { SearchIndex } from "../src/index.js";

interface Doc {
  id: string;
  title: string;
  body: string;
}

describe("BM25 ranking", () => {
  test("title match ranks higher than body match when title is boosted", () => {
    const idx = new SearchIndex<Doc>({
      fields: { title: { boost: 3 }, body: { boost: 1 } },
    });
    idx.add({ id: "titleDoc", title: "unicorn special term here", body: "nothing relevant" });
    idx.add({ id: "bodyDoc", title: "nothing relevant", body: "unicorn special term here" });

    const results = idx.search("unicorn");
    assert.equal(results.length, 2);
    assert.equal(results[0]?.id, "titleDoc");
    assert.ok((results[0]?.score ?? 0) > (results[1]?.score ?? 0));
  });

  test("results sorted by score desc, ties broken by id asc", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    idx.add({ id: "b", title: "zephyr zephyr", body: "" });
    idx.add({ id: "a", title: "zephyr zephyr", body: "" });
    idx.add({ id: "c", title: "zephyr zephyr", body: "" });
    const results = idx.search("zephyr");
    assert.deepEqual(
      results.map((r) => r.id),
      ["a", "b", "c"]
    );
  });

  test("more term frequency yields higher score (all else equal)", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    idx.add({ id: "1", title: "", body: "dog dog dog dog cat" });
    idx.add({ id: "2", title: "", body: "dog cat cat cat cat" });
    const results = idx.search("dog");
    assert.equal(results[0]?.id, "1");
  });

  test("field boost override via boostFields option", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    idx.add({ id: "titleDoc", title: "special", body: "" });
    idx.add({ id: "bodyDoc", title: "", body: "special" });
    const results = idx.search("special", { boostFields: { title: 10 } });
    assert.equal(results[0]?.id, "titleDoc");
  });

  test("field boost with a nonexistent field name does not throw and is ignored", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    idx.add({ id: "1", title: "hello", body: "" });
    assert.doesNotThrow(() => idx.search("hello", { boostFields: { notarealfield: 5 } }));
    const results = idx.search("hello", { boostFields: { notarealfield: 5 } });
    assert.equal(results.length, 1);
  });

  test("limit and offset paginate results", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    for (let i = 0; i < 5; i++) {
      idx.add({ id: `d${i}`, title: "match", body: "" });
    }
    const page1 = idx.search("match", { limit: 2, offset: 0 });
    const page2 = idx.search("match", { limit: 2, offset: 2 });
    assert.equal(page1.length, 2);
    assert.equal(page2.length, 2);
    assert.notEqual(page1[0]?.id, page2[0]?.id);
  });

  test("filter option post-filters results", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    idx.add({ id: "1", title: "match", body: "" });
    idx.add({ id: "2", title: "match", body: "" });
    const results = idx.search("match", { filter: (doc) => doc.id === "2" });
    assert.equal(results.length, 1);
    assert.equal(results[0]?.id, "2");
  });
});
