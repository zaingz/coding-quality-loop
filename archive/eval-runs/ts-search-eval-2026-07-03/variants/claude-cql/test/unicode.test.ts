import { test } from "node:test";
import assert from "node:assert/strict";
import { SearchIndex } from "../src/SearchIndex.js";

interface Doc {
  id: string;
  title: string;
  body: string;
}

function makeIndex(): SearchIndex<Doc> {
  return new SearchIndex<Doc>({ fields: { title: { boost: 1 }, body: { boost: 1 } } });
}

test("unicode: doc with 'café' is found by query 'café' and 'CAFÉ'", () => {
  const idx = makeIndex();
  idx.add({ id: "1", title: "café menu", body: "we serve café daily" });
  const lower = idx.search({ term: "café" });
  const upper = idx.search({ term: "CAFÉ" });
  assert.deepEqual(lower.map((r) => r.id), ["1"]);
  assert.deepEqual(upper.map((r) => r.id), ["1"]);
});

test("unicode: Chinese and Arabic terms are tokenized and searchable", () => {
  const idx = makeIndex();
  // The default tokenizer splits on runs of \p{L}\p{N}; CJK text with no
  // whitespace forms a single contiguous token per run (no CJK word
  // segmentation is implemented — that is a distinct, much larger problem
  // out of scope for this library). Space-separated CJK words, as used
  // here, tokenize as separate whole-word tokens and are fully searchable.
  idx.add({ id: "cn", title: "搜索 引擎", body: "全文 搜索 工具" });
  idx.add({ id: "ar", title: "محرك بحث", body: "بحث نص كامل" });
  assert.deepEqual(idx.search({ term: "搜索" }).map((r) => r.id), ["cn"]);
  assert.deepEqual(idx.search({ term: "بحث" }).map((r) => r.id).sort(), ["ar"]);
});

test("unicode: contiguous (unsegmented) CJK run is indexed as a single token", () => {
  const idx = makeIndex();
  idx.add({ id: "cn2", title: "搜索引擎", body: "x" });
  // A prefix/exact match on the full run works even without segmentation.
  assert.deepEqual(idx.search({ term: "搜索引擎" }).map((r) => r.id), ["cn2"]);
});

test("unicode: combining characters match precomposed equivalents", () => {
  const idx = makeIndex();
  idx.add({ id: "1", title: "cafe\u0301 combining form", body: "x" }); // e + combining acute
  const results = idx.search({ term: "caf\u00e9" }); // precomposed é
  assert.deepEqual(results.map((r) => r.id), ["1"]);
});

test("unicode: naïve is tokenized as a single word and matched", () => {
  const idx = makeIndex();
  idx.add({ id: "1", title: "naïve approach", body: "x" });
  assert.deepEqual(idx.search({ term: "naïve" }).map((r) => r.id), ["1"]);
});
