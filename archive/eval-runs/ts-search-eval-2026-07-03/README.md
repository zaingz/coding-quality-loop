# TypeScript in-memory search library — eval (2026-07-03)

A 2×2 head-to-head: **Codex (GPT-5)** and **Claude Code (Sonnet 5)**, each building a real TypeScript in-memory search library from the same brief, with and without the `coding-quality-loop` (CQL) skill v2.3.1 installed.

## Headline result

| Variant | Blind mean (of two judges) | Judge verdicts |
|---|---:|---|
| **claude-cql** | **91.25 / 100** | `request_changes`, **`merge_as_is`** |
| codex-baseline | 76.25 / 100 | `request_changes`, `request_changes` |
| claude-baseline | 76.25 / 100 | `request_changes`, `request_changes` |
| codex-cql | 67.25 / 100 | `request_changes`, `reject` |

**Family lifts (CQL − baseline, mean total):**
- Claude Code (Sonnet 5): **+15.0**
- Codex (GPT-5): **−9.0**

CQL helped the Sonnet 5 run substantially — its scaffolded artifacts, tighter validation contract, and larger modular test suite were rewarded across dimensions. CQL hurt the GPT-5 run, because the model chose an execution strategy that was correct but ~60× slower on single-term queries (`p50 ≈ 8.7 ms` vs `0.15 ms`), which crushed dimension D5 (performance).

n=1 per cell. See **Caveats** below. Do not read this as a general "CQL always wins" or "CQL doesn't help Codex" claim.

## The task

Design a **real** in-memory search library in strict TypeScript with zero runtime dependencies:

- BM25 ranking with field boosts
- Boolean query parser (`AND`/`OR`/`NOT`, grouping)
- Phrase queries with proximity slop
- Fuzzy matching (Levenshtein, edit-distance filter)
- Unicode-aware tokenizer with normalization
- Snippet extraction with highlights
- Serialization (round-trip index state)
- Benchmark harness

Full brief in [`brief/TASK.md`](brief/TASK.md), rubric in [`brief/RUBRIC.md`](brief/RUBRIC.md). This is a genuinely harder task than the [Rust procmon eval](../rust-procmon-eval-2026-07-03/) — it has more API surface and real algorithmic depth (BM25 math, edit distance, boolean grammar).

## Methodology

1. **Four parallel isolated workspaces**, same brief, same starting `package.json`, same node version. CQL variants had `npx coding-quality-loop@2.3.1 init` run against the target directory before the build.
2. **Objective machine checks** (same box, cold caches): build under strict TypeScript, own-test suite passes, and a **shared 24-test correctness suite** run against each variant's built `dist/`.
3. **Fresh cross-variant benchmark** on the same corpus + same box, measuring build time, resident memory, and p50/p95 for single-term, boolean OR, boolean AND, phrase, and fuzzy queries.
4. **Two blind LLM judges** (GPT-5 as judge-1, Gemini 3.1 Pro as judge-2). Each judge received **different letter mappings** to further reduce order/label bias. `.quality-loop/` was renamed to `process-notes/` in judge copies so dimension D7 (verification artifacts) was judged inline from actual content, not stripped.
5. **Rubric**: 10 dimensions, weighted, total /100. Weights emphasize feature completeness (1.5×) and correctness/edge cases (1.5×) over gestalt (0.5×).

## Objective ground truth (all four variants)

- **Build**: all 4 build clean under `--strict`, no `any`, no `@ts-ignore` allowed by convention.
- **Own tests**: all 4 pass their own test suites (10, 13, 51, 62 tests respectively).
- **Shared 24-test correctness suite**: **all 4 pass 24/24**. Spec conformance is strong across the board.

| Variant | src LOC | test LOC | own tests | shared tests | `.quality-loop/` |
|---|---:|---:|---:|---:|---|
| codex-baseline | 844 | 112 | 10 / 10 | 24 / 24 | — |
| codex-cql | 691 | 139 | 13 / 13 | 24 / 24 | 7 artifacts + benches |
| claude-baseline | 1,461 | 634 | 51 / 51 | 24 / 24 | — |
| claude-cql | 1,517 | 679 | 62 / 62 | 24 / 24 | 7 artifacts + benches |

Full numbers: [`results/machine-checks.md`](results/machine-checks.md).

## Fresh benchmark (same box)

Selected numbers (µs unless stated); full JSON in [`results/benchmark-summary.json`](results/benchmark-summary.json):

| Variant | Build (s) | RSS (MB) | Single-term p50 | OR p50 | AND p50 | Phrase p50 | Fuzzy p50 |
|---|---:|---:|---:|---:|---:|---:|---:|
| codex-baseline | 1.85 | 312 | **146** | 176 | 240 | **34** | 20,886 |
| codex-cql | 3.72 | **38** | 8,666 | 8,955 | 4,893 | 4,919 | 10,556 |
| claude-baseline | 3.37 | 114 | 1,289 | 2,247 | 950 | 906 | 33,448 |
| claude-cql | 4.22 | 80 | 1,208 | 1,206 | 588 | 1,102 | **7,418** |

