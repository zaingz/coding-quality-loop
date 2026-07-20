import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { SearchIndex } from "../src/index.js";

interface Doc {
  id: string;
  title: string;
  body: string;
}

describe("Snippets", () => {
  test("returns a highlighted excerpt around the match", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    idx.add({
      id: "1",
      title: "doc",
      body: "The quick brown fox jumps over the lazy dog in the meadow near the river.",
    });
    const results = idx.search("fox", { snippet: { field: "body", length: 40 } });
    assert.equal(results.length, 1);
    const snippet = results[0]?.snippet;
    assert.ok(snippet !== undefined);
    assert.ok(snippet?.includes("<mark>fox</mark>"));
  });

  test("snippet on a field that does not contain the match still returns without throwing", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    idx.add({ id: "1", title: "fox story", body: "nothing to do with the query term here" });
    const results = idx.search("fox", { snippet: { field: "body", length: 20 } });
    assert.equal(results.length, 1);
    // Should not throw, and snippet should be defined (excerpt without mark)
    assert.doesNotThrow(() => results[0]?.snippet);
    const snippet = results[0]?.snippet;
    assert.ok(snippet !== undefined);
    assert.ok(!snippet?.includes("<mark>"));
  });

  test("no snippet field requested means no snippet property set meaningfully", () => {
    const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
    idx.add({ id: "1", title: "fox", body: "" });
    const results = idx.search("fox");
    assert.equal(results[0]?.snippet, undefined);
  });
});
