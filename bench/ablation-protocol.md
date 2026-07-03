# Ablation Protocol — CQL v3.0

## Goal

Prove which harness components are load-bearing for code quality (not artifact
production) by running ablation arms against real models on real tasks.

## Design

**3 tasks:**
1. **ts-search** — TypeScript in-memory search library (BM25, boolean parser, phrase, fuzzy, snippets, serialization, benchmark). Existing eval in `examples/ts-search-eval-2026-07-03/`.
2. **procmon** — Rust Unix process manager (CLI with list/find/kill/watch/tree, /proc parsing, minimal deps). Existing eval in `examples/rust-procmon-eval-2026-07-03/`.
3. **webapp** — Browser-based task manager with localStorage persistence, filter, responsive UI, browser-automation verification. Task spec in `bench/tasks/13-webapp-task-manager.json`.

**2-3 model families:** Claude (Sonnet), Codex (GPT-5), Droid/GLM (if available).

**3 seeds** per cell to reduce single-run noise.

**4 arms:**
| Arm | What runs | What is stripped |
|---|---|---|
| `baseline` | Raw brief, no skill | Everything |
| `v3-full` | CQL v3.0 skill, full lifecycle | Nothing |
| `v3-no-review` | CQL v3.0 skill, **no independent review** | The REVIEW phase (except PACKAGE) |
| `v3-no-contract` | CQL v3.0 skill, **no validation contract** | The contract step (PLAN still maps context) |

## Headline metric

**Code-quality lift only.** Judge dimensions D1-D6 and D8-D10 (correctness, tests,
API design, performance, code quality, minimality, README, gestalt). **Exclude D7**
(verification artifacts) from the headline, since it measures process legibility,
not code quality. Report D7 separately as a process-legibility signal.

## Judging

- Two blind LLM judges (different model families, different letter mappings).
- Each judge sees source, tests, README, and machine-check summary.
- Machine checks: build, own-test suite, shared correctness suite (where applicable),
  fresh benchmark on the same box.

## Pruning rule

A component whose ablation shows **no code-quality lift across ≥2 model families**
is a v3.1 cut candidate. If `v3-no-review` shows no quality drop, review is not
load-bearing for current models and should be made optional (not removed). If
`v3-no-contract` shows no quality drop, the validation contract is not load-bearing
and should be simplified.

## Running

```bash
# Fixture smoke (validates plumbing, no live models)
python3 bench/runner.py --ablation --seeds 3 --out /tmp/ablation-fixture-smoke.json

# Live runs: use the same brief + rubric pattern as the existing evals.
# Record host, model, seed, cost, artifacts, and null results for every cell.
```

Live runs must be executed with real model access. Record host, model, seed, cost,
artifacts, and null results for every cell. Commit results under
`bench/results/ablation-YYYY-MM-DD.json`.
