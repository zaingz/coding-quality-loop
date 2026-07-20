# @eval/minisearch

<!-- The vendored copy of the Quality Loop skill (scripts/, hosts/, assets/) has
been removed from this eval artifact to avoid duplicating the source of truth.
The skill lives at the repo root; the run artifacts under .quality-loop/ and the
eval's own src/test/bench are what's preserved here. -->

A strict TypeScript, zero-runtime-dependency in-memory full-text search library.

## Install and build

```bash
npm install
npm run build
npm test
npm run bench
```

## Example

```ts
import { SearchIndex } from "@eval/minisearch";

type Doc = { id: string; title: string; body: string; tags: string[] } & Record<string, unknown>;

const index = new SearchIndex<Doc>({
  fields: { title: { boost: 3 }, body: { boost: 1 }, tags: { boost: 2 } },
  stopwords: "english"
});

index.add({ id: "1", title: "Quick brown fox", body: "A quick search example", tags: ["demo"] });
index.addAll([{ id: "2", title: "Fuzzy colour", body: "Color matching", tags: [] }]);

const results = index.search('title:quick OR {not real syntax}', {
  limit: 5,
  snippet: { field: "body", length: 80 }
});
```

## Query API

`index.search(query, options?)` accepts either a string query or a structured query.

String queries support:

- `AND`, `OR`, `NOT` with precedence `NOT > AND > OR`
- parentheses
- quoted phrases, e.g. `"quick brown"`
- field prefixes, e.g. `title:quick` or `body:"quick brown"`
- default whitespace operator `OR`, with `NOT` after an `AND` sequence treated as exclusion

Structured queries:

```ts
type Query =
  | { term: string; field?: string }
  | { phrase: string; field?: string; slop?: number }
  | { prefix: string; field?: string }
  | { fuzzy: string; field?: string; maxEdits?: 1 | 2 }
  | { and: Query[] }
  | { or: Query[] }
  | { not: Query };
```

Options include `limit`, `offset`, `filter`, `boostFields`, and `snippet: { field, length }`.

## Ranking

Results use BM25 (`k1=1.2`, `b=0.75` by default) with field boosts and deterministic sorting by score descending, then id ascending. Phrase queries add a proximity multiplier so closer terms rank higher.

## Mutations and introspection

- `add(doc)`, `addAll(docs)`, `remove(id)`, `update(id, patch)`
- `size`, `has(id)`
- `docs()`, `terms()`, `docFrequency(term)`

Declared fields may be strings, string arrays, numbers, missing, or undefined. Undeclared fields are ignored.

## Serialization

```ts
const snapshot = index.toJSON();
const restored = SearchIndex.fromJSON<Doc>(snapshot, {
  // Re-supply custom tokenizer, stemmer, or stopwords here if needed.
});
```

Snapshots are plain JSON and contain documents plus index options, not custom functions.
