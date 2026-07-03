# Plan

## Complexity brake (pre-implementation)

Rung ladder applied:
1. No change needed — N/A, this is a net-new library requested by the task.
2. Delete/simplify existing code — N/A, greenfield.
3. Reuse existing function/component/pattern/config — nothing exists to reuse.
4. Standard library behavior — **used wherever possible**: `Intl`/regex
   unicode property escapes (`\p{L}\p{N}`) for tokenization instead of a
   unicode-segmentation package; `String.prototype.normalize('NFC')` for
   combining characters instead of a normalization library; native
   `Array.sort` (stable) for result ordering; native `JSON` for
   serialization; Node's built-in `node:test` and `node:assert` for tests
   instead of a test framework; Node's `perf_hooks.performance.now()` for
   benchmark timing instead of a benchmarking library.
5. Native platform behavior — covered above (regex `u` flag, `Intl` not
   even needed once `\p{L}\p{N}` + NFC normalize covers the required
   unicode cases).
6. Already-installed dependency — none installed; zero-runtime-dep
   constraint forbids adding any. Dev deps limited to `typescript` +
   `@types/node`, both explicitly pre-approved by the task brief.
7. One-liner / localized patch — not applicable at this scope (net-new
   library).
8. Minimal new code — **selected rung.** BM25, the boolean query parser,
   phrase-proximity scoring, Levenshtein fuzzy matching, and the unicode
   tokenizer are all algorithms with no acceptable stdlib/native
   equivalent under a zero-runtime-dependency constraint, so they must be
   hand-implemented. Justification per component:
   - **BM25**: no built-in ranking function in Node/JS stdlib.
   - **Boolean query parser**: no built-in query-language parser; a
     hand-rolled recursive-descent parser is smaller and more auditable
     than pulling in a parser-generator, and the grammar is small (3
     binary/unary operators + quotes + field prefix).
   - **Levenshtein**: no built-in edit-distance function; classic O(n·m)
     DP table is the minimal correct implementation, iterative not
     recursive to avoid stack/perf issues on long tokens.
   - **Unicode tokenizer**: covered by native regex unicode property
     escapes + `normalize('NFC')` — this *is* the "native platform
     behavior" rung, no separate segmentation library needed.
   - **Snippet/highlight**: simple substring/index math, no library needed.
   - **Inverted index / postings**: plain `Map`/`Set` structures, the
     standard data structure for this problem, no library needed.
   No framework, queue, cache, background job, external service, or
   database is introduced. Total new source surface is kept to one
   module per concern (see file list below) rather than one monolithic
   file, to keep each diff/review unit small — this is a readability
   minimality trade-off, not a complexity increase.

## Files/modules to create

```
package.json
tsconfig.json
README.md
src/
  types.ts            # public types: Query, SearchOptions, SearchResult, FieldConfig, IndexOptions, JSON snapshot shape
  tokenizer.ts         # default unicode tokenizer, stopword sets (english/none/custom), normalize
  levenshtein.ts        # edit distance function, boundable by maxEdits for early exit
  bm25.ts               # BM25 term-weight + score accumulation helpers
  queryParser.ts        # string -> Query AST (recursive descent, precedence NOT>AND>OR, quotes, field:term)
  postings.ts           # inverted index data structure: term -> field -> docId -> positions[]; df/field-length tracking
  queryEngine.ts        # Query AST -> matched doc set + per-field per-term contributions (term/phrase/prefix/fuzzy/and/or/not)
  snippet.ts            # snippet extraction + <mark> highlighting from raw field text
  SearchIndex.ts         # main class: constructor, add/addAll/remove/update/size/has, search, docs/terms/docFrequency, toJSON/fromJSON
  index.ts              # barrel: re-export public surface
test/
  tokenizer.test.ts
  crud.test.ts
  query-parser.test.ts
  ranking.test.ts
  fuzzy.test.ts
  unicode.test.ts
  serialization.test.ts
  snippet.test.ts
  edge-cases.test.ts
bench/
  rng.ts                 # Mulberry32 seeded PRNG
  words.ts                # fixed deterministic vocabulary
  bench.ts                # corpus gen + workload + JSON report
.quality-loop/            # process artifacts (this plan + siblings)
```

## Implementation slices (in order)

1. **Scaffold** — `package.json`, `tsconfig.json`, directory skeleton.
   Verify: `npm install` succeeds, `npx tsc --noEmit` on an empty `src/index.ts`.
2. **Types + tokenizer** — `types.ts`, `tokenizer.ts` (unicode regex,
   NFC normalize, stopword sets). Verify: unit test for tokenizer alone.
3. **Postings/inverted index core** — `postings.ts` with add/remove/update
   at the term-position level, doc-length tracking, corpus stats (df,
   avg field length, doc count) needed for BM25. Verify: CRUD test
   (add/remove/update/orphan-cleanup) against postings directly.
4. **BM25 + Levenshtein** — pure functions, independently testable.
   Verify: unit tests with hand-computed expected values.
5. **Query parser** — string → AST, recursive descent with precedence.
   Verify: parser unit tests (operator precedence, quotes, field prefix,
   nested parens if supported — spec doesn't require parens explicitly;
   support them anyway since NOT/AND/OR nesting needs *some* grouping
   mechanism for "deeply nested" edge case, and parens are the standard
   minimal mechanism).
6. **Query engine** — AST → doc matches + scores using postings + BM25 +
   Levenshtein + phrase proximity. Verify: ranking/phrase/fuzzy/boolean
   tests.
7. **Snippet module** — extraction from raw text + `<mark>` wrapping.
   Verify: snippet tests including no-match-in-field case.
8. **SearchIndex class** — wires everything, implements full public API
   incl. serialization (`toJSON`/`fromJSON`), `docs()/terms()/docFrequency()`.
   Verify: full integration tests, serialization round-trip, unicode,
   edge cases.
9. **index.ts barrel + README** — export surface + docs with examples.
   Verify: `npm run build` clean, no `any`.
10. **Benchmark** — `bench/rng.ts`, `bench/words.ts`, `bench/bench.ts`.
    Verify: compiled and run, JSON output validated structurally.
11. **Full verification pass** — `npm install && npm run build && npm test`
    + benchmark run; fix any failures; re-run until green.
12. **Independent review** — fresh read of the diff against
    `validation-contract.md`; log findings in `decision-log.md` and fix
    before completion record.

## Verification commands
```
npm install
npm run build
npm test
node dist/bench/bench.js
```

## Risks
- Node 20 vs. the task's Node 22.6 assumption for `--experimental-strip-types`
  — mitigated by compiling everything (build step already required anyway).
- Recursive-descent parser edge cases (empty query, all-stopwords, unmatched
  quotes) — covered by dedicated edge-case tests.
- Phrase proximity scoring formula is not fully pinned by the spec beyond
  "closer term positions rank higher" — implemented as an inverse-distance
  bonus added to the BM25 phrase-term score; documented in README and
  decision-log as a deliberate, disclosed design choice.

## Non-goals (restated)
Stemming beyond identity default, persistence, HTTP/CLI layer, linting.

## Rollback path
Net-new files only; rollback = delete the created files/directories. No
existing code is modified, so rollback carries no risk to any pre-existing
system.
