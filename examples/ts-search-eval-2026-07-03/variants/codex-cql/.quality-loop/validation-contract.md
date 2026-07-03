# Validation Contract

| Requirement | Concrete check/evidence |
| --- | --- |
| Strict package with required files | `package.json`, `tsconfig.json`, `src/`, `test/`, `bench/`, `README.md` exist; `npm run build` passes. |
| Zero runtime dependencies | `package.json` has empty `dependencies`; Node command reports dependency count 0. |
| Core mutations and introspection | Tests cover add/upsert, addAll, remove without orphaned postings, update, size/has/docs/terms/docFrequency. |
| Unicode tokenizer | Tests search `café`, `CAFÉ`, combining-character form, Chinese, and Arabic terms. |
| Boolean/string parser | Tests include `a AND b NOT c`, default OR, field prefix, and nested structured booleans. |
| Phrase/proximity | Tests exact phrase excludes non-adjacent match and slop/proximity ranks closer phrase higher. |
| Fuzzy Levenshtein | Test `colour` maxEdits 1 matches `color`; edge case with edit distance equal to length is safe. |
| BM25 ranking and boosts | Test title boost ranks title match above body-only match; deterministic id tie behavior. |
| Snippets | Test returns highlighted `<mark>` excerpt and handles requested nonmatching field. |
| Serialization | Test `fromJSON(toJSON())` returns equivalent search results and docs. |
| Benchmark | `npm run bench` completes and prints valid JSON with required keys/counts. |

## Regression risks to inspect in review
- Orphaned postings after replace/remove/update.
- Accidental global/shared mutable state between indexes.
- Runtime dependency drift.
- Query parser treating operators as terms in unintended places.
- Benchmark using nondeterministic RNG or malformed JSON.
