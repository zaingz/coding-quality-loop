# Validation Contract

Each acceptance criterion is paired with the concrete check that proves it.

| # | Acceptance criterion | Concrete check |
|---|---|---|
| 1 | `npm install` succeeds | Run `npm install`; exit code 0; `node_modules/` populated with only `typescript` + `@types/node` (+ transitive). |
| 2 | Build succeeds, strict, no `any`/unsafe casts | `npm run build` exit code 0. `grep -rn "\bany\b\|@ts-ignore\|@ts-expect-error\|as unknown as" src/ bench/` returns no unjustified hits. `tsconfig.json` has `"strict": true`. |
| 3 | Tests pass via Node's runner | `npm test` (→ `node --test dist/test/**/*.test.js`) exit code 0, all subtests pass, no `.skip`. |
| 4 | Benchmark runs, prints valid JSON | `node dist/bench/bench.js` exit 0; stdout parses with `JSON.parse` and matches required top-level keys (`index_build_ms`, `index_size_docs`, `index_memory_estimate_kb`, `queries` with 5 named workload keys each having `count/total_ms/p50_us/p99_us`). |
| 5 | Zero runtime deps | `node -e "console.log(Object.keys(require('./package.json').dependencies||{}).length)"` prints `0`. |
| 6 | Index construction options honored | Test: construct with `fields`, custom `tokenizer`, `stopwords: 'none'`, custom `stemmer`, custom `idField`; assert each is respected (e.g., custom idField used as key, custom tokenizer output drives matches). |
| 6a | Schema-safety: missing field ok, undeclared field ignored | Test: add doc missing a declared field → no throw, field treated empty. Add doc with extra undeclared key → indexing doesn't throw, extra key not searchable/does not affect scoring. |
| 6b | `add`/`addAll`/`remove`/`update`/`size`/`has` | Dedicated CRUD test: add doc, `has` true, `size` increments; `remove` → `has` false, `size` decrements, orphaned postings gone (`terms()` no longer contains a term unique to that doc, `docFrequency` decremented); `update(id, patch)` reindexes only changed field (verify via a term that appears only in the *unchanged* field still matches after update, and old term from changed field no longer matches while new one does); upsert on existing id doesn't duplicate. |
| 6c | Boolean string query (AND/OR/NOT, phrase, field prefix, precedence) | Test: `"a AND b NOT c"` returns docs with a & b, without c. Test explicit precedence case combining AND/OR/NOT in one string. Test quoted phrase inside boolean string. Test `field:term` prefix restricts to a field. |
| 6d | Structured query object forms | One test per variant: `{term}`, `{phrase, slop}`, `{prefix}`, `{fuzzy, maxEdits}`, `{and}`, `{or}`, `{not}`, including nested composition. |
| 6e | Search options | Test `limit`/`offset` paging; `filter` excludes docs post-rank; `boostFields` override changes ranking order; `snippet` option returns `<mark>` around match, and doc with snippet field not containing any match term returns without throwing (snippet omitted or empty per implementation contract documented in README). |
| 7 | BM25 ranking correct, phrase proximity, field boosts, stable sort | Test: two docs, term in title vs. body, title boost > body boost → title-match doc ranks first. Test phrase query proximity: closer terms score higher than farther (same terms, different gap) when combined with OR fallback scoring. Test tie-break: equal score → ascending id order. |
| 8 | Iteration / introspection | Test `docs()` yields all live docs (not removed ones), `terms()` yields unique term set, `docFrequency(term)` matches manual count. |
| 9 | Serialization round-trip | Test: `fromJSON(index.toJSON())` search results equal original index's search results for several queries; confirms state (postings, doc store, corpus stats) is fully captured, not just doc list. |
| 10 | Unicode tokenizer default | Test: `café`/`naïve`/`搜索`/`بحث` are tokenized as words with `\p{L}\p{N}`, matched case-insensitively (`café` vs `CAFÉ`), and combining-character variant of `café` (e + combining acute) matches precomposed `café`. |
| 11 | No global state | Test: two `SearchIndex` instances, add different docs to each, assert cross-contamination does not occur (index A's `size`/`terms` unaffected by index B's adds). |
| 12 | Determinism | Test: run same query twice on same index → identical result array (deep equal), including snippet text. |
| 13 | Edge cases (TASK.md list) | One test per bullet: empty index search returns `[]`; empty/whitespace query returns `[]` (not throw); 100 KB body doc indexes and is searchable within reasonable time; upsert by existing id; remove mid-session (search before/after remove differ correctly); all-stopword query returns `[]` without throwing; phrase with non-adjacent terms doesn't match at slop 0; fuzzy edit distance exactly equal to word length is evaluated correctly (boundary, not off-by-one); deeply nested boolean AND/OR/NOT; boost referencing nonexistent field doesn't throw; snippet requested on field without a match doesn't throw. |
| 14 | Required minimum tests present (TASK.md list) | Manual checklist cross-reference during review: BM25 sanity, phrase exact/non-adjacent, fuzzy colour/color, boolean `a AND b NOT c`, unicode café/CAFÉ, remove cleans postings, serialization round trip, snippet highlight, update reindexes only patched field — each has a corresponding `test()`/`it()` block. |
| 15 | Quality-loop artifacts present | `ls .quality-loop/` contains all 7 required files, each non-empty and reflecting actual decisions (not boilerplate placeholders). |

## Regression risks
- Changing tokenizer defaults after tests are written could silently break
  unrelated tests (tokenizer is shared infra) — tokenizer tests added early
  and re-run after any later tokenizer edit.
- Postings cleanup on `remove`/`update` is the highest-risk correctness area
  for silent data leaks (memory growth, wrong `docFrequency`) — must be
  covered by an explicit orphan-check test, not inferred from `has()` alone.
- Benchmark performance depends on postings-based lookups; a regression to
  linear doc scans would still pass tests but silently blow the benchmark's
  practical runtime — bench itself is the guard here (it must complete in a
  reasonable time, checked qualitatively during VERIFY).

## Evidence required at VERIFY
- Full terminal output (or captured log) of: `npm install`, `npm run build`,
  `npm test`, `node dist/bench/bench.js`.
- `execution-log.md` recording each slice and its local verification.
- Final `completion-record.md` citing all of the above.
