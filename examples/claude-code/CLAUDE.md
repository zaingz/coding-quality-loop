# Coding Quality Loop (Claude Code)

This project follows the Coding Quality Loop. Produce the smallest correct change with
enough evidence that a human can trust, review, revert, or merge it.

Lifecycle: `INTAKE -> EXPLORE -> MINIMALITY_GATE -> PLAN -> IMPLEMENT_SLICE -> VERIFY -> REVIEW -> PACKAGE`.

- **INTAKE**: turn the goal into acceptance criteria, constraints, assumptions, a risk tier
  (`low|medium|high`), and a verification plan. Ask only if a missing answer changes
  architecture, data safety, security, cost, side effects, or user-visible behavior.
- **EXPLORE / PLAN**: map only the relevant files, callers, tests, and config. Name the
  files you expect to change and the checks you will run.
- **MINIMALITY_GATE**: pick the highest valid rung — no change, delete, reuse, stdlib,
  native, existing dependency, one-liner, minimal new code. Never drop security, validation,
  authorization, accessibility, or data-loss protection for the sake of minimality.
- **IMPLEMENT_SLICE**: one small, reviewable slice using existing conventions.
- **VERIFY**: run the smallest sufficient checks, then broader checks if risk warrants.
  Record exact commands and results. Green tests are necessary, not sufficient.
- **REVIEW**: for non-trivial work, review the diff in a **fresh context / subagent** against
  the original contract.
- **PACKAGE**: hand off goal, files changed, minimality decision, verification evidence,
  risks, rollback, and follow-ups.

Escalate before destructive migrations, secret/credential exposure, payments/billing,
production infra, ambiguous user-facing behavior, or after two failed repair loops.

## Agentic routing

Run REVIEW as a separate subagent so it does not inherit the implementer's confidence. Use a
strong-reasoning model for PLAN/MINIMALITY_GATE and a code-specialized model for
IMPLEMENT_SLICE. Enforce non-negotiable blocks (secrets, destructive migrations, auth/billing)
with `.claude/settings.json` `PreToolUse` / `Stop` hooks — see
https://docs.anthropic.com/en/docs/claude-code/hooks

Install project hooks and read-only reviewer agents with:

```bash
python3 scripts/install.py --host claude-code
```

Hooks are advisory by default. Set `.quality-loop/config.json` to
`{"enforcement": "required"}` to block medium/high edits before PLAN +
MINIMALITY_GATE.

Keep this file concise; prefer path-scoped `.claude/rules/` as instructions grow
(https://docs.anthropic.com/en/docs/claude-code/memory).

## One-line usage

```bash
claude "Follow the Coding Quality Loop to fix the invoice rounding bug and open a PR."
```
