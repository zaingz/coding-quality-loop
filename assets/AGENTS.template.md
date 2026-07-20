# AGENTS.md

Command-first repo instructions for coding agents. Short and accurate beats long and vague. Fill the placeholders, delete what does not apply. Read by Codex (`AGENTS.md`); a good base for Claude Code (`CLAUDE.md`) and Cursor (`.cursor/rules`).

## Commands

```bash
# install
<install command, e.g. npm ci | uv sync>
# test
<test command, e.g. npm test | pytest>
# typecheck
<typecheck command, e.g. tsc --noEmit | mypy .>
# lint
<lint command, e.g. eslint . | ruff check .>
# build
<build command, e.g. npm run build | make>
```

Run the relevant checks before claiming done. Green tests are necessary, not sufficient.

## How To Work Here

Follow the Coding Quality Loop: smallest correct change, with evidence to trust, review, revert, or merge. `PLAN -> EXECUTE -> REVIEW`, each closed by its gate. Sub-steps: `INTAKE`, `EXPLORE`, `MINIMALITY_GATE`, `PLAN` | `IMPLEMENT_SLICE`, `VERIFY` | `REVIEW`, `PACKAGE`, `RETROSPECT`.

- Pick the smallest safe task class (tiny/small/medium/mission).
- Deletion, reuse, stdlib, native before new code or new dependencies.
- Small diffs in existing conventions; no speculative abstraction, no unrelated cleanup.
- Non-trivial work: validation contract first, independent review, completion record.

## Stop Conditions (escalate, do not proceed)

- Destructive migrations or data deletion.
- Secrets, credentials, or auth-policy changes.
- Payments, billing, production infrastructure, irreversible external side effects.
- New dependencies without justification.
- Ambiguous user-facing behavior, or repeated verification failure after two repair attempts.

## Project Memory (optional, advisory)

- Recall before mapping: `python3 scripts/quality_loop.py memory-recall --goal "<goal>" --files <changed,files> --risk <low|medium|high>`
- Commit a lesson at retrospective: `python3 scripts/quality_loop.py memory-commit .quality-loop/agent-record.json`
- Lessons live in `.quality-loop/memory/` (project) and `~/.quality-loop/global/` (cross-project). Never store secrets.

## Session Continuity

- Session start: `python3 scripts/quality_loop.py brief`.
- At PACKAGE / RETROSPECT: update `.quality-loop/progress.md`; leave the repo clean and committable.

## Project-Specific Notes

- <conventions, gotchas, protected paths, deploy notes>
