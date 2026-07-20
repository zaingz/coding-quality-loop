# Context Map

## Starting state
Working directory is a **greenfield** package (no existing `src/`, no git
history to inherit conventions from). Present before this task: `.claude/`
(quality-loop skill installation), `assets/`, `hosts/`, `scripts/` (harness
scaffolding for the eval, not library code — not touched by this task).
No existing `package.json`, `tsconfig.json`, or source files.

## Entry points (to be created)
- `src/index.ts` — public API barrel export (the only import surface
  external consumers use).
- `bench/bench.ts` — standalone benchmark entry point (not part of the
  public API, run directly via compiled JS).

## Affected surfaces
- **New package manifest**: `package.json` (name `@eval/minisearch`,
  `type: module`, `engines.node >= 18`, zero runtime deps).
- **New TS config**: `tsconfig.json`, strict mode, target that supports
  Node 20 (ES2022), module `NodeNext` for ESM + `node --test` compatibility.
- **New library modules** under `src/`:
  - `tokenizer.ts` — unicode-aware default tokenizer + stopword sets.
  - `bm25.ts` — BM25 scoring math.
  - `levenshtein.ts` — edit-distance function for fuzzy matching.
  - `queryParser.ts` — string query → structured `Query` AST (boolean
    precedence NOT > AND > OR, quoted phrases, `field:term` prefix).
  - `queryEngine.ts` — structured `Query` AST → postings-based match/score.
  - `snippet.ts` — snippet extraction + `<mark>` highlighting.
  - `types.ts` — shared public types (`Query`, `SearchResult`, options).
  - `SearchIndex.ts` — the class tying tokenizer + postings + query engine
    + serialization together; the main stateful object.
  - `index.ts` — re-exports.
- **Tests** under `test/*.test.ts`, one file per concern area (index CRUD,
  query parsing, ranking/BM25, phrase/proximity, fuzzy, unicode, snippet,
  serialization) to keep diffs/readability manageable and mirror "Tests you
  must include" in TASK.md.
- **Benchmark**: `bench/words.ts` (fixed vocabulary), `bench/rng.ts`
  (Mulberry32 seeded PRNG), `bench/bench.ts` (corpus gen + workload + JSON
  report).
- **README.md** — usage + API docs with code examples, each covering one
  documented feature (construction, mutation, query forms, serialization).

## Existing patterns to reuse
None — greenfield. Will establish internal conventions once during
IMPLEMENT and hold them consistent (one class/concern per file, named
exports, no default exports, no barrel re-export cycles).

## Data flow (target)
```
raw doc --add()--> per-field tokenize (unicode regex + stopwords + stemmer)
                 --> term positions recorded per (docId, field)
                 --> inverted index: term -> field -> docId -> positions[]
                 --> per-field doc length + corpus stats (df, avg field len)

query string --parse()--> Query AST --queryEngine--> candidate doc set
                 (term/prefix/fuzzy lookups against inverted index;
                  phrase/AND/OR/NOT combine candidate sets)
             --> BM25 score per field * field boost, summed
             --> phrase queries add proximity bonus from position gaps
             --> sort by score desc, id asc --> filter --> offset/limit
             --> optional snippet extraction from raw stored field text
```

## Risks identified
- **Unicode correctness**: `\p{L}\p{N}` with the `u` regex flag, combining
  character normalization (NFC) needed so `café` (precomposed vs. combining
  acute) match consistently — mitigate with `.normalize('NFC')` before
  tokenizing/matching.
- **Orphaned postings on remove/update**: must delete empty term/field/doc
  entries all the way up the structure, not just doc metadata, or
  `terms()`/`docFrequency()` will report stale data — dedicated test.
- **Phrase slop correctness**: "quick red brown fox" must NOT match phrase
  `"quick brown"` at slop 0 — position-gap check must be exact.
- **Fuzzy edit distance == word length**: classic off-by-one risk in
  Levenshtein early-exit optimizations — must not special-case incorrectly.
- **BM25 tie-breaking**: needs stable sort by (score desc, id asc), JS
  `Array.prototype.sort` is stable in Node ≥ 12 so a single comparator
  suffices.
- **Node version mismatch**: task assumes Node ≥22.6 for
  `--experimental-strip-types`; sandbox has Node 20.20.1 — must compile
  bench/tests instead, per the task's own documented fallback.
- **Performance for 10k-doc benchmark**: naive O(n) doc scans per query
  would be too slow / not representative; must query via inverted index
  postings, not linear scans over all docs.

## Verification commands anticipated
- `npm install`
- `npm run build` (tsc)
- `npm test` (node --test against compiled dist/test)
- `node dist/bench/bench.js`
