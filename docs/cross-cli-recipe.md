# Cross-CLI orchestrator recipe (R7)

One page of verified headless commands for running the loop's roles across
harnesses. Verified live on **2026-07-12** with: Claude Code **2.1.207**,
codex-cli **0.144.1**, droid **0.170.0**. Re-verify after CLI upgrades — flags
move.

**The caveat first:** harness diversity does not guarantee model heterogeneity.
A different CLI can host the same model family (Droid's default model is a
Claude model). `check-config` stays the arbiter: it compares the resolved model
*families* across hosts, and `verify-gates` string-compares reviewer ≠
implementer on the record. Declare your topology in `model_routing`
(`agents: {name: {host, class}}` + `main_session`) so the check sees what you
actually run — see `assets/routing/` for pre-validated variants.

## Role → headless command

Prompt cards live in `assets/prompts/`; pipe them in and append the task
context. Every invocation below starts a **fresh session** (no inherited
implementer context) unless you explicitly resume one.

| Role | Command (verified) | Notes |
|---|---|---|
| context mapper | `cat assets/prompts/context-map.md task.md \| claude -p --model haiku` | cheap_fast leg |
| planner | `cat assets/prompts/planner.md task.md \| claude -p --model claude-fable-5` | strong_reasoning leg |
| implementer | `droid exec -m glm-5.2-fast --auto low -f slice-prompt.md` | `-w` runs in a git worktree for isolation; `--auto low` keeps permission checks on |
| verification runner | `droid exec -m glm-5.2-fast --auto low "run: <commands from the validation contract>; record exact output"` | or run the commands yourself — `run-evidence` re-executes them anyway |
| fresh reviewer | `cat assets/prompts/reviewer.md \| codex exec -s read-only -m gpt-5.6-sol` | fresh session, read-only sandbox — the reviewer needs no writes; run inside the repo (codex requires a trusted git dir; close stdin or pipe the card) |
| security reviewer | `cat assets/prompts/security-reviewer.md \| codex exec -s read-only -m gpt-5.6-sol` | boundary changes only |

The implementer needing writes is the reason `codex exec -s workspace-write`
exists; reserve it for a Codex-implementer topology, not for review legs.

## Session and evidence mechanics

- **Fresh sessions:** `claude -p`, `codex exec`, and `droid exec` each start a
  new session per invocation. Droid resumes only with `-s <session-id>`; don't
  pass it for reviewer roles.
- **Exit codes are the evidence:** capture each command's exit code and record
  it in the agent record —

  ```bash
  cat assets/prompts/reviewer.md | codex exec -s read-only -m gpt-5.6-sol; echo "exit=$?"
  ```

  then append the command to `commands_run` with `result: pass|fail` and the
  output as `evidence`, and add it to `.quality-loop/allowed-commands` so
  `run-evidence` can re-execute it. A reviewer verdict goes into
  `independent_review` with `fresh_context: true` and `ran_checks`.
- **Model swaps mid-run:** if the implementer leg escalates (two verified
  failures on the same check), record the event in `escalations` citing the
  failing `commands_run` entries — `verify-gates` rejects escalations that cite
  no recorded failing check — and the per-role models in `models_used`.
- **Codex trust:** `codex exec` refuses untrusted directories; run it from the
  repo root (where `.codex/` lives) or pass `--skip-git-repo-check` only in
  externally sandboxed CI.

## What this recipe is not

It does not make CQL a runtime — these commands are what *you* (or your
supervisor harness) run; CQL supplies the routing data, prompt cards, and the
gates that check what came back.
