// Shared correctness suite — runs against a variant's built library.
// Usage: node shared-tests.mjs <path-to-variant-root>
// Expects the variant to have `dist/index.js` after `npm run build`.

import { pathToFileURL } from "node:url";
import path from "node:path";
import assert from "node:assert/strict";

const variantRoot = process.argv[2];
if (!variantRoot) {
  console.error("Usage: node shared-tests.mjs <variant-root>");
  process.exit(2);
}

// Try common entry points
const candidates = [
  "dist/index.js",
  "dist/src/index.js",
  "dist/main.js",
  "dist/SearchIndex.js",
];
let mod = null;
let usedEntry = null;
for (const c of candidates) {
  const abs = path.join(variantRoot, c);
  try {
    mod = await import(pathToFileURL(abs).href);
    usedEntry = c;
    break;
  } catch (e) {
    // try next
  }
}
if (!mod) {
  console.error(`FAIL: could not import any of ${candidates.join(", ")} from ${variantRoot}`);
  process.exit(1);
}

// Try common export names
const SearchIndex =
  mod.SearchIndex ||
  mod.MiniSearch ||
  mod.default?.SearchIndex ||
  mod.default;

if (typeof SearchIndex !== "function") {
  console.error("FAIL: no SearchIndex constructor exported. keys:", Object.keys(mod));
  process.exit(1);
}

const results = [];
function T(name, fn) {
  try {
    const ret = fn();
    if (ret && typeof ret.then === "function") {
      // async
      return ret.then(
        () => results.push({ name, pass: true }),
        (e) => results.push({ name, pass: false, err: String(e).slice(0, 300) })
      );
    }
    results.push({ name, pass: true });
  } catch (e) {
    results.push({ name, pass: false, err: String(e).slice(0, 300) });
  }
}

// ---------------- Tests ----------------

T("constructor accepts fields config", () => {
  const idx = new SearchIndex({
    fields: { title: { boost: 3 }, body: { boost: 1 } },
  });
  assert.equal(idx.size, 0);
});

T("add and size", () => {
  const idx = new SearchIndex({ fields: { title: {}, body: {} } });
  idx.add({ id: "1", title: "hello world", body: "" });
  idx.add({ id: "2", title: "foo bar", body: "" });
  assert.equal(idx.size, 2);
});

T("upsert (add with existing id replaces)", () => {
  const idx = new SearchIndex({ fields: { title: {}, body: {} } });
  idx.add({ id: "1", title: "hello", body: "" });
  idx.add({ id: "1", title: "world", body: "" });
  assert.equal(idx.size, 1);
  const r = idx.search("hello");
  assert.equal(r.length, 0);
  const r2 = idx.search("world");
  assert.equal(r2.length, 1);
});

T("remove eliminates doc from results", () => {
  const idx = new SearchIndex({ fields: { title: {}, body: {} } });
  idx.add({ id: "1", title: "hello world", body: "" });
  idx.add({ id: "2", title: "foo bar", body: "" });
  idx.remove("1");
  assert.equal(idx.size, 1);
  const r = idx.search("hello");
  assert.equal(r.length, 0);
});

T("empty query returns []", () => {
  const idx = new SearchIndex({ fields: { title: {} } });
  idx.add({ id: "1", title: "hello", body: "" });
  const r = idx.search("");
  assert.deepEqual(r, []);
});

T("whitespace-only query returns []", () => {
  const idx = new SearchIndex({ fields: { title: {} } });
  idx.add({ id: "1", title: "hello", body: "" });
  const r = idx.search("   ");
  assert.deepEqual(r, []);
});

T("default operator is OR", () => {
  const idx = new SearchIndex({ fields: { body: {} } });
  idx.add({ id: "1", body: "alpha" });
  idx.add({ id: "2", body: "beta" });
  const r = idx.search("alpha beta");
  assert.equal(r.length, 2);
});

T("AND operator", () => {
  const idx = new SearchIndex({ fields: { body: {} } });
  idx.add({ id: "1", body: "alpha beta" });
  idx.add({ id: "2", body: "alpha" });
  idx.add({ id: "3", body: "beta" });
  const r = idx.search("alpha AND beta");
  assert.equal(r.length, 1);
  assert.equal(r[0].id, "1");
});

T("NOT operator", () => {
  const idx = new SearchIndex({ fields: { body: {} } });
  idx.add({ id: "1", body: "alpha" });
  idx.add({ id: "2", body: "alpha beta" });
  const r = idx.search("alpha NOT beta");
  assert.equal(r.length, 1);
  assert.equal(r[0].id, "1");
});

T("phrase query slop=0 (adjacency required)", () => {
  const idx = new SearchIndex({ fields: { body: {} }, stopwords: "none" });
  idx.add({ id: "1", body: "quick brown fox" });
  idx.add({ id: "2", body: "quick red brown fox" });
  const r = idx.search('"quick brown"');
  const ids = r.map(x => x.id).sort();
  assert.deepEqual(ids, ["1"], `expected only doc 1, got ${JSON.stringify(ids)}`);
});

T("field: prefix syntax", () => {
  const idx = new SearchIndex({ fields: { title: {}, body: {} } });
  idx.add({ id: "1", title: "alpha", body: "beta" });
  idx.add({ id: "2", title: "beta", body: "alpha" });
  const r = idx.search("title:alpha");
  assert.equal(r.length, 1);
  assert.equal(r[0].id, "1");
});

