# AGENTS.md

Baseline, command-first repo instructions for coding agents. Keep it short and accurate —
short, accurate guidance beats long, vague guidance. Fill the placeholders, delete what does
not apply. Read by Codex (`AGENTS.md`), and a good base for Claude Code (`CLAUDE.md`) and
Cursor (`.cursor/rules`).

## Commands

```bash
# install
<install command, e.g. npm ci | uv sync | go mod download>
# test
<test command, e.g. npm test | pytest | go test ./...>
# typecheck
<typecheck command, e.g. tsc --noEmit | mypy . >
# lint
<lint command, e.g. eslint . | ruff check . >
# build
<build command, e.g. npm run build | make>
```

Run the relevant checks before claiming a task is done. Green tests are necessary, not sufficient.

## How To Work Here

Follow the Coding Quality Loop: produce the smallest correct change with enough evidence to
trust, review, revert, or merge it.

`INTAKE -> CONTEXT MAP -> SPEC/VALIDATION CONTRACT -> COMPLEXITY BRAKE -> PLAN -> IMPLEMENT IN SMALL SLICES -> VERIFY -> INDEPENDENT REVIEW -> SHIP/HANDOFF -> RETROSPECTIVE`

- Pick the smallest safe task class (tiny/small/medium/mission).
- Prefer deletion, reuse, stdlib, and native features before new code or new dependencies.
- Keep diffs small and in existing conventions; no speculative abstraction, no unrelated cleanup.
- For non-trivial work: write a validation contract first, get an independent review, ship a completion record.

## Stop Conditions (escalate, do not proceed)

- Destructive migrations or data deletion.
- Secrets, credentials, or auth-policy changes.
- Payments, billing, production infrastructure, or irreversible external side effects.
- New dependencies without justification.
- Ambiguous user-facing behavior, or repeated verification failure after two repair attempts.

## Project memory (optional, advisory)

- Recall prior lessons before mapping a change:
  `python3 scripts/quality_loop.py memory-recall --goal "<goal>" --files <changed,files> --risk <low|medium|high>`
- Commit a durable lesson at retrospective:
  `python3 scripts/quality_loop.py memory-commit agent-record.json`
- Lessons live in `.quality-loop/memory/`. Writes are advisory; never store secrets as lessons.

## Project-Specific Notes

- <conventions, gotchas, protected paths, deploy notes>
