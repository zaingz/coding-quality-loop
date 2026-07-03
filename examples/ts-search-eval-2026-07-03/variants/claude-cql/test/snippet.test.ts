import { test } from "node:test";
import assert from "node:assert/strict";
import { SearchIndex } from "../src/SearchIndex.js";

interface Doc {
  id: string;
  title: string;
  body: string;
}

test("snippet: returns a highlighted excerpt around the match", () => {
  const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
  idx.add({
    id: "1",
    title: "t",
    body: "This is a long body of text that eventually mentions the special keyword somewhere in the middle of it all.",
  });
  const results = idx.search({ term: "keyword" }, { snippet: { field: "body", length: 40 } });
  assert.equal(results.length, 1);
  const snippet = results[0]?.snippet ?? "";
  assert.match(snippet, /<mark>keyword<\/mark>/i);
});

test("snippet: field that doesn't contain the match doesn't throw, returns usable text", () => {
  const idx = new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
  idx.add({ id: "1", title: "keyword here", body: "no relation at all in this field" });
  assert.doesNotThrow(() => {
    idx.search({ term: "keyword" }, { snippet: { field: "body", length: 30 } });
  });
  const results = idx.search({ term: "keyword" }, { snippet: { field: "body", length: 30 } });
  assert.equal(results.length, 1);
  // No <mark> since "keyword" isn't in body.
  assert.ok(!(results[0]?.snippet ?? "").includes("<mark>"));
});
