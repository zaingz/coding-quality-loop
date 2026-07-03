# Task Contract

## Goal
Build a strict TypeScript, zero-runtime-dependency in-memory full-text search package in `/home/user/workspace/ts-search-eval-2026-07-03/variants/codex-cql` that satisfies the task brief.

## Task class and risk
- Class: MEDIUM.
- Risk tier: medium, because ranking, parsing, mutation correctness, Unicode tokenization, serialization, and benchmark behavior interact across multiple modules.

## Acceptance criteria
1. Package metadata, strict TypeScript config, source, tests, benchmark, and README exist.
2. `SearchIndex<Doc>` supports schema-safe indexing, add/addAll/remove/update/size/has, docs/terms/docFrequency.
3. String and structured queries support boolean operators, field prefixes, phrase/slop, prefix, fuzzy Levenshtein, filters, pagination, snippets, and deterministic sorting.
4. Ranking uses BM25 with field boosts and phrase proximity.
5. Default tokenizer is Unicode-aware and case-insensitive.
6. Serialization round-trips through plain JSON; custom functions are supplied on restore.
7. Runtime dependencies remain zero; no jest/vitest/mocha/ts-node/tsx.
8. Acceptance commands pass: `npm install`, `npm run build`, `npm test`, benchmark prints JSON.

## Constraints
- Node 20 available.
- No runtime dependencies; dev dependencies limited to TypeScript and Node types.
- Strict TypeScript; no `any`, `@ts-ignore`, or unjustified type suppressions.
- Do not commit, push, or remove generated workspace files.

## Non-goals
- Persistent disk index, distributed search, stemming beyond caller-supplied stemmer, query language beyond the brief, npm publishing, or external services.

## Assumptions
- The default English stopword list may be compact, but must make all-stopword queries harmless.
- `fromJSON` may rebuild internal postings from serialized documents to keep snapshots simple and robust.
- Partial update can reindex only changed declared fields while preserving other fields.

## Verification plan
Run `npm install`, `npm run build`, `npm test`, inspect runtime dependencies, and run the benchmark to capture JSON.

## Escalation conditions
Stop if required behavior would need a runtime dependency, destructive operation, network service, ambiguous public API break, or repeated verification failure after two focused repair attempts.
