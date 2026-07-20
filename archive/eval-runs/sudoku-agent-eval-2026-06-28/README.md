# Sudoku Agent Evaluation — 2026-06-28

A committed proof that the `coding-quality-loop` skill improves coding-agent output. Four agent
variants built the **same** local browser Sudoku app from identical requirements; an orchestrator
reran every test suite and a real-browser smoke test, and three independent judges scored each
variant on a fixed 100-point rubric.

The full writeup — setup, rubric, per-judge scores, findings, and recommended harness
improvements — is in [`evaluation-report.md`](evaluation-report.md).

For the newer six-arm live run across Codex, Claude Code, and Droid/GLM-5.2, see
[`../sudoku-agent-eval-2026-07-01/`](../sudoku-agent-eval-2026-07-01/).

## Result

| Rank | Variant | Skill? | Tests | Avg judge score |
|---:|---|---|---:|---:|
| 1 | `openai_skill` | yes | 17/17 | 93.0 |
| 2 | `claude_skill` | yes | 9/9 | 88.7 |
| 3 | `openai_baseline` | no | 12/12 | 86.3 |
| 4 | `claude_baseline` | no | 11/11 | 80.3 |

The two skill variants averaged **90.8** versus **83.3** for the two baselines — a ~7.5-point lift,
driven by stronger pre-implementation clarity, more robust MRV solvers, better verification
evidence, and easier reviewability.

## What's here

```text
sudoku-agent-eval-2026-06-28/
├── evaluation-report.md   # consolidated report: setup, rubric, scores, findings
├── claude_skill/          # Claude-style agent WITH the skill
│   ├── app/               #   app source + node --test suite
│   └── artifacts/         #   lifecycle artifacts (contract, plan, review, completion, ...)
├── openai_skill/          # OpenAI-style agent WITH the skill
│   ├── app/
│   └── artifacts/
├── claude_baseline/       # Claude-style agent WITHOUT the skill
│   └── app/
└── openai_baseline/       # OpenAI-style agent WITHOUT the skill
    └── app/
```

Only the skill variants were required to produce lifecycle artifacts (task contract, context map,
validation contract, plan, execution log, decision log, independent review, completion record), so
the baselines ship app source only.

## Rerun the proof

Each app is dependency-free and tested with the Node built-in test runner:

```bash
for v in claude_skill openai_skill claude_baseline openai_baseline; do
  echo "== $v =="; npm test --prefix "$v/app"
done
```

Expected: `9`, `17`, `11`, and `12` passing tests respectively. To play any variant, open its
`app/index.html` in a browser (or run its `npm start`, where defined).
