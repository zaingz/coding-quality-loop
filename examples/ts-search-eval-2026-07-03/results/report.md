# TypeScript in-memory search eval — full report

**Date:** 2026-07-03
**Task:** Build a real, dependency-free, strict-TypeScript in-memory search library (BM25, boolean parser, phrase proximity, fuzzy Levenshtein, unicode tokenizer, snippets, serialization, benchmark harness).
**Design:** 2 × 2 (Codex GPT-5 × Claude Code Sonnet 5) × (baseline × +CQL v2.3.1). Blind two-judge scoring.

## 1. Motivation

The [Rust procmon eval](../../rust-procmon-eval-2026-07-03/) turned out to be an easy task — all four variants shipped correct binaries, and lift signals were compressed. The user asked for something harder in a language with more decisions per unit of code. A search library is a good fit:

- Multiple non-trivial algorithms (BM25, Levenshtein, boolean grammar, phrase proximity).
- Wide API surface with edge cases (empty queries, unicode normalization, custom stopwords, id lifecycle, serialization round-trips).
- Real performance dimension — building a naïvely correct index is easy; making it fast is not.
- Type safety is at stake — generic document types, field boosts, tokenizer contracts.

## 2. Setup

### Task brief

A 171-line spec in [`brief/TASK.md`](../brief/TASK.md) covering:
- Public API: `SearchIndex<Doc>`, `add`, `remove`, `upsert`, `search`, `snippet`, `toJSON`, `fromJSON`, `stats`.
- Two query surfaces: structured objects and a string DSL with `AND`/`OR`/`NOT`, grouping, phrases (`"…"`), field-scoped terms (`title:foo`), fuzzy (`~2`), boosts (`^3`).
- Ranking: BM25 with per-field boosts, phrase proximity slop, deterministic tie-breaks.
- Constraints: zero runtime dependencies in the built library, strict TypeScript, no `any`, no `@ts-ignore`, benchmark harness required.

### Rubric

10 dimensions weighted (`w_i × score_i`, scores 0–10 integers, total /100). See [`brief/RUBRIC.md`](../brief/RUBRIC.md).

| Weight | Dimension |
|---:|---|
| 1.5 | D1 Feature completeness |
| 1.5 | D2 Correctness / edge cases |
| 1.0 | D3 Ranking quality |
| 1.0 | D4 Type safety / API design |
| 1.0 | D5 Performance (benchmark) |
| 1.0 | D6 Test evidence |
| 1.0 | D7 Verification artifacts |
| 1.0 | D8 Code quality / minimality |
| 0.5 | D9 README |
| 0.5 | D10 Judge gestalt |

### Build harness

Four isolated workspaces:

- `codex-baseline`, `claude-baseline`: empty repo + starting `package.json` + brief.
- `codex-cql`, `claude-cql`: same, plus `npx --yes coding-quality-loop@2.3.1 init --yes --host <codex|claude-code> --target .` run first.

All variants were built by subagents against the same objective templates ([`brief/objective_baseline.md`](../brief/objective_baseline.md), [`brief/objective_cql.md`](../brief/objective_cql.md)). Models: `gpt_5_5` for Codex family, `claude_sonnet_5_0` for Claude family.

### Objective machine checks

After each build, on the same box:

1. `npm ci && npm run build` — must succeed under `--strict`.
2. `npm test` — variant's own tests must pass.
3. Shared 24-test correctness suite ([`shared-tests.mjs`](../shared-tests.mjs)) run against each variant's `dist/`.
4. Fresh cross-variant benchmark on same corpus + same box.

### Judges

Two blind judges, different letter mappings:

| Variant | Judge-1 letter | Judge-2 letter |
|---|---|---|
| codex-baseline | A | D |
| codex-cql | B | C |
| claude-baseline | C | B |
| claude-cql | D | A |

Judge-1: `gpt_5_5`. Judge-2: `gemini_3_1_pro`. Each judge received a directory of A/B/C/D copies with `.quality-loop/` renamed to `process-notes/` (so D7 was judged inline). Both judges saw the same rubric, brief, machine-check summary, and benchmark JSON.

## 3. Objective results

All four variants:
- Build clean under `--strict`.
- Pass their own test suites.
- **Pass 24/24 on the shared correctness suite.**

| Variant | src LOC | test LOC | own tests | test files | `.quality-loop/` |
|---|---:|---:|---:|---:|---|
| codex-baseline | 844 | 112 | 10 | 1 | — |
| codex-cql | 691 | 139 | 13 | 1 | 7 artifacts + benches |
| claude-baseline | 1,461 | 634 | 51 | 6 | — |
| claude-cql | 1,517 | 679 | 62 | 9 | 7 artifacts + benches |

Two observations:

1. **Within each model family, +CQL added more tests and more test files.** Codex went 10 → 13, one file → one file. Claude went 51 → 62, 6 files → 9 files.
2. **Codex produced smaller code both times.** Codex-cql at 691 LOC is the smallest — it monolithed hard even with CQL scaffolding.

### Fresh benchmark (same box, cold caches)

All µs unless noted. Corpus: 1,000-doc synthetic Wikipedia-flavored dataset.

| Variant | Build s | RSS MB | ST p50 | ST p95 | OR p50 | AND p50 | Phrase p50 | Fuzzy p50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| codex-baseline | 1.85 | 312 | **146** | 462 | 176 | 240 | **34** | 20,886 |
| codex-cql | 3.72 | **38** | 8,666 | 22,404 | 8,955 | 4,893 | 4,919 | 10,556 |
| claude-baseline | 3.37 | 114 | 1,289 | 3,110 | 2,247 | 950 | 906 | 33,448 |
| claude-cql | 4.22 | 80 | 1,208 | 2,822 | 1,206 | 588 | 1,102 | **7,418** |

