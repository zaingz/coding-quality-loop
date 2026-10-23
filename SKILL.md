---
name: coding-quality-loop
description: "Use when a coding agent must turn a software goal, bug, issue, or refactor into a small, verified, independently reviewed code change."
license: MIT
compatibility: "Portable Markdown skill with optional Python helper scripts. Requires git for diff checks; Python 3.10+ for bundled validation utilities."
metadata:
  author: zaingz
  version: "6.8.0"
---

# Coding Quality Loop

Goal: the smallest correct change with evidence a human can review, revert, or merge. This is the skill entrypoint; load references only when the task needs them.

## Orchestrator Layer

The main session owns scope, risk, and final decisions. Delegate bounded work with a brief naming the goal, contract slice, files, checks, and done condition. Keep the final review independent of the implementer. For optional worker topology and model routing, see `references/agentic-orchestration.md`.

## Task Classes

- **tiny:** typo or one-liner; edit and run the smallest check, without extra artifacts.
- **small:** local bug or one module; map narrowly, fix, and run targeted checks.
- **medium:** multi-file work, feature, migration, or risk boundary; write a contract and plan, verify, obtain independent review, and record completion.
- **mission:** multi-day or multi-repo work; use bounded slices and shared `.quality-loop/` artifacts.

Risk overrides size: auth, payments (including money math), secrets, cryptography, PII, migrations, destructive operations, production infrastructure, external side effects, concurrency or distributed systems, data loss, upload/download, network, shell, or dependencies make the task medium+ and the risk tier high. This is the canonical risk-boundary list.

## Lifecycle

**Understand:** State the goal, acceptance criteria, constraints, non-goals, assumptions, risk tier, and checks. Ask when an answer changes architecture, safety, security, or visible behavior. Map only relevant entry points, callers, tests, and config. For medium+ records, each acceptance criterion is `{"criterion": ..., "proving_command": ...}`; the command must match a pass-labeled `commands_run` entry.

**Right-Size Gate:** Choose the first safe rung: `skip` (no change), `delete`, `reuse`, `stdlib`, `native`, `existing_dependency`, `one_liner`, `minimal_new_code`. Justify a new dependency or abstraction against smaller options. Preserve security, trust-boundary validation, authorization, accessibility, data-loss protection, and required behavior. Recheck this choice on the final diff before review attestation.

**Change:** Implement one coherent slice using existing conventions. Keep tests with the behavior; never weaken or skip them to get green. Mark a deliberate shortcut with a `cql:` comment naming its limit and upgrade path.

**Check:** Run the smallest sufficient checks and record exact commands and results. `run-evidence` re-executes only commands listed in `.quality-loop/allowed-commands` (one exact command per line; comments and globs are supported). For medium+ work with changed tests, `verify --red-green` replays each proving command against old source plus proposed tests. Put `expected_red` on its pass-labeled `commands_run` row as a literal substring of the intended old failure; an absent or unmatched marker is `not_proven`. Inspect the old output: a matching marker alone cannot prove that the intended assertion ran. The command must pass now. For an already committed failing test, use `bugfix_test: {path, precommitted: true}` and `red_green: true` with `expected_red`. If an installed helper is broken, report it rather than weakening the gate in the consumer project.

**Review:** For medium+ work, use a fresh reviewer to check the final diff against the contract and run checks when possible. Prefer a different model family. If only one family is available, medium work may record `same_family_fallback: true` with a reason and report `REVIEW NOT INDEPENDENT`; high-risk work cannot use that fallback. Review security at a risk boundary. For user-facing changes, check keyboard use, input labels, and primary flows without `prompt()`/`confirm()`. Resolve in-scope findings, then run `attest-review` on the final diff; edits after attestation require a new attestation. Package the changed files, evidence, risks, rollback, and follow-ups. See `references/lifecycle.md` for record teardown and shipped-outcome tracking.

**RETROSPECTIVE:** Turn repeated mistakes into a tested rule, hook, or eval; keep one-off lessons in project memory. See `references/lifecycle.md`.

## Hard Rules

Map before editing; define done before medium+ work; prefer existing code; keep final review separate from implementation; support claims with evidence; do not game tests; stop at risk boundaries; delete when deletion is simplest. The limits of deterministic enforcement are in `references/enforcement-matrix.md`.

## Stock Routing

Use `assets/routing/README.md` for dated model presets; `setup-models` applies them and `check-config` checks their structure, not live access. Escalate after a recorded failing check, and record per-role models in `models_used`. Optional host and worker details are in `references/agentic-orchestration.md`.

## Persistent Project Memory (optional, advisory)

Use `memory-recall` at intake and `memory-commit` at retrospective when persistent project memory helps. Do not store secrets. See `references/memory.md`.

## Session Continuity

Run `brief` at session start. Before handoff or compaction, record the last verified slice, checks, open risks, and `next_action` in the record or `.quality-loop/progress.md`. On resume, recheck the current diff and evidence; inspect the outcome of an interrupted external side effect before retrying it.

## Verify

With the full runtime installed, run:

```bash
python3 scripts/quality_loop.py verify .quality-loop/agent-record.json --red-green
```

`--base` overrides `QUALITY_LOOP_BASE`, config `base`, then automatic merge-base discovery. A manual skill copy does not install the helper scripts. See `references/tool-contracts.md` for commands, `docs/control-plane.md` for the optional add-on, and `assets/prompts/drop-in-prompt.md` for a skill-less prompt.

## References (load on demand)

- `references/lifecycle.md` — states and task gates.
- `references/agentic-orchestration.md` — roles, routing, and host mapping.
- `references/reviewer-checklists.md` — review prompts.
- `references/tool-contracts.md` — helper commands and prerequisites.
- `references/memory.md` — optional project memory.
- `references/enforcement-matrix.md` — deterministic and advisory rules.
