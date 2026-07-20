# Claude baseline TS search — run results

## Summary

Built `@eval/minisearch`, a zero-dependency, strict-TypeScript, in-memory full-text
search library at `/home/user/workspace/ts-search-eval-2026-07-03/variants/claude-baseline/`.
It implements a real inverted index (term → field → docId → positions), BM25 ranking
(k1=1.2, b=0.75, tuneable), a hand-written boolean query parser supporting
`AND`/`OR`/`NOT`, quoted phrases, `field:term` scoping, and parenthesized nesting with
NOT > AND > OR precedence and OR as the default operator between bare terms, phrase
queries with slop-based proximity scoring, prefix and Levenshtein-bounded fuzzy
matching, a unicode-safe default tokenizer (`\p{L}\p{N}\p{M}`, NFC-normalized,
lowercased) that correctly handles `café`, `naïve`, `搜索`, `بحث`, and combining-mark
sequences, `<mark>`-based snippet highlighting, full `toJSON`/`fromJSON`
serialization, and mutation methods (`add`/`addAll`/`remove`/`update`) that keep
postings orphan-free. During development, three real bugs were found and fixed via
direct reproduction scripts before the final acceptance run: (1) the boolean parser
silently dropped a trailing `NOT` clause not preceded by an explicit `AND` (e.g.
`"a AND b NOT c"` lost the NOT clause), (2) bare adjacency between terms with no
explicit operator (the spec's default-OR case) silently dropped the second term
instead of combining as OR, and (3) a few tests used English stopwords (`"a"`,
`"same"`) as literal search terms, which is expected default-tokenizer behavior, not
a library bug, and were corrected to use non-stopword vocabulary. The final suite
of 51 tests (Node's built-in `node --test` runner, no external test framework) all
pass, the strict-mode TypeScript build is clean with zero errors, and the 10,000-doc
synthetic benchmark (seeded Mulberry32, seed 42) completes and prints valid JSON.

## Acceptance checks

| Check | Status |
|---|---|
| `npm install` | PASS (exit 0, 0 vulnerabilities, only `typescript` + `@types/node` installed) |
| `npm run build` (`tsc`, strict mode) | PASS (zero errors) |
| `npm test` (`node --test`, no jest/vitest/mocha) | PASS (51/51 tests, exit 0) |
| Benchmark runs and prints valid JSON | PASS (see below) |
| Zero runtime dependencies (`dependencies: {}`) | PASS (verified via `Object.keys(require('./package.json').dependencies).length === 0`) |
| No `.quality-loop/` artifacts | PASS (none created) |
| No jest/vitest/mocha/ts-node/tsx installed | PASS (verified in `node_modules`) |
| No git commit/push | PASS (directory is not a git repo; nothing committed) |

## Files created

```
package.json
tsconfig.json
README.md
src/index.ts
src/types.ts
src/tokenizer.ts
src/levenshtein.ts
src/queryParser.ts
src/SearchIndex.ts
test/basic.test.ts
test/ranking.test.ts
test/query.test.ts
test/snippet.test.ts
test/serialization.test.ts
test/introspection.test.ts
bench/words.ts
bench/bench.ts
```//(dist/, node_modules/, package-lock.json are build artifacts, not committed to any VCS since no git repo exists here)

## Benchmark JSON output

```json
{
  "index_build_ms": 3827.08,
  "index_size_docs": 10000,
  "index_memory_estimate_kb": 116386,
  "queries": {
    "single_term": {
      "count": 1000,
      "total_ms": 1474.47,
      "p50_us": 1281.14,
      "p99_us": 3300.83
    },
    "or_two": {
      "count": 500,
      "total_ms": 1590.98,
      "p50_us": 2848.62,
      "p99_us": 5335.88
    },
    "and_two": {
      "count": 500,
      "total_ms": 1031.44,
      "p50_us": 1662.92,
      "p99_us": 10096.05
    },
    "phrase": {
      "count": 200,
      "total_ms": 183.2,
      "p50_us": 507.39,
      "p99_us": 10025.5
    },
    "fuzzy_edit1": {
      "count": 100,
      "total_ms": 3691.69,
      "p50_us": 38569.01,
      "p99_us": 125289.54
    }
  }
}
```

## Known limitations (not blocking acceptance)

- Fuzzy queries do a full dictionary scan with bounded Levenshtein (no BK-tree/
  n-gram index), so `fuzzy_edit1` p50 (~38ms) is the slowest workload at this
  corpus/vocabulary size — documented as a known optimization opportunity in the
  README.
- `index_memory_estimate_kb` is a proxy based on JSON snapshot size × 2 (approximating
  V8's UTF-16 string storage), not actual heap profiling — reasonable for a
  dependency-free benchmark but not a precise RSS measurement.
