# Live-run recipe (proven 2026-07-07)

The mechanics used by the webapp live eval
(`examples/webapp-agent-eval-2026-07-07/`). Reuse them for ablation cells so
every run is isolated, contamination-checked, and blind-judged the same way.

## Isolation (per arm)

- One fresh git workspace per arm containing only `SPEC.md` (plus `cql/` skill
  bundle for CQL arms: `SKILL.md`, `references/`, `assets/`, and the **complete**
  `scripts/` directory: all four `quality_loop*.py` modules).
- **Codex**: clean `CODEX_HOME` containing only `auth.json` (no user AGENTS.md,
  no user skills). `codex exec -s workspace-write` from the workspace. Delete
  the auth copy after the run.
- **Claude Code**: `claude -p --safe-mode --dangerously-skip-permissions`
  (safe-mode disables user CLAUDE.md, skills, hooks).
- Baseline prompts explicitly ban CQL and nested agent CLIs; verify post-hoc by
  grepping transcripts and checking for `.quality-loop/` artifacts.

## Objective checks (per arm)

1. `npm test` (or the task's test command) plus dependency count.
2. Hidden behaviors exercised through real browser automation (one isolated
   localStorage origin per arm) or the task's held-out suite.
3. `diff-audit` against the initial commit; LOC and load timing.
4. Post-hoc pristine-gate re-run: `verify` with the **repo's** scripts, never
   the workspace copy (the workspace copy may have been modified; compare
   helper-integrity hashes).

## Blind judging

- Two judges from different model families than each other; anonymized packets
  with **different letter mappings per judge**.
- Rename `.quality-loop/` to `process-notes/`; strip `cql/`, `.git/`; scrub
  host/model/vendor identity strings and re-scan until clean.
- Attach a blinded machine-check summary (tests, deps, hidden behaviors, LOC,
  timing). Exclude anything that leaks arm identity (commit counts under a
  sandbox that blocks commits, sandbox notes).
- Headline metric excludes the verification-artifacts dimension (D7); report it
  separately as process legibility.

## Record for every cell

Host + version, model, seed, prompt file, wall time, cost, artifacts location,
and null results. Commit sanitized results only; keep raw workspaces and
transcripts local.
