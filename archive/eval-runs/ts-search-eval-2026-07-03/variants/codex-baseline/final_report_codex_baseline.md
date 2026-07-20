# Codex baseline TS search final report

Summary: Built a dependency-free strict TypeScript in-memory search library with BM25 ranking, boolean/string and structured queries, field boosts, phrase slop/proximity, prefix/fuzzy search, Unicode tokenization, snippets, updates/removes, introspection, serialization, tests, benchmark, and README.

Acceptance checks:
- npm install: PASS
  
  up to date, audited 4 packages in 897ms
  
  found 0 vulnerabilities
- npm run build: PASS
  
  > @eval/minisearch@0.1.0 build
  > tsc
  
- npm test: PASS
    ...
  # Subtest: serialization roundtrip preserves search behavior
  ok 7 - serialization roundtrip preserves search behavior
    ---
    duration_ms: 7.369644
    ...
  # Subtest: snippet highlights matched text
  ok 8 - snippet highlights matched text
    ---
    duration_ms: 0.512613
    ...
  # Subtest: update reindexes changed field only
  ok 9 - update reindexes changed field only
    ---
    duration_ms: 1.433005
    ...
  # Subtest: edge cases: empty queries, missing fields, prefix, filters, and docs iterator
  ok 10 - edge cases: empty queries, missing fields, prefix, filters, and docs iterator
    ---
    duration_ms: 0.451237
    ...
  1..10
  # tests 10
  # suites 0
  # pass 10
  # fail 0
  # cancelled 0
  # skipped 0
  # todo 0
  # duration_ms 88.396276
- benchmark: PASS
  {
    "index_build_ms": 1588.315,
    "index_size_docs": 10000,
    "index_memory_estimate_kb": 316467,
    "queries": {
      "single_term": {
        "count": 1000,
        "total_ms": 215.306,
        "p50_us": 150,
        "p99_us": 978
      },
      "or_two": {
        "count": 500,
        "total_ms": 210.108,
        "p50_us": 329,
        "p99_us": 2740
      },
      "and_two": {
        "count": 500,
        "total_ms": 145.11,
        "p50_us": 240,
        "p99_us": 855
      },
      "phrase": {
        "count": 200,
        "total_ms": 15.47,
        "p50_us": 39,
        "p99_us": 197
      },
      "fuzzy_edit1": {
        "count": 100,
        "total_ms": 2431.318,
        "p50_us": 21388,
        "p99_us": 53633
      }
    }
  }

Files created:
- ./README.md
- ./acceptance_bench.json
- ./acceptance_bench_full.txt
- ./acceptance_build_tail.txt
- ./acceptance_npm_install_tail.txt
- ./acceptance_test_tail.txt
- ./bench/bench.ts
- ./bench/words.ts
- ./final_report_codex_baseline.md
- ./package-lock.json
- ./package.json
- ./src/index.ts
- ./test/search.test.ts
- ./tsconfig.json

Runtime dependency count: 0
