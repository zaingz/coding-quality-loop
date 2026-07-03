# Rubric — TypeScript in-memory search library

Score each variant against this rubric. Each dimension is scored **0–10** (integer) and weighted; the weighted total is **/100**.

## Dimensions

### 1. Feature completeness (weight 15)
Are all listed subcommands and API methods present and behaving as specified? Missing features are hard hits, not stylistic gaps. Check: BM25 (not just TF-IDF), phrase with proximity scoring, fuzzy with configurable maxEdits, boolean query string parser (AND/OR/NOT/quotes/field:), structured query objects, field boosts, snippets with `<mark>`, filter callback, serialization round-trip, update/remove without orphans, iteration methods.

### 2. Correctness on edge cases (weight 15)
Does it handle the listed edge cases without throwing, silent corruption, or wrong results? Empty index, unicode with combining characters, extremely long docs, upsert semantics, remove-mid-query, all-stopword queries, phrase-non-adjacent, deep boolean nesting, nonexistent field boost, snippet on non-matching field.

### 3. Ranking quality (weight 10)
BM25 is implemented (not just TF-IDF), formula matches literature, field boosts multiply correctly, phrase proximity affects score, tie-breaking is deterministic (score DESC, id ASC).

### 4. Type safety / API design (weight 10)
Public API is fully typed and generic over `Doc`. No `any`. No `@ts-ignore` without justification. Strict mode. Types are ergonomic (a caller can use it without fighting the compiler). Exported surface is minimal and coherent.

### 5. Performance (weight 10)
Judged from the benchmark JSON output. Index build under a reasonable bound (target: 10k docs indexed in <5s on a modern CPU; higher is worse). Single-term queries fast (target: p50 < 500µs, p99 < 5ms). Fuzzy queries do not scan every term for tiny queries (should use n-gram/prefix filter, not brute force over all terms).

### 6. Test evidence (weight 10)
Tests cover the required list, use `node --test`, actually exercise behavior (not just constructor assertions). Look for: phrase-vs-non-phrase discrimination, unicode assertions, serialization roundtrip equality, remove cleanup verified, and edge cases from the brief.

### 7. Verification evidence in the handoff (weight 10)
Beyond passing tests, did the agent record what it did? A validation contract, plan, execution log, or completion record. **Scored on substance, not template match** — boilerplate copies of a template score low. Missing entirely = 0.

### 8. Code quality / minimality (weight 10)
Reads like professional TypeScript. Coherent module structure. No dead code, TODOs, `console.log` debugging noise. Uses stdlib where reasonable. No speculative abstractions. No vendored copies of stdlib. Zero runtime deps (verified from package.json).

### 9. README quality (weight 5)
Is the README something you'd read? Every public method shown with a real example. Query DSL documented. Design choices (BM25 params, tokenizer defaults) explained. Under 3 pages.

### 10. Judge gestalt (weight 5)
Reviewer's honest professional gut: would you approve this PR for a real npm package? 10 = ship as-is; 5 = request changes; 0 = would not merge.

## Aggregation

```
score = 1.5*D1 + 1.5*D2 + 1.0*D3 + 1.0*D4 + 1.0*D5 + 1.0*D6 + 1.0*D7 + 1.0*D8 + 0.5*D9 + 0.5*D10
```

Where D1..D10 are 0-10 integer scores. Result is a number in [0, 100].

## Anti-hacks

- Longer is not automatically better; judge by what the extra lines do.
- Missing a required feature is a D1 hit, not softened by good code elsewhere.
- A validation-contract markdown that just paraphrases the brief with no signal → D7 low.
- Tests that assert `index.size === 0` after construction do not count for D6 — need behavioral tests.
- Impressive-looking BM25 with bugs (wrong idf, missing avgdl) → D3 low even if code is idiomatic.
- Faking the benchmark (hardcoded numbers, no real work) → D5 = 0.

## Judge protocol

- You are one of two blind judges. Variants are shuffled A/B/C/D per judge; the mapping is not disclosed.
- You must actually read the source. Do not skim.
- You may run `node --test` and the benchmark to verify behavior only if the machine-check summary is missing that data. The pre-computed machine-check summary is authoritative for build/test status.
- Return one JSON object per variant with `{dimension_1..10: {score, reason}, total, verdict}` where `verdict` is one of `merge_as_is | request_changes | reject`.
- Be a critical senior reviewer of a real npm package. Do not give participation trophies.
