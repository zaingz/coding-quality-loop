# Execution Log

Each entry records the slice, files touched, local verification run, and
result. Slices were implemented in the order below; later slices
occasionally required small revisits to earlier files (noted inline).

## Slice 1: Scaffold
- Files: `package.json`, `tsconfig.json`, `src/`, `test/`, `bench/` directory
  skeleton.
- Verify: `npm install` (0 vulnerabilities, only `typescript` + `@types/node`
  devDependencies installed); `npx tsc --noEmit` on an empty `src/index.ts`
  stub.
- Status: **done**.

## Slice 2: Types + Tokenizer
- Files: `src/types.ts` (public option/query/result interfaces),
  `src/tokenizer.ts` (default unicode tokenizer using `\p{L}\p{N}` Unicode
  property escapes, NFC normalization, lowercasing, ~30-word English
  stopword list), `test/tokenizer.test.ts`.
- Verify: `npx tsc --noEmit` clean; `node --test dist/test/tokenizer.test.js`
  green (5 tests: ascii, unicode letters incl. café/naïve/搜索/بحث, combining
  vs. precomposed normalization, stopword removal, custom tokenizer
  override).
- Status: **done**.

## Slice 3: Postings store (inverted index)
- Files: `src/postings.ts` — per-field postings (`term -> docId -> positions[]`),
  document-frequency tracking, field-length tracking for BM25, `restorePosting`
  / `restoreFieldLength` for deserialization.
- Verify: exercised indirectly via `test/crud.test.ts` (add/remove/update
  orphan checks) once `SearchIndex` slice landed; `npx tsc --noEmit` clean at
  each step.
- Status: **done**. **Bug fixed during VERIFY** (see Decision #12 in
  `decision-log.md`): `clearField` was originally implemented as an
  O(total-vocabulary) scan on every `indexField` call (iterating every term
  in the store to find postings belonging to the doc/field being
  re-indexed). This made `update()` and re-indexing pathologically slow and
  was the dominant cost in the benchmark's index-build time. Fixed by adding
  a reverse index `docFieldTerms: field -> docId -> Set<term>` so
  `clearField` only touches terms actually used by that specific
  `(docId, field)` pair. This dropped benchmark index-build time from ~5.9s
  to ~4.4-4.7s and single-term query p50 from several milliseconds to
  ~1.2ms, since stale/duplicate postings were no longer accumulating.

