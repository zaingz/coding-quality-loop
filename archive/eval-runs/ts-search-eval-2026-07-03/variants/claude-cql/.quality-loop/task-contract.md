# Task Contract

## Goal
Build a production-quality, in-memory full-text search library in TypeScript
(`@eval/minisearch`) with zero runtime dependencies: BM25 ranking, boolean
query parsing (AND/OR/NOT, quoted phrases, field prefixes), structured query
objects (term/phrase/prefix/fuzzy/and/or/not), phrase proximity scoring,
Levenshtein-based fuzzy matching, a unicode-aware tokenizer, snippet
generation with `<mark>` highlighting, JSON serialization round-trip, and a
deterministic benchmark harness over a 10,000-document synthetic corpus.

## Task class
**Medium** (multi-file library, non-trivial ranking/parsing algorithms,
correctness-sensitive edge cases, but single-repo/single-agent, no
cross-service or infra risk).

## Risk tier
**Low-medium.** No user data, no network/auth/payment surface, no
persistence beyond in-memory JS objects and JSON export. Main risks are
correctness bugs in ranking/parsing math and unicode handling, not safety
or security. Treated as medium risk tier for process rigor because of
algorithmic complexity, not because of blast radius.

## Acceptance criteria
1. `npm install` succeeds.
2. `npm run build` (`tsc`) succeeds with zero errors under `strict: true`,
   no `any`, no unsafe casts through `unknown`, no `@ts-ignore`/`@ts-expect-error`.
3. `npm test` runs `node --test` against compiled tests and all pass.
4. Benchmark (`bench/bench.ts`, compiled and run as plain JS since the
   sandbox Node is 20.20.1, not 22.6+) runs to completion and prints valid
   JSON matching the required shape.
5. `dependencies` field in `package.json` is `{}` — zero runtime deps.
6. All required functionality in TASK.md §1-6 implemented and exported from
   `src/index.ts`.
7. All "Tests you must include (minimum)" in TASK.md are present and pass.
8. Quality-loop artifacts exist under `.quality-loop/`.

## Non-goals
- No persistence backend (disk index, SQLite, etc.) — in-memory only.
- No stemming algorithm beyond identity default (caller may supply one).
- No relevance tuning beyond BM25 + phrase proximity + field boosts as specified.
- No CLI, no HTTP server, no bundler config.
- No linting/formatting tooling (explicitly disallowed).

## Constraints
- Zero runtime dependencies; only `typescript` and `@types/node` as dev deps.
- Strict TypeScript, no `any`.
- Node's built-in test runner only (no jest/vitest/mocha/ts-node/tsx).
- Must not commit `node_modules/` or `dist/`, must not push to git.
- Default tokenizer must use `\p{L}\p{N}` unicode property escapes, not `\w`.
- No global state; two `SearchIndex` instances must not interfere.
- Deterministic output; ties broken by ascending id.

## Assumptions (recorded, not asked)
- Node 20.20.1 is the actual runtime (verified via `node --version`), which
  is below the 22.6 threshold for `--experimental-strip-types`. The
  benchmark and tests will therefore be **compiled with tsc** and run as
  `.js` from `dist/`, per the task's own fallback instruction ("if your
  Node is older, compile to `dist/bench.js` first"). `npm test` will run
  compiled test files under `dist/test`.
- "boost" defaults to `1` for any field not given an explicit boost.
- `stopwords: 'english'` uses a small, standard, hardcoded English stopword
  list (not an external dataset) — no runtime dependency permitted.
- `stemmer` default is the identity function, per spec.
- BM25 defaults: `k1 = 1.2`, `b = 0.75`, tuneable via constructor per spec.
- Prefix/fuzzy matching operate on indexed (post-tokenizer/stemmer) tokens.
- Filter (`filter?: (doc: Doc) => boolean`) applies after ranking/sorting,
  before `limit`/`offset` slicing, per spec wording ("post-filter after ranking").
- Snippet extraction operates on the *original* field string (re-derived
  from stored raw field text), not the tokenized form, so punctuation/case
  is preserved in the output; matched-term positions are found via a
  case-insensitive/tokenizer-aware scan of the raw text.
- The benchmark's `bench/words.ts` word list is generated deterministically
  (fixed literal array), not fetched from an external source.
- `index_memory_estimate_kb` is computed via a deterministic heuristic
  (`JSON.stringify(toJSON()).length / 1024`) since Node has no cross-platform
  precise heap-attribution API without deps.

## Escalation conditions (none triggered)
- No credentials, secrets, destructive migrations, payments, or auth
  surfaces are involved. No escalation needed during this task.

## Verification plan
1. `npm install`
2. `npm run build`
3. `npm test`
4. `node dist/bench/bench.js` (compiled benchmark) — print JSON summary.
5. Manual read-through of the diff against `validation-contract.md`.
6. Independent review pass (fresh read of the diff vs. contract, distinct
   from implementation reasoning).
