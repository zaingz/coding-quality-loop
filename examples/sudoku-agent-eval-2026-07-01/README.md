# Live Sudoku Agent Evaluation - 2026-07-01

Six live agent arms built the same local browser Sudoku app from an identical
`SPEC.md`: Codex, Claude Code, and Droid/GLM-5.2, each with and without the
Coding Quality Loop. The CQL arms received the same `CQL.md` instructions. The
baseline prompts explicitly banned CQL, Droid/subagents, nested agent CLIs, and
external coding agents after an initial contaminated Codex baseline attempt was
stopped and restarted.

## Result

All six arms completed successfully, used zero dependencies, passed `npm test`,
and reached the machine heuristic score of `100/100`. Differentiation came from
two blind LLM judges, Claude and Codex, scoring anonymized source packets and
machine-check summaries on the same 100-point rubric.

| Rank | Arm | CQL? | Tests | Claude judge | Codex judge | Avg |
|---:|---|---|---:|---:|---:|---:|
| 1 | `claude_cql` | yes | 22 | 96 | 98 | 97.0 |
| 2 | `claude_baseline` | no | 45 | 91 | 94 | 92.5 |
| 3 | `droid_cql` | yes | 12 | 84 | 90 | 87.0 |
| 4 | `codex_cql` | yes | 5 | 80 | 89 | 84.5 |
| 5 | `codex_baseline` | no | 4 | 79 | 88 | 83.5 |
| 6 | `droid_baseline` | no | 18 | 72 | 86 | 79.0 |

CQL average: **89.5**. Baseline average: **85.0**. Lift: **+4.5 points**.

Per-agent CQL delta:

| Agent | Baseline | CQL | Delta |
|---|---:|---:|---:|
| Codex | 83.5 | 84.5 | +1.0 |
| Claude Code | 92.5 | 97.0 | +4.5 |
| Droid/GLM-5.2 | 79.0 | 87.0 | +8.0 |

Both LLM judges produced the same ranking:

1. `claude_cql`
2. `claude_baseline`
3. `droid_cql`
4. `codex_cql`
5. `codex_baseline`
6. `droid_baseline`

## What the Scores Mean

This run supports the narrower claim that CQL improved reviewability and judged
quality in a one-seed live Sudoku task, especially for Droid and Claude Code. It
does not prove a durable benchmark lift by itself.

Important caveats:

- Single task, single seed.
- All arms passed the broad machine checks, so the lift is from source/process
  review, not hidden-test separation.
- No real browser automation was run; browser smoke is recorded as not verified
  because no repo-local Playwright/browser runner was available.
- Judges were LLMs, not humans; they were blind to builder identity and arm
  mapping, but still subjective.
- Raw run workspaces and judge packets were kept under ignored `.quality-loop`
  run artifacts, not committed.

The sanitized result data is in [`results.json`](results.json).