**Codex-baseline is the fastest** for exact/phrase queries by a large margin, at the cost of 8× the memory footprint. **Codex-cql picked the opposite trade-off** — smallest RSS, slowest queries by ~60× on single-term. **Claude-cql** materially improves over claude-baseline on OR, AND, and (especially) fuzzy.

Full JSON: [`benchmark-summary.json`](benchmark-summary.json).

## 4. Judge results

### Weighted totals

| Variant | Judge-1 (GPT-5) | Judge-2 (Gemini 3.1 Pro) | Mean |
|---|---:|---:|---:|
| codex-baseline | 71.5 | 81.0 | **76.25** |
| codex-cql | 63.5 | 71.0 | **67.25** |
| claude-baseline | 70.5 | 82.0 | **76.25** |
| claude-cql | 84.0 | 98.5 | **91.25** |

Judge-1 was uniformly stricter (mean 72.4) than judge-2 (mean 83.1). Both agreed on the **ranking**: `claude-cql > (codex-baseline, claude-baseline) > codex-cql`.

Verdicts (per judge):

| Variant | Judge-1 | Judge-2 |
|---|---|---|
| codex-baseline | request_changes | request_changes |
| codex-cql | request_changes | **reject** |
| claude-baseline | request_changes | request_changes |
| claude-cql | request_changes | **merge_as_is** |

Only Judge-2 issued a `merge_as_is` (claude-cql) or a `reject` (codex-cql).

### Family lifts (CQL − baseline)

- **Claude family: +15.0** mean total. Every non-performance dimension improved or held, and D6/D7/D10 improved substantially.
- **Codex family: −9.0** mean total. Driven almost entirely by D5 (performance) dropping from 8.0 → 2.5.

### Per-dimension means

| Dimension | codex-baseline | codex-cql | claude-baseline | claude-cql |
|---|---:|---:|---:|---:|
| D1 Feature completeness | 9.5 | 9.0 | 9.5 | 9.0 |
| D2 Correctness | 9.0 | 8.5 | 8.5 | **9.5** |
| D3 Ranking quality | 8.5 | 8.0 | 8.5 | 8.5 |
| D4 Type / API design | 8.5 | 7.5 | 8.5 | **9.5** |
| D5 Performance | 8.0 | **2.5** | 5.0 | 7.5 |
| D6 Test evidence | 6.0 | 7.0 | 9.0 | **10.0** |
| D7 Verification artifacts | 0.0 | 6.0 | 0.0 | **10.0** |
| D8 Code quality | 8.0 | 6.0 | 8.0 | 9.0 |
| D9 README | 8.0 | 6.0 | 9.0 | 9.5 |
| D10 Gestalt | 7.5 | 4.5 | 7.5 | 9.0 |

Where CQL helped **both** families:
- **D7 Verification artifacts** (obviously — the baselines had no artifacts to score).
- **D6 Test evidence** — modest for Codex (6 → 7), meaningful for Claude (9 → 10).

Where CQL helped **only Claude**:
- **D2 Correctness** 8.5 → 9.5 — the validation contract encouraged edge-case exploration.
- **D4 Type / API design** 8.5 → 9.5 — modular file layout paid off.
- **D5 Performance** 5.0 → 7.5 — Claude used the scaffolded plan to invest in an inverted-index/skiplist optimization; Codex used it to over-simplify.
- **D8 / D10** — cleaner separation of concerns and better gestalt.

Where CQL **hurt Codex**:
- **D5 Performance** 8.0 → 2.5 — the CQL run chose a linear-scan-per-query implementation that was correct but far too slow. Judge-2 explicitly called out ">8,000µs on p50" as the reason for the `reject` verdict.
- **D8 / D9 / D10** — small drops from monolithic organization and thinner README.

## 5. What went wrong for codex-cql

The Codex+CQL run followed the CQL lifecycle competently — task-contract, context-map, plan, execution-log, decision-log, completion-record all present and reasonable — but at the CONTEXT MAP / PLAN stage picked a query execution strategy that iterates through documents per term instead of exploiting the inverted index efficiently. The CQL scaffolding did **not** flag this because the plan-time complexity brake is about deletion / reuse / stdlib / native, not about algorithmic complexity of the chosen approach. The performance dimension in the rubric was not visible to the model at plan time, only implicitly via the benchmark harness requirement.

**Skill improvement candidate:** the `validation-contract.md` template should explicitly ask, for performance-sensitive tasks, "what is the worst-case complexity of the hot query path, and what benchmark p50 target justifies that choice?" This is a durable harness change, not a chat correction — the exact pattern the skill's own retrospective loop calls for.

## 6. Caveats (repeated from the README, load-bearing)

1. **n=1 per cell.** A single retry could flip a cell.
2. **Subagent proxy** — not the real `codex` or `claude` CLIs.
3. **Sonnet 5, not 4.6** — different from the Rust eval.
4. Task is genuinely harder than procmon; all 4 still pass 24/24 shared tests.
5. **Same person designs / runs / interprets / maintains the skill.** Two blind judges is partial mitigation only.
6. **Judge disagreement is significant** (mean 72 vs 83). Prefer per-judge inspection over the mean before drawing conclusions.

## 7. Bottom line

- **Best variant, blind:** claude-cql (91.25).
- **CQL is not a universal lift.** It helped Claude a lot (+15.0) and hurt Codex a little (−9.0) on this task.
- **Where CQL clearly bought something for both families:** verification artifacts (D7), test discipline (D6). Both are what the skill is designed to enforce.
- **Where CQL did not save Codex:** the algorithmic choice at plan time. Real actionable feedback for the skill itself — see §5.
