# @eval/minisearch

A zero-runtime-dependency, in-memory full-text search library for
TypeScript. BM25 ranking, boolean query parsing, phrase proximity, fuzzy
(Levenshtein) matching, unicode-aware tokenization, snippet highlighting,
and JSON serialization — all implemented from scratch (see
[Design notes](#design-notes)).

## Install

```bash
npm install
npm run build
```

No runtime dependencies are installed (`dependencies: {}` in
`package.json`). Dev dependencies are `typescript` and `@types/node` only.

## Quick start

```ts
import { SearchIndex } from "@eval/minisearch";

interface Article {
  id: string;
  title: string;
  body: string;
  tags: string[];
}

const index = new SearchIndex<Article>({
  fields: {
    title: { boost: 3 },
    body: { boost: 1 },
    tags: { boost: 2 },
  },
});

index.addAll([
  { id: "1", title: "Getting started with BM25", body: "BM25 is a ranking function...", tags: ["search", "ranking"] },
  { id: "2", title: "Unicode tokenization", body: "Handling café, naïve, 搜索, بحث correctly.", tags: ["unicode"] },
]);

const results = index.search("bm25 OR unicode");
for (const r of results) {
  console.log(r.id, r.score, r.matched);
}
```

## API

### Constructing an index

```ts
new SearchIndex<Doc>({
  fields: { title: { boost: 3 }, body: { boost: 1 }, tags: { boost: 2 } },
  tokenizer?: (text: string) => string[],           // default: unicode-aware word split, lowercased
  stopwords?: Set<string> | "english" | "none",     // default: "english"
  stemmer?: (token: string) => string,              // default: identity
  idField?: keyof Doc,                              // default: "id"
  k1?: number,                                      // default: 1.2
  b?: number,                                       // default: 0.75
});
```

Fields may be plain strings, string arrays (e.g. `tags`), or numbers
(coerced to strings). Adding a document that is missing a declared field is
fine (indexed as empty); a field not declared in `fields` is silently
ignored during indexing.

### Mutations

```ts
index.add(doc);           // add or replace by id, O(fields * tokens)
index.addAll(docs);       // batch add
index.remove(id);         // delete by id; cleans up all postings, no orphans
index.update(id, patch);  // partial update; only reindexes the changed fields
index.size;                // number of live docs
index.has(id);              // presence check
```

### Searching

```ts
const results = index.search(query, options?);
```

`query` may be:

- **A string**, parsed for boolean operators `AND`, `OR`, `NOT`, quoted
  `"exact phrase"`, parenthesized grouping, and field prefixes
  (`title:foo`). Default operator between adjacent terms is `OR`.
  Precedence: `NOT` > `AND` > `OR`.
- **A structured query object**, one of:
  ```ts
  { term: string, field?: string }
  { phrase: string, field?: string, slop?: number }   // slop default 0 = exact adjacency
  { prefix: string, field?: string }
  { fuzzy: string, field?: string, maxEdits?: 1 | 2 }  // Levenshtein distance
  { and: Query[] } | { or: Query[] } | { not: Query }
  ```

`options`:

- `limit` (default 10), `offset` (default 0)
- `filter?: (doc: Doc) => boolean` — applied **after** ranking/sorting, before pagination
- `boostFields?: Record<string, number>` — per-query multiplier on top of the field's configured boost; unknown field names are ignored, not an error
- `snippet?: { field: string, length: number }` — returns an excerpt with `<mark>...</mark>` around matched terms; if the requested field has no match, a plain excerpt is returned (never throws)

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

Results are sorted by score descending, then id ascending for deterministic
tie-breaking.

### Introspection

```ts
index.docs();               // iterable of { id, doc }
index.terms();               // iterable of unique indexed terms
index.docFrequency(term);    // number of docs containing `term` (after tokenizing/stemming)
```

### Serialization

```ts
const snapshot = index.toJSON();          // plain-JSON snapshot
const restored = SearchIndex.fromJSON<Doc>(snapshot, {
  tokenizer, stemmer, stopwords,          // re-supply any custom functions used originally
});
```

Functions (tokenizer/stemmer) are never serialized — only state. If the
original index used a custom tokenizer/stemmer/stopwords, pass the same
ones to `fromJSON` so future `add`/`update` calls remain consistent with
the restored postings (the restored postings themselves are taken verbatim
from the snapshot, not re-tokenized, so existing data is exact regardless).

## Ranking

- **BM25** (tuneable `k1`, `b`) is used for term scoring, not raw TF-IDF.
- **Phrase queries** score with a proximity bonus: matches with a smaller
  gap between the query terms' positions rank higher than more spread-out
  matches, on top of the base BM25 score of the phrase's terms (see
  `bestPhraseWindow` in `src/queryEngine.ts` for the exact algorithm).
- **Field boosts** multiply each field's contribution to a document's score.
- Ties are broken by ascending document id for determinism.

## Unicode handling

The default tokenizer splits on runs of `\p{L}\p{N}` (unicode letters and
numbers) after NFC-normalizing and lowercasing the input, so:

- Non-Latin scripts (Chinese, Arabic, etc.) are matched correctly.
- Accented Latin characters (`café`, `naïve`) are matched case-insensitively.
- Combining-character sequences (e.g. `e` + U+0301 combining acute) match
  their precomposed equivalents (`é`) because both are NFC-normalized
  before tokenizing/matching.

**Known limitation**: contiguous CJK text with no whitespace (e.g.
`搜索引擎`) is indexed as a single token per contiguous run, because
`\p{L}\p{N}` correctly identifies CJK characters as letters but cannot by
itself infer word boundaries without a segmentation dictionary/algorithm.
Space-separated CJK words tokenize and match correctly; dictionary-based
segmentation is out of scope for a zero-dependency default tokenizer (a
consumer can supply a custom `tokenizer` that performs segmentation if
needed).

## Design notes

- **Zero runtime dependencies.** BM25, the boolean query parser, phrase
  proximity, and Levenshtein fuzzy matching are implemented from scratch in
  `src/bm25.ts`, `src/queryParser.ts`, `src/queryEngine.ts`, and
  `src/levenshtein.ts` respectively — there is no lower-complexity rung
  (stdlib/native/existing dependency) available for these under the
  zero-dependency constraint. See `.quality-loop/plan.md` and
  `.quality-loop/decision-log.md` for the full complexity-brake reasoning
  and a record of bugs found and fixed during implementation.
- **No global state.** All state lives on the `SearchIndex` instance
  (postings, doc store, corpus stats); two instances never share state.
- **Deterministic.** Same input produces the same output, including snippet
  text and tie-broken ordering, on any run.

## Benchmark

```bash
npm run build
node dist/bench/bench.js
```

`bench/bench.ts` generates a deterministic (seed 42, Mulberry32 PRNG)
10,000-document synthetic corpus, indexes it, runs a fixed query workload
(1000 single-term, 500 two-term OR, 500 two-term AND, 200 phrase, 100
fuzzy-edit-1 queries), and prints a JSON summary of build time, estimated
memory footprint, and per-workload latency percentiles.

## Testing

```bash
npm test
```

Runs Node's built-in test runner (`node --test`) against the compiled
`dist/test/` directory. No external test framework is used or installed.

## Source of the task specification

Built to the specification in the working repository's brief
(`TASK.md`), covering index construction, mutation, structured/boolean
query parsing, BM25 + phrase-proximity ranking, snippet highlighting,
serialization, and a benchmark harness.