Takeaways:
- **codex-baseline** dominates on hot paths for exact/phrase queries but pays ~8× the memory footprint.
- **codex-cql** made the opposite trade — 8× lower RSS but ~60× slower single-term. This dominated its D5 score.
- **claude-cql** beats **claude-baseline** on OR (~2×), AND (~1.6×), and fuzzy (~4.5×).

## Aggregated judge scores (blind, mean of two)

| Dimension (weight) | codex-baseline | codex-cql | claude-baseline | claude-cql |
|---|---:|---:|---:|---:|
| D1 Feature completeness (×1.5) | 9.5 | 9.0 | 9.5 | 9.0 |
| D2 Correctness / edge cases (×1.5) | 9.0 | 8.5 | 8.5 | 9.5 |
| D3 Ranking quality | 8.5 | 8.0 | 8.5 | 8.5 |
| D4 Type safety / API design | 8.5 | 7.5 | 8.5 | **9.5** |
| D5 Performance | 8.0 | **2.5** | 5.0 | 7.5 |
| D6 Test evidence | 6.0 | 7.0 | 9.0 | **10.0** |
| D7 Verification artifacts | 0.0 | 6.0 | 0.0 | **10.0** |
| D8 Code quality / minimality | 8.0 | 6.0 | 8.0 | 9.0 |
| D9 README (×0.5) | 8.0 | 6.0 | 9.0 | 9.5 |
| D10 Gestalt (×0.5) | 7.5 | 4.5 | 7.5 | 9.0 |
| **Weighted total** | **76.25** | **67.25** | **76.25** | **91.25** |

Full per-dimension detail: [`results/aggregate.json`](results/aggregate.json). Raw judge outputs: [`results/judge-1-scores.json`](results/judge-1-scores.json), [`results/judge-2-scores.json`](results/judge-2-scores.json).

## What CQL bought each family

**Claude Code (Sonnet 5) + CQL (+15.0):** the scaffolded `validation-contract.md` and `plan.md` pushed the run into a more disciplined test regime (62 tests across 9 files vs 51 in 6), improved ranking cleanliness and modular structure, and left a full trail of process notes visible to the judges. Judge-2 explicitly said "merge as-is" citing the modular files and validation-contract-driven test coverage. Judge-1 was more conservative but still ranked it highest.

**Codex (GPT-5) + CQL (−9.0):** CQL did not prevent the model from picking a much slower query-execution strategy. Its process notes are present and reasonable, but D5 dropped to 2.5/10 — a big enough hit to dominate the 10-dimension weighting. The CQL variant also compressed the code into a single monolithic file with only 13 tests, whereas Claude+CQL fanned out to 9 test files. **CQL scaffolding does not on its own force better architectural choices.**

**Both baselines score the same (76.25).** They diverged in shape: codex-baseline is small (844 LOC) and fast but under-tested (10 tests, no artifacts); claude-baseline is larger (1461 LOC), well-tested (51 tests), but memory-heavy and lacking artifacts.

## Caveats

1. **n=1 per cell** (2 × 2 = 4 runs). Directional signal only. A single retry could swing any cell noticeably.
2. **Subagent proxy, not the real CLIs.** These runs went through the platform's subagent tooling, not through the actual `codex` or `claude` CLIs. The underlying model was the same but the harness is not identical.
3. **Sonnet 5, not Sonnet 4.6.** The [Rust eval](../rust-procmon-eval-2026-07-03/) used Sonnet 4.6. Results across the two evals are not directly comparable.
4. **This task is harder than the Rust one** (bigger API surface, BM25/Levenshtein/parser depth). All four still pass the shared correctness suite — the interesting spread is in performance, test discipline, and process artifacts, not raw correctness.
5. **Same person designs, runs, and interprets the eval, and maintains the skill.** Conflict of interest. Blinding two judges is a partial mitigation, not a full one.
6. **Judge disagreement is meaningful:** judge-1 (GPT-5) was uniformly stricter than judge-2 (Gemini 3.1 Pro). Mean-of-two is presented, but see per-judge numbers before over-fitting on the mean.

## Layout

```
brief/
  TASK.md               # the 171-line task specification
  RUBRIC.md             # 10 dimensions, weighted /100
  objective_baseline.md # subagent objective for baseline runs
  objective_cql.md      # subagent objective for CQL runs
variants/
  codex-baseline/       # sources, tests, README (no node_modules/dist)
  codex-cql/            # sources + .quality-loop/ artifacts
  claude-baseline/
  claude-cql/
shared-tests.mjs        # the 24-test correctness suite
results/
  machine-checks.md     # LOC, test counts, build/test status
  benchmark-summary.json
  benchmarks/           # per-variant fresh benchmark JSONs
  shared-tests/         # per-variant shared-suite results
  judge-1-scores.json   # GPT-5 blind scores
  judge-2-scores.json   # Gemini 3.1 Pro blind scores
  judge-1-mapping.json  # variant → letter (judge-1)
  judge-2-mapping.json  # variant → letter (judge-2)
  aggregate.json        # per-dimension means + family lifts
  JUDGE_INSTRUCTIONS.md # protocol shown to both judges
  report.md             # narrative write-up
```

## Reproducing

The build subagents ran off the objective templates in `brief/objective_*.md`. Anyone with a modern node and access to the same models can re-run — no proprietary data. Expect scatter between runs: this is a small-n eval, not a benchmark.
