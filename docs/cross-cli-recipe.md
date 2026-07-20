# Cross-CLI orchestrator recipe (R7)

One page of verified headless commands for running the loop's routed kernel —
**Claude Code as implementer, Codex as the independent reviewer**. Verified live
on **2026-07-12** with: Claude Code **2.1.207**, codex-cli **0.144.1**.
Re-verify after CLI upgrades — flags move.

**The caveat first:** harness diversity does not guarantee model heterogeneity.
A different CLI can host the same model family. `check-config` stays the
arbiter: it compares the resolved model *families* across hosts, and
`verify-gates` string-compares reviewer ≠ implementer on the record. Declare
your topology in `model_routing` (`agents: {name: {host, class}}` +
`main_session`) so the check sees what you actually run — see `assets/routing/`
for pre-validated variants.

## Role → headless command

Prompt cards live in `assets/prompts/`; pipe them in and append the task
context. Every invocation below starts a **fresh session** (no inherited
implementer context) unless you explicitly resume one.

| Role | Command (verified) | Notes |
|---|---|---|
| context mapper | `cat assets/prompts/context-map.md task.md \| claude -p --model haiku` | cheap_fast leg |
| planner | `cat assets/prompts/planner.md task.md \| claude -p --model claude-fable-5` | strong_reasoning leg |
| implementer | `cat assets/prompts/implementer.md slice-prompt.md \| claude -p --model claude-fable-5` | the main-session leg; run in a git worktree for isolation on parallel slices |
| verification runner | run the validation-contract commands yourself and record exact output | `run-evidence` re-executes them from the allowlist anyway |
| fresh reviewer | `python3 scripts/quality_loop.py render-prompt --role reviewer --record agent-record.json \| codex exec -s read-only -m gpt-5.6-sol` | fresh session, read-only sandbox — the reviewer needs no writes; run inside the repo (codex requires a trusted git dir; close stdin or pipe the prompt) |
| security reviewer | `python3 scripts/quality_loop.py render-prompt --role security-reviewer --record agent-record.json \| codex exec -s read-only -m gpt-5.6-sol` | boundary changes only |

`render-prompt` substitutes `{contract}`/`{diff}`/`{evidence}` from the record
into the prompt card, so the reviewer receives the actual contract slice and
diff instead of a raw template (`--base` defaults to the auto merge-base).

### One user's setup (not shipped): the agent-os override

**This is one user's personal harness, not part of the CQL package** — the
`droid-glm-exec` / `codex-exec` wrappers below are not shipped here. It is kept
as a worked example of an explicit higher-level harness owning model selection.
When such a harness (here, "agent-os") is active, it owns model selection and
replaces the stock routing table: Fable/max planning → Droid/GPT-5.6 Sol/high
implementation → fresh Codex/GPT-5.6 Sol/xhigh review. CQL `model_routing`
stays host-neutral rather than claiming model heterogeneity.

| Role | Command (user-local wrappers, not shipped) | Effective route |
|---|---|---|
| planner | `cat assets/prompts/planner.md task.md \| claude -p --model claude-fable-5 --effort max --permission-mode plan` | Fable/max; one fresh Sol/max planning attempt after a benign safeguard refusal |
| implementer | `droid-glm-exec --cwd "$PWD" --mode patch --allow-shell --prompt-file slice-prompt.md` | Droid/GPT-5.6 Sol/high |
| verification runner | `droid-glm-exec --cwd "$PWD" --mode verify --prompt-file verify-prompt.md` | Droid/GPT-5.6 Sol/high |
| fresh or security reviewer | `codex-exec --cwd "$PWD" --mode review --prompt-file reviewer-prompt.md` | fresh Codex/GPT-5.6 Sol/xhigh, read-only |

This same-model implementation/review route is an explicit same-model,
separate-host/session exception — it is not model heterogeneity. Fresh
context, separate hosts, a non-editing reviewer, deterministic gates, and
supervisor verification remain mandatory and provide the independence boundary.

The reviewer legs run read-only; `codex exec -s workspace-write` exists for a
Codex-implementer topology, not for review legs.

## Session and evidence mechanics

- **Fresh sessions:** `claude -p` and `codex exec` each start a new session per
  invocation; don't resume a session for reviewer roles — the reviewer must
  arrive with fresh context.
- **Exit codes are the evidence:** capture each command's exit code and record
  it in the agent record —

  ```bash
  python3 scripts/quality_loop.py render-prompt --role reviewer --record agent-record.json |
    codex exec -s read-only -m gpt-5.6-sol; echo "exit=$?"
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
