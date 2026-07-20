# Rust `procmon` A/B eval — Coding Quality Loop vs baseline

**Date**: 2026-07-03
**Task**: Build a Unix process manager in Rust (`procmon`) — CLI with `list`, `find`, `kill`, `watch`, `tree`, `--format json`, direct `/proc` parsing, minimal deps, `cargo build --release`/`cargo test`/`cargo clippy -- -D warnings` all clean.
**Agents**: Codex family (GPT-5) and Claude Code family (Sonnet 4.6), each run twice — once with the `coding-quality-loop` npm package (v2.3.1) installed, once without.
**Judges**: two blind LLM judges (GPT-5 and Gemini 3.1 Pro) scoring 10 dimensions / 100 total.

## Headline result

After correcting a methodology bug (see caveats), CQL variants scored higher than baselines in both families:

| Family | Baseline | +CQL | Lift |
|---|---:|---:|---:|
| Codex (GPT-5) | 71.75 | 75.75 | **+4.00** |
| Claude Code (Sonnet 4.6) | 69.25 | 76.75 | **+7.50** |
| **Overall** | 70.50 | 76.25 | **+5.75** |

Almost all of the numeric lift comes from **D7 — verification artifacts** (the mission docs CQL produces). On the code-quality dimensions (correctness, tests, safety, idiomatic Rust, reviewability), CQL was roughly flat or slightly worse in this run. This is a directional signal about **process legibility**, not code quality.

**This is n=1 per cell. Do not read it as a benchmark.** See caveats before drawing conclusions.

## What was built

Four isolated variants in `variants/`:

- `codex-baseline/` — GPT-5, no skill, raw brief
- `codex-cql/` — GPT-5, with `coding-quality-loop@2.3.1` installed via `npx ... init --host codex`, instructed to follow the lifecycle
- `claude-baseline/` — Sonnet 4.6, no skill, raw brief
- `claude-cql/` — Sonnet 4.6, with `coding-quality-loop@2.3.1` installed via `npx ... init --host claude-code`, instructed to follow the lifecycle

All 4 met the brief's acceptance criteria (`cargo build --release`, `cargo test`, `cargo clippy -- -D warnings` all pass).

## Methodology

### Brief and rubric

- `brief/TASK.md` — the task the agents were given (6 subcommands, `/proc` parsing, minimal deps, no shell-out, integration tests, README ≤2 pages).
- `brief/RUBRIC.md` — 10 dimensions, weighted, /100. Includes two dimensions that could cut either way: D7 (verification artifacts, pro-CQL) and D9 (absence of scope creep, anti-CQL).

### Build phase

Each variant was built by a fresh subagent whose underlying model matched the target CLI (GPT-5 for Codex, Sonnet 4.6 for Claude Code). CQL variants had the skill preloaded and objectives instructing them to run the full lifecycle; baseline variants received the raw brief only.

### Objective machine checks

Ran in each variant directory after the build (see `results/machine-checks.md`):

- `cargo build --release`
- `cargo test`
- `cargo clippy -- -D warnings`
- LOC (src/ and tests/), dep count, README length, presence of mission artifacts

All four passed the acceptance checks as written in the brief. Under stricter `cargo clippy --all-targets -- -D warnings`, `claude-cql` failed with one unused-import error in its integration test file — flagged in the report but not in the acceptance criteria.

### Blind judging

- Two judges (GPT-5, Gemini 3.1 Pro) each scored variants relabelled A/B/C/D under a different shuffle to prevent cross-referencing.
- Judges saw source, tests, README, Cargo.toml, and the machine-check summary. Did not run the code.
- Each judge produced a JSON scorecard: 10 dimensions × 0-10 integer, plus a verdict of `merge_as_is` | `request_changes` | `reject`.

### D7 rescoring (methodology correction)

The initial anonymized copies for both judges accidentally **stripped the `.quality-loop/` artifact directory** from the CQL variants (to prevent trivial de-anonymization by directory listing). This made D7 unmeasurable — every variant scored ~0.5 across the board. A targeted third pass (`results/d7-rescoring.json`) rescored D7 only, with the artifacts visible. That corrected D7 is what feeds the headline totals; the raw per-judge JSONs preserve the original D7 scores untouched for auditability.

## Files in this directory

| Path | What it is |
|---|---|
| `brief/TASK.md` | The task brief given to every agent |
| `brief/RUBRIC.md` | The 10-dimension scoring rubric |
| `variants/{codex,claude}-{baseline,cql}/` | Source, tests, README from each build. CQL variants also include `.quality-loop/` with the mission artifacts. |
| `results/machine-checks.md` | Build/test/clippy/LOC/deps for all four variants |
| `results/judge-1-scores.json` | Judge 1 (GPT-5) raw scorecard |
| `results/judge-2-scores.json` | Judge 2 (Gemini 3.1 Pro) raw scorecard |
| `results/judge-1-mapping.json` | Judge 1's A/B/C/D → variant mapping (kept out of judge context) |
| `results/judge-2-mapping.json` | Judge 2's A/B/C/D → variant mapping |
| `results/d7-rescoring.json` | Corrected D7 scores with artifacts visible |
| `results/aggregated-corrected.json` | Per-variant totals and family lift after D7 correction |
| `results/report.md` | Full write-up with per-dimension breakdown and caveats |

## Caveats — read before quoting

1. **n=1 per cell.** Four builds total. This is directional evidence, not a benchmark. Any single variant randomly having a bad day would move the numbers materially.

2. **Subagent proxy, not real CLIs.** I did not run this inside Claude Code or the Codex CLI. Each variant was built by a Perplexity subagent whose underlying model matched the target (Sonnet 4.6 for Claude family, GPT-5 for Codex family). Same pattern as the existing `examples/sudoku-agent-eval-2026-07-01/` in this repo. The mapping is model-family, not tool-identical. A real Codex or Claude Code session would have different tool defaults, session state, and prompts.

3. **The lift is concentrated in D7.** On D1-D6 and D8-D10, CQL was flat or slightly worse than baseline. D7 alone (weight 10) drives the +5.75 headline. If you don't value artifact production, the number shrinks to near-zero.

4. **Judge disagreement was large on the Claude variants** (17-25 pts between GPT-5 and Gemini). Cross-model judging noise is a real factor here — a single-judge study would have produced a different headline. This is why we ran two.

5. **The rubric was designed to be honest about CQL's failure modes.** D9 (absence of scope creep) penalizes over-engineering; D3 (minimality) penalizes bloated dep lists. CQL didn't lose on these — actually slightly won on D9 — which is worth noting.

6. **The eval was designed and executed by the same person maintaining the skill.** That's a conflict of interest. The judge scorecards and machine checks are reproducible; the report interpretation is not free of bias.

## How to re-run

The build objectives (`brief/objective_baseline.md`, `brief/objective_cql.md`) and judge instructions are preserved verbatim in the eval workspace. To reproduce with different models or with the real Codex/Claude Code CLIs, use the same brief + rubric and repeat the two-judge protocol.
