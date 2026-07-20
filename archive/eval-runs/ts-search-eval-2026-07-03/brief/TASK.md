# Task: In-memory full-text search library (TypeScript)

Build a production-quality, in-memory full-text search library in TypeScript. This is a real library — API surface matters, edge cases matter, performance matters. Treat it as if it were shipping to npm.

## Deliverables

A single TypeScript package rooted at the repository root of your working directory:

- `package.json` — private, name `@eval/minisearch`, `"type": "module"`, Node ≥18
- `tsconfig.json` — strict TypeScript
- `src/` — library source
- `test/` — tests (Node's built-in test runner `node --test` — DO NOT add jest/vitest/mocha)
- `bench/` — a runnable benchmark harness (see below)
- `README.md` — API docs with examples

## Required functionality

### 1. Index construction

```ts
const index = new SearchIndex<Doc>({
  fields: { title: { boost: 3 }, body: { boost: 1 }, tags: { boost: 2 } },
  tokenizer?: (text: string) => string[],           // default: unicode-aware word split, lowercased
  stopwords?: Set<string> | 'english' | 'none',     // default: 'english'
  stemmer?: (token: string) => string,              // default: identity
  idField?: keyof Doc,                              // default: 'id'
});
```

- Documents are plain objects. The generic parameter `Doc` types them.
- Fields are strings, string arrays (for tags), or numbers coerced to strings.
- The index must be schema-safe: adding a doc missing a declared field is fine (empty), adding a doc with an undeclared field is silently ignored.

### 2. Mutations

- `index.add(doc)` — add or replace by id. O(fields·tokens) time.
- `index.addAll(docs[])` — batch add.
- `index.remove(id)` — delete by id. Must not leave orphaned postings.
- `index.update(id, patch)` — partial field update; only reindex changed fields.
- `index.size` — number of live docs.
- `index.has(id)` — presence check.

### 3. Query API

```ts
const results: SearchResult<Doc>[] = index.search(query, options?);
```

Where `query` is:
- **String**: parsed for boolean operators `AND`, `OR`, `NOT`, quoted `"exact phrase"`, and field prefix `title:foo`. Default operator: OR. Precedence: NOT > AND > OR.
- **Object**: a structured query — one of:
  - `{ term: string, field?: string }`
  - `{ phrase: string, field?: string, slop?: number }` (slop default 0 = exact)
  - `{ prefix: string, field?: string }` (prefix match)
  - `{ fuzzy: string, field?: string, maxEdits?: 1|2 }` (Levenshtein edit distance ≤ maxEdits)
  - `{ and: Query[] }` / `{ or: Query[] }` / `{ not: Query }`

Options:
- `limit` (default 10), `offset` (default 0)
- `filter?: (doc: Doc) => boolean` — post-filter after ranking
- `boostFields?: Record<string, number>` — per-query field boost override
- `snippet?: { field: string, length: number }` — return a snippet with `<mark>...</mark>` around matched terms

Result shape:
```ts
type SearchResult<Doc> = {
  id: string;
  doc: Doc;
  score: number;
  matched: { field: string; terms: string[] }[];
  snippet?: string;
};
```

### 4. Ranking

- Use **BM25** (k1=1.2, b=0.75, tuneable via constructor). Not raw TF-IDF.
- Phrase queries score by proximity — closer term positions rank higher.
- Field boosts multiply the per-field contribution.
- Return results sorted by score descending, then by id ascending for stability.

### 5. Iteration / introspection

- `index.docs()` — iterable of `{id, doc}`.
- `index.terms()` — iterable of unique terms in the index.
- `index.docFrequency(term)` — number of docs containing term.

### 6. Serialization

- `index.toJSON()` returns a plain-JSON snapshot.
- `SearchIndex.fromJSON<Doc>(snapshot, options?)` restores an index. Custom tokenizer/stemmer/stopwords must be re-supplied by the caller — the snapshot only serializes state, not functions.

## Constraints

- **Zero runtime dependencies** (`dependencies: {}` in `package.json`). Dev deps (typescript, @types/node) are fine.
- **`"strict": true`** in tsconfig. No `any`, no `@ts-ignore`, no `// @ts-expect-error` unless justified in a comment.
- **No unsafe casts through `unknown`** to escape the type system.
- Public API surface must be fully typed and exported from `src/index.ts`.
- **Unicode-safe** by default: the default tokenizer must handle non-ASCII words (`café`, `naïve`, Chinese `搜索`, Arabic `بحث`). Use `\p{L}\p{N}` regex, not `\w`.
- **No global state.** Two `SearchIndex` instances must not interfere.
- **Deterministic**: same input → same output, including score ties broken by id.

## Edge cases the tests will exercise

- Empty index, empty query, whitespace-only query.
- Documents with missing/undefined fields.
- Extremely long documents (100 KB body).
- Adding a doc with an existing id (upsert).
- Removing a doc mid-search-session.
- Query with all-stopword terms.
- Phrase query where terms exist but not adjacent.
- Fuzzy query with edit distance == word length.
- Boolean query with deeply nested AND/OR/NOT.
- Field boost with a nonexistent field name.
- Snippet on a field that doesn't contain the match.
- Unicode combining characters.

## Benchmark harness

Create `bench/bench.ts` that:

1. Generates a synthetic corpus of **10,000 documents** using a deterministic seeded RNG (Mulberry32 or similar; seed = 42). Each doc has `id: string`, `title: string` (3-8 words), `body: string` (50-500 words), `tags: string[]` (0-5 tags). Vocabulary drawn from a fixed word list (bench/words.ts — you generate this from a deterministic method).
2. Indexes them all, then runs a fixed workload:
   - 1000 single-term queries
   - 500 two-term OR queries
   - 500 two-term AND queries
   - 200 phrase queries
   - 100 fuzzy queries (edit distance 1)
3. Prints a JSON summary:
```json
{
  "index_build_ms": N,
  "index_size_docs": 10000,
  "index_memory_estimate_kb": N,
  "queries": {
    "single_term": {"count": 1000, "total_ms": N, "p50_us": N, "p99_us": N},
    "or_two": {...},
    "and_two": {...},
    "phrase": {...},
    "fuzzy_edit1": {...}
  }
}
```

Runnable as `node --experimental-strip-types bench/bench.ts` (Node 22.6+ can strip TS types natively; if your Node is older, compile to `dist/bench.js` first with `npm run build && node dist/bench.js`).

## Acceptance checks

- `npm run build` (or `npx tsc`) succeeds with zero errors under `strict: true`.
- `npm test` (or `node --test test/**/*.test.ts` after compile) passes.
- The benchmark runs to completion and prints a valid JSON summary.
- Zero runtime dependencies verified: `Object.keys(require('./package.json').dependencies || {}).length === 0`.

## Tests you must include (minimum)

- BM25 ranking sanity: two docs with matching title vs body — title match ranks higher when boost is set.
- Phrase query: doc with "quick brown fox" matches `"quick brown"`; doc with "quick red brown fox" does not (slop 0).
- Fuzzy: "colour" query with maxEdits 1 matches "color".
- Boolean: `"a AND b NOT c"` returns docs with both a and b and without c.
- Unicode: doc with "café" is found by query "café" and (case-insensitive) "CAFÉ".
- Remove: doc is gone after `remove(id)`; term postings for orphaned terms are cleaned.
- Serialization roundtrip: `fromJSON(toJSON())` gives an equivalent index.
- Snippet: returns a highlighted excerpt around the match.
- Update: `update(id, {body: 'new'})` reindexes only the body field.

## How to work

Write the code as you would for a normal team code review. You have full shell access. Node 20 is pre-installed. `npm install` is available but you should have **zero runtime deps**. Install `typescript` and `@types/node` as dev deps. Do not install any other dev tooling (no jest/vitest/eslint/prettier). Do not commit `node_modules/` or `dist/`. Do not push to any git remote.

When you are done, print a one-paragraph summary and the acceptance-check pass/fail status.
