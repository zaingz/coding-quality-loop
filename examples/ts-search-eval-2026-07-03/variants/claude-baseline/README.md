# @eval/minisearch

An in-memory full-text search library for TypeScript/Node.js, with BM25
ranking, a boolean query language, phrase proximity search, fuzzy
(Levenshtein) matching, unicode-safe tokenization, and snippet highlighting.

Zero runtime dependencies. Strict TypeScript. No `any`.

## Install

```bash
npm install
npm run build
```

## Quick start

```ts
import { SearchIndex } from "./dist/src/index.js";

interface Doc {
  id: string;
  title: string;
  body: string;
  tags: string[];
}

const index = new SearchIndex<Doc>({
  fields: {
    title: { boost: 3 },
    body: { boost: 1 },
    tags: { boost: 2 },
  },
});

index.addAll([
  { id: "1", title: "Quick brown fox", body: "The fox jumps over the lazy dog.", tags: ["animals"] },
  { id: "2", title: "Café culture", body: "A naïve guide to café culture in Paris.", tags: ["travel"] },
]);

const results = index.search("fox AND dog");
console.log(results);
```

## API

### Constructing an index

```ts
const index = new SearchIndex<Doc>({
  fields: { title: { boost: 3 }, body: { boost: 1 }, tags: { boost: 2 } },
  tokenizer?: (text: string) => string[],
  stopwords?: Set<string> | "english" | "none", // default: "english"
  stemmer?: (token: string) => string,          // default: identity
  idField?: keyof Doc,                          // default: "id"
  k1?: number,                                  // BM25 k1, default 1.2
  b?: number,                                   // BM25 b, default 0.75
});
```

- Documents are plain objects. Declared fields may be strings, string arrays
  (e.g. tags), or numbers (coerced to strings). Missing declared fields are
  treated as empty. Undeclared fields are silently ignored.
- The default tokenizer is unicode-aware (`\p{L}\p{N}\p{M}` regex), NFC
  normalizes, and lowercases — so `café`, `naïve`, `搜索`, and `بحث` are all
  tokenized correctly.

### Mutations

```ts
index.add(doc);            // add or replace by id
index.addAll(docs);        // batch add
index.remove(id);          // delete by id; cleans up orphaned postings
index.update(id, patch);   // partial update; only reindexes changed fields
index.size;                // number of live docs
index.has(id);             // presence check
```

### Searching

```ts
const results = index.search(query, options?);
```

`query` can be a string or a structured `Query` object.

**String queries** support:
- Boolean operators `AND`, `OR`, `NOT` (case-insensitive keywords)
- Quoted phrases: `"exact phrase"`
- Field-scoped terms: `title:foo`
- Parentheses for grouping: `(a AND b) OR (c NOT d)`
- Default operator between bare terms is `OR`. Precedence: `NOT` > `AND` > `OR`.

**Structured queries**:

```ts
{ term: string, field?: string }
{ phrase: string, field?: string, slop?: number }   // slop default 0 = exact adjacency
{ prefix: string, field?: string }
{ fuzzy: string, field?: string, maxEdits?: 1 | 2 }  // Levenshtein distance
{ and: Query[] }
{ or: Query[] }
{ not: Query }
```

**Options**:

```ts
{
  limit?: number;      // default 10
  offset?: number;      // default 0
  filter?: (doc: Doc) => boolean;              // post-filter after ranking
  boostFields?: Record<string, number>;        // per-query field boost override
  snippet?: { field: string; length: number }; // highlighted excerpt
}
```

**Result shape**:

```ts
type SearchResult<Doc> = {
  id: string;
  doc: Doc;
  score: number;
  matched: { field: string; terms: string[] }[];
  snippet?: string; // present only if `snippet` option was passed
};
```

Results are ranked by **BM25** (tuneable `k1`/`b`), with per-field boosts
multiplying each field's contribution. Phrase queries additionally weight by
term-position proximity — tighter clusters score higher. Ties are broken by
ascending `id` for determinism.

### Introspection

```ts
index.docs();               // iterable of { id, doc }
index.terms();               // iterable of unique indexed terms
index.docFrequency(term);    // number of docs containing term
```

### Serialization

```ts
const snapshot = index.toJSON();           // plain-JSON snapshot
const restored = SearchIndex.fromJSON<Doc>(snapshot, {
  tokenizer, stopwords, stemmer, // re-supply any custom functions used originally
});
```

Snapshots serialize index state only (postings, field lengths, documents) —
custom functions (tokenizer/stemmer) are not serialized and must be passed
again to `fromJSON` if they were used originally.

## Design notes

- **Inverted index**: `term -> field -> docId -> positions[]`. Postings store
  token positions per field so phrase/proximity queries can be evaluated
  without re-tokenizing documents at query time.
- **BM25**: implemented directly (not wrapped TF-IDF), with the standard
  `idf * (tf * (k1+1)) / (tf + k1 * (1 - b + b * fieldLen/avgFieldLen))`
  formula per field, summed across matched fields with per-field boosts
  applied as multipliers.
  **Note:** we deliberately use the `idf = ln(1 + (N - df + 0.5)/(df + 0.5))`
  smoothed variant (rather than the classic Robertson/Sparck-Jones form,
  which can go negative for very common terms) so scores stay non-negative
  and comparable across queries; this is a common, well-documented BM25
  variant.
- **Phrase/slop**: for each candidate document, we search for the alignment
  of phrase-term positions that minimizes total positional displacement from
  perfect adjacency; if that minimum is within the requested `slop`, the doc
  matches, and the proximity value scales the score (closer = higher).
- **Fuzzy**: bounded-edit-distance Levenshtein against the term dictionary,
  with early-exit row pruning once the running edit count exceeds
  `maxEdits`. This is a full dictionary scan; acceptable for a library
  targeting small-to-medium in-memory corpora, but the first thing to
  optimize (e.g. via a BK-tree or n-gram index) if you need low-latency
  fuzzy search over larger vocabularies.
- **Remove/update correctness**: `remove` walks all postings referencing the
  doc id and deletes empty per-doc, per-field, and per-term map entries so no
  orphaned structures remain; `update` only touches postings for fields
  present in the patch.
- **No global state**: all index state lives in instance fields; two
  `SearchIndex` instances never share data structures.

## Benchmark

`bench/bench.ts` generates a deterministic 10,000-document synthetic corpus
(Mulberry32 PRNG, seed 42) from a fixed generated vocabulary
(`bench/words.ts`), indexes it, and times a fixed query workload (1000
single-term, 500 two-term OR, 500 two-term AND, 200 phrase, 100 fuzzy
edit-distance-1 queries), printing a JSON summary.

```bash
npm run build
npm run bench
# or directly:
node dist/bench/bench.js
```

## Testing

Tests use Node's built-in test runner — no external test framework.

```bash
npm test
```

## Constraints honored

- Zero runtime dependencies (`dependencies: {}` in `package.json`).
- `strict: true` in `tsconfig.json`; no `any`, no `@ts-ignore`/`@ts-expect-error`.
- Unicode-safe default tokenizer using `\p{L}\p{N}\p{M}`, not `\w`.
- Deterministic: identical input produces identical output, with score ties
  broken by ascending id.