T("BM25: field boost affects ranking", () => {
  const idx = new SearchIndex({ fields: { title: { boost: 5 }, body: { boost: 1 } } });
  idx.add({ id: "1", title: "rare", body: "common common common" });
  idx.add({ id: "2", title: "common", body: "rare common common" });
  const r = idx.search("rare");
  assert.equal(r.length, 2);
  assert.equal(r[0].id, "1", "title-boosted match should rank first");
});

T("unicode: lowercase café matches CAFÉ", () => {
  const idx = new SearchIndex({ fields: { body: {} } });
  idx.add({ id: "1", body: "café menu" });
  const r = idx.search("CAFÉ");
  assert.ok(r.length >= 1, "expected uppercase unicode query to match lowercase indexed term");
});

T("unicode: non-ASCII (Chinese) tokens", () => {
  const idx = new SearchIndex({ fields: { body: {} }, stopwords: "none" });
  idx.add({ id: "1", body: "搜索 引擎" });
  const r = idx.search("搜索");
  assert.equal(r.length, 1);
});

T("structured query: term", () => {
  const idx = new SearchIndex({ fields: { body: {} } });
  idx.add({ id: "1", body: "hello" });
  const r = idx.search({ term: "hello" });
  assert.equal(r.length, 1);
});

T("structured query: and/or/not", () => {
  const idx = new SearchIndex({ fields: { body: {} } });
  idx.add({ id: "1", body: "alpha beta" });
  idx.add({ id: "2", body: "alpha" });
  const r = idx.search({ and: [{ term: "alpha" }, { term: "beta" }] });
  assert.equal(r.length, 1);
  assert.equal(r[0].id, "1");
});

T("fuzzy: colour matches color with maxEdits=1", () => {
  const idx = new SearchIndex({ fields: { body: {} } });
  idx.add({ id: "1", body: "color palette" });
  const r = idx.search({ fuzzy: "colour", maxEdits: 1 });
  assert.ok(r.length >= 1, "fuzzy colour->color with edit distance 1 should match");
});

T("limit + offset", () => {
  const idx = new SearchIndex({ fields: { body: {} } });
  for (let i = 0; i < 10; i++) idx.add({ id: String(i), body: "match" });
  const r = idx.search("match", { limit: 3, offset: 2 });
  assert.equal(r.length, 3);
});

T("filter callback", () => {
  const idx = new SearchIndex({ fields: { body: {} } });
  idx.add({ id: "1", body: "match", cat: "a" });
  idx.add({ id: "2", body: "match", cat: "b" });
  const r = idx.search("match", { filter: (d) => d.cat === "a" });
  assert.equal(r.length, 1);
  assert.equal(r[0].id, "1");
});

T("snippet returns <mark>", () => {
  const idx = new SearchIndex({ fields: { body: {} } });
  idx.add({ id: "1", body: "the quick brown fox jumps" });
  const r = idx.search("quick", { snippet: { field: "body", length: 40 } });
  assert.ok(r[0].snippet, "expected snippet");
  assert.ok(r[0].snippet.includes("<mark>"), `expected <mark>, got: ${r[0].snippet}`);
});

T("serialization roundtrip", () => {
  const idx = new SearchIndex({ fields: { title: {}, body: {} } });
  idx.add({ id: "1", title: "hello", body: "world" });
  idx.add({ id: "2", title: "foo", body: "bar" });
  const snapshot = idx.toJSON();
  const restored = SearchIndex.fromJSON(snapshot);
  assert.equal(restored.size, 2);
  const r = restored.search("hello");
  assert.equal(r.length, 1);
  assert.equal(r[0].id, "1");
});

T("deterministic tie-break by id ASC", () => {
  const idx = new SearchIndex({ fields: { body: {} } });
  idx.add({ id: "b", body: "match" });
  idx.add({ id: "a", body: "match" });
  const r = idx.search("match");
  assert.deepEqual(r.map(x => x.id), ["a", "b"]);
});

T("has(id)", () => {
  const idx = new SearchIndex({ fields: { body: {} } });
  idx.add({ id: "1", body: "hi" });
  assert.equal(idx.has("1"), true);
  assert.equal(idx.has("nope"), false);
});

T("update reindexes only patched field", () => {
  const idx = new SearchIndex({ fields: { title: {}, body: {} } });
  idx.add({ id: "1", title: "old", body: "keep" });
  idx.update("1", { title: "new" });
  const r1 = idx.search("old");
  assert.equal(r1.length, 0);
  const r2 = idx.search("keep");
  assert.equal(r2.length, 1);
  const r3 = idx.search("new");
  assert.equal(r3.length, 1);
});

// -------- Wait for async, print summary --------
await Promise.resolve();

const total = results.length;
const passed = results.filter(r => r.pass).length;
const failed = total - passed;

console.log(JSON.stringify({
  variant: variantRoot,
  entry: usedEntry,
  total,
  passed,
  failed,
  failures: results.filter(r => !r.pass).map(r => ({ name: r.name, err: r.err })),
}, null, 2));

process.exit(failed > 0 ? 1 : 0);