## Slice 4: Levenshtein + BM25
- Files: `src/levenshtein.ts` (bounded edit-distance with early exit at
  `maxEdits`), `src/bm25.ts` (BM25 term-frequency/IDF scoring with
  configurable `k1`/`b`, per-field boost multipliers, phrase proximity bonus
  formula documented in `decision-log.md` Decision #4).
- Verify: `test/ranking.test.ts` (11 tests: title vs. body boost ordering,
  phrase proximity ordering, tie-break by ascending id, `docFrequency`
  correctness, corpus statistics); `test/fuzzy.test.ts` (4 tests: colour/color
  edit-1 match, edit-distance boundary exactly equal to word length,
  maxEdits respected, no match beyond maxEdits).
- Status: **done**.

## Slice 5: Query parser
- Files: `src/queryParser.ts` — recursive-descent parser for the string
  query grammar (implicit OR, explicit `AND`/`OR`/`NOT`, quoted phrases,
  `field:term` prefix, parenthesized grouping, precedence `NOT > AND > OR`).
- Verify: `test/query-parser.test.ts` (13 tests covering boolean combinations,
  phrase-in-boolean, field prefix, explicit precedence, nested parens, deeply
  nested AND/OR/NOT).
- Status: **done**. **Two bugs found and fixed during VERIFY** (Decisions #9
  and companion fix in `decision-log.md`):
  1. A bare `NOT c` following an `AND` chain (`"a AND b NOT c"`, TASK.md's
     own worked example) was being dropped because `parseAnd` did not
     recognize a trailing `NOT` atom as continuing the same conjunctive
     clause. Fixed so `NOT` after `AND` extends the current AND clause
     rather than falling through to the outer OR level.
  2. Implicit OR between adjacent atoms (e.g. two bare terms/phrases placed
     side by side with no operator) was not being parsed as OR in every
     position — `parseOr` only continued when it saw an explicit `OR`
     token. Fixed to also continue parsing when the next token is
     `WORD`/`PHRASE`/`LPAREN`, per the "default operator is OR" rule in
     TASK.md.

## Slice 6: Query engine + SearchIndex
- Files: `src/queryEngine.ts` (evaluates the parsed/structured `Query` AST
  against the postings store: term/phrase/prefix/fuzzy leaves, and/or/not
  combinators, with NOT handled as set subtraction inside an AND context),
  `src/SearchIndex.ts` (public class: constructor options, `add`/`addAll`/
  `remove`/`update`/`size`/`has`, `search` accepting string or structured
  `Query`, `limit`/`offset`/`filter`/`boostFields`/`snippet` search options,
  `docs()`/`terms()`/`docFrequency()`, `toJSON()`/`fromJSON()`).
- Verify: `test/crud.test.ts` (10 tests: add/has/size, remove cleans up
  postings and `docFrequency`, update reindexes only the changed field and
  leaves unchanged-field terms matching, upsert on existing id does not
  duplicate, schema-safety for missing/undeclared fields, custom `idField`),
  `test/edge-cases.test.ts` (8 tests: empty index, empty/whitespace query,
  large 100 KB doc, all-stopword query, phrase at slop 0 with non-adjacent
  terms, boost referencing nonexistent field, snippet on non-matching field,
  no cross-instance global-state leakage between two `SearchIndex`
  instances).
- Status: **done**. **Bug found and fixed during VERIFY** (Decision #11):
  `SearchIndex.search` had an overly aggressive post-rank filter that
  dropped any result with `score <= 0 && matchedByField.size === 0`. This
  silently discarded legitimate `NOT`-only-influenced matches (a doc that
  matches because it lacks an excluded term can legitimately have zero
  positive-match score contribution from the "matched" side of the query).
  Removed the filter; correctness now relies solely on the query engine's
  own doc-set evaluation, not a secondary heuristic filter.

## Slice 7: Snippets
- Files: `src/snippet.ts` — builds `<mark>`-wrapped snippets from the raw
  (untokenized) field text, locating match spans by tokenizing text and
  mapping token offsets back to raw character ranges.
- Verify: `test/snippet.test.ts` (2 tests: snippet wraps matched term in
  `<mark>`, snippet omitted/empty without throwing when the snippet field
  contains no match).
- Status: **done**.

## Slice 8: Serialization
- Files: additions to `src/postings.ts` / `src/SearchIndex.ts` for
  `toJSON()`/`fromJSON()` covering postings, per-doc field lengths, corpus
  statistics (avg field length, doc count), and the live document store.
- Verify: `test/serialization.test.ts` (4 tests: round-trip search results
  identical to original index across multiple query types, including
  fuzzy and phrase queries which depend on positional/corpus data being
  fully restored, not just the doc list).
- Status: **done**.

## Slice 9: Barrel export + README
- Files: `src/index.ts` (public API barrel export), `README.md` (API
  reference, design notes incl. phrase-proximity formula and BM25
  parameters, zero-runtime-deps statement, documented unicode/CJK
  segmentation limitation).
- Verify: `npx tsc --noEmit` clean; manual read-through of README against
  actual exported API surface.
- Status: **done**.

## Slice 10: Benchmark
- Files: `bench/rng.ts` (Mulberry32 deterministic PRNG, seed 42),
  `bench/words.ts` (20,000-word deterministic vocabulary, generated via
  nested syllable-combination loops — no dependency on an external word
  list), `bench/bench.ts` (builds a 10,000-doc corpus, runs the fixed
  1000/500/500/200/100 query workload across single-term/or-two/and-two/
  phrase/fuzzy-edit1 categories, prints the required JSON shape).
- Verify: `node dist/bench/bench.js` runs to completion and prints
  `JSON.parse`-able output matching the required top-level keys.
- Status: **done**. Vocabulary was enlarged from an initial ~800 words to
  20,000 during VERIFY (Decision #13) because the small vocabulary produced
  unrealistically high per-term document frequency (every query touched a
  large fraction of the corpus), which both masked the postings-store
  performance bug in Slice 3 and produced misleadingly slow/uninformative
  per-query timings. The larger vocabulary is still fully deterministic
  (seeded PRNG, no external data), and dropped per-query p50/p99 latencies
  by roughly an order of magnitude once combined with the Slice-3 fix.

## Slice 11: Full VERIFY pass (clean-room)
- Actions: `rm -rf node_modules dist package-lock.json`; `npm install`;
  `npm run build`; `npm test`; `npm run bench`; confirmed zero runtime deps
  via `node -e "console.log(Object.keys(require('./package.json').dependencies||{}).length)"`
  → `0`; confirmed no unsafe casts via
  `grep -rn "as unknown as" src/ test/ bench/` → no matches; confirmed no
  git repository exists (no risk of accidental commit/push of
  `node_modules`/`dist`).
- Result: `npm install` — 0 vulnerabilities, 3 packages added. `npm run
  build` — exit 0, no errors. `npm test` — 62/62 pass, 0 fail, 0 skipped.
  `npm run bench` — valid JSON printed, matches required shape (see
  `.quality-loop/bench-output.json` for the final captured run).
- Status: **done**.

## Slice 12: Final test cleanup
- Files: `test/crud.test.ts` — replaced the one remaining `as unknown as`
  cast (previously used to attach an extra field to an already-constructed
  `SearchIndex<Doc>` instance for the "undeclared field ignored" test) with
  a properly-typed `new SearchIndex<ExtendedDoc>(...)` construction, so the
  test exercises the same behavior without any unsafe cast anywhere in the
  codebase.
- Verify: `npx tsc -p tsconfig.json` clean; `npm test` → 62/62 still pass
  (unaffected behavior, test-only change); `grep -rn "as unknown as" test/
  src/ bench/` → no matches.
- Status: **done**.

## Summary
All 12 slices complete. Final clean-room verification (Slice 11, re-run
after Slice 12) passed every acceptance criterion. See
`.quality-loop/completion-record.md` for the consolidated evidence and
`.quality-loop/validation-contract.md` for the row-by-row acceptance
mapping.
