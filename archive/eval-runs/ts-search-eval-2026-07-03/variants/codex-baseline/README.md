# @eval/minisearch

A dependency-free, in-memory full-text search index for TypeScript. It supports BM25 ranking, boosted fields, boolean string queries, structured queries, phrase proximity, fuzzy matching, prefix matching, highlighting snippets, updates/removes, introspection, and JSON snapshots.

## Install and build

```sh
npm install
npm run build
npm test
npm run bench
```

The package is private for this evaluation and has no runtime dependencies.

## Quick start

```ts
import { SearchIndex } from '@eval/minisearch';

type Doc = { id: string; title: string; body: string; tags: string[] };

const index = new SearchIndex<Doc>({
  fields: {
    title: { boost: 3 },
    body: { boost: 1 },
    tags: { boost: 2 }
  },
  stopwords: 'english'
});

index.add({
  id: '1',
  title: 'Quick brown fox',
  body: 'A quick brown fox jumps over a lazy dog.',
  tags: ['animal']
});

const results = index.search('title:quick AND "brown fox"', {
  limit: 5,
  snippet: { field: 'body', length: 80 }
});
```

## Constructor

```ts
new SearchIndex<Doc>({
  fields: { title: { boost: 3 }, body: { boost: 1 } },
  tokenizer?: (text: string) => string[],
  stopwords?: Set<string> | 'english' | 'none',
  stemmer?: (token: string) => string,
  idField?: keyof Doc,
  k1?: number,
  b?: number
})
```

Declared fields are indexed when present. Missing fields are treated as empty, and undeclared document fields are ignored by the index. String arrays and numbers are coerced to text. The default tokenizer lowercases and uses Unicode property escapes so non-ASCII words such as `café`, `搜索`, and `بحث` are tokenized safely.

## Mutations

- `add(doc)` adds or replaces by id.
- `addAll(docs)` indexes a batch.
- `remove(id)` deletes a document and its postings.
- `update(id, patch)` applies a partial update and reindexes changed declared fields.
- `size` returns the number of live documents.
- `has(id)` checks presence.

## Queries

String queries support `AND`, `OR`, `NOT`, quotes for exact phrases, parentheses, and `field:term` / `field:"phrase"`. `NOT` binds tighter than `AND`, and `AND` binds tighter than `OR`; plain adjacent terms default to `OR`, while `term NOT other` is treated as `term AND NOT other`.

Structured queries are also supported:

```ts
index.search({ term: 'fox', field: 'title' });
index.search({ phrase: 'quick brown', field: 'body', slop: 1 });
index.search({ prefix: 'qui' });
index.search({ fuzzy: 'colour', maxEdits: 1 });
index.search({ and: [{ term: 'quick' }, { not: { term: 'slow' } }] });
```

## Ranking and results

Ranking uses BM25 with configurable `k1` and `b`; phrase queries add a proximity multiplier, and field boosts multiply per-field contributions. Results are sorted by score descending and id ascending for deterministic tie-breaking.

```ts
type SearchResult<Doc> = {
  id: string;
  doc: Doc;
  score: number;
  matched: { field: string; terms: string[] }[];
  snippet?: string;
};
```

Search options include `limit`, `offset`, `filter`, `boostFields`, and `snippet`. Snippets return an excerpt with matching terms wrapped in `<mark>...</mark>` when possible.

## Introspection and serialization

```ts
for (const { id, doc } of index.docs()) console.log(id, doc);
for (const term of index.terms()) console.log(term);
console.log(index.docFrequency('fox'));

const snapshot = index.toJSON();
const restored = SearchIndex.fromJSON<Doc>(snapshot);
```

Snapshots serialize plain index state and documents. Custom tokenizer, stemmer, or custom stopword functions must be supplied again to `fromJSON`.

## Benchmark

`bench/bench.ts` generates 10,000 deterministic synthetic documents, builds an index, runs 2,300 queries, and prints a JSON summary. Run it with:

```sh
npm run bench
```
