---
name: coding-quality-loop
description: "Use when a coding agent must turn a software goal, bug, issue, or refactor into a small, verified, independently reviewed code change."
license: MIT
compatibility: "Portable Markdown skill with optional Python helper scripts. Requires git for diff checks; Python 3.10+ for bundled validation utilities."
metadata:
  author: zaingz
  version: "5.0.0"
---

# Coding Quality Loop

Goal: the smallest correct change, with evidence a human can trust, review, revert, or merge. This file is the only always-loaded text. Load `references/` only when needed. Workers never load either.

## Orchestrator Layer

The main session is the **orchestrator**. It thinks hard and makes every decision; workers only execute.

- Orchestrator owns: task class, context map, contract, right-size rung, plan, model routing, verdict on findings, stop-if-unsafe.
- Workers (implementer, reviewer) receive a **brief, not context**: goal, contract slice, files, commands, done-check. One screen max. No skill text, no references, no repository tour.
- Delegate only to frontier Anthropic and OpenAI models on Claude Code and Codex (see Routing). Reviewer must be a different model family than the implementer.

## Task Class (pick the smallest safe)

- **tiny** — typo, one-liner. Edit, run the smallest check. No artifacts.
- **small** — local bug, one module. Mini map, minimal fix, targeted test.
- **medium** — multi-file, feature, migration, auth/payment/data risk. Contract, plan, right-size gate, independent review, completion record.
- **mission** — multi-day, multi-repo. Orchestrator + workers + validators, shared artifacts in `.quality-loop/`.

## Lifecycle

`PLAN -> EXECUTE -> REVIEW`, each phase closed by its gate.
Machine sub-steps (records/configs): `INTAKE`, `EXPLORE`, `MINIMALITY_GATE`, `PLAN` | `IMPLEMENT_SLICE`, `VERIFY` | `REVIEW`, `PACKAGE`, `RETROSPECT`.

**PLAN** — Contract: one-sentence goal, acceptance criteria, constraints, non-goals, assumptions, risk tier, task class, verification plan. Ask only if the answer changes architecture, data safety, security, or user-visible behavior. Map narrowly: entry points, callers, tests, config — findings, not a tour. Medium+: validation contract pairs each acceptance criterion with the concrete check that proves it.

**Right-size gate** — choose the highest valid rung:
`1 no change · 2 delete · 3 reuse · 4 stdlib · 5 native · 6 installed dependency · 7 one-liner · 8 minimal new code`
A new dependency, framework, queue, cache, service, migration, or abstraction must justify why every lower rung fails. Never traded away: security, trust-boundary validation, authorization, accessibility, data-loss protection, required behavior. Minimal diff is not minimal architecture — do not monolith; benchmarked hot paths get a worst-case-complexity and p50/p95 commitment at plan time.

**EXECUTE** — one coherent slice at a time. Boring code, existing conventions, small diffs, no speculative abstraction, no unrelated cleanup. Tests move with the behavior. Mark known shortcuts inline with a `cql:` comment naming the ceiling and upgrade path. Verify: smallest sufficient checks first; record exact commands and results; add each command to `.quality-loop/allowed-commands` so `run-evidence` can re-execute it. Bug fix = RED then GREEN. Never weaken, skip, or delete tests to reach green. If a helper script is broken, report and stop — never repair the gate.

**REVIEW** — medium+: a fresh-context reviewer in a different model family checks the diff against the contract, executes tests when possible (`ran_checks: true|false`), and flags stubs as blocking. The implementer is never the final validator. Security review at risk boundaries: auth, secrets, payments, PII, migrations, upload/download, network, shell, dependency changes. User-facing work carries a product floor: keyboard operable, labeled inputs, no `prompt()`/`confirm()` primary flows. Bridge: in-scope findings become fix tasks; out-of-scope findings become follow-ups, not blockers. `attest-review` is the final act on the diff; any later code edit requires re-attestation. Package: goal, files changed, right-size decision, evidence, risks, rollback, follow-ups.

**RETROSPECTIVE** — every repeated mistake becomes a durable harness change (a rule, a test, a hook, an eval case), never a repeated chat correction. On recurring verification failure, record `repeated_failure: true` and the fix in `harness_update`.

## Hard Rules

1. Map before edit. 2. Write "done" first (medium+). 3. Existing code before new code. 4. The implementer cannot be the final validator. 5. No success claim without evidence. 6. Don't game the tests — RED then GREEN, never weakened. 7. Stop at risk boundaries. 8. Delete when deletion is the simplest correct solution.

Rules 1–6 are enforced as record-shape or diff-grounded gates by the helper script; see `references/enforcement-matrix.md`.

## Routing (Claude Code + Codex only)

| Role | Model | Host |
|---|---|---|
| plan / orchestrate | Claude Fable 5 (Opus 4.8 to save cost) | Claude Code |
| implement | Claude Sonnet 5 | Claude Code |
| independent + security review | GPT-5.6 Sol (Terra to save cost) | Codex |
| map / summarize | Claude Haiku 4.5 | Claude Code |

Escalate a model tier only on a recorded failing check — never on a "stuck" or "done" self-report. Record per-role models in `models_used`. Pre-validated variants: `assets/routing/` (apply with `setup-models`, validate with `check-config`).

## Persistent Project Memory (optional, advisory)

`memory-recall` at INTAKE; `memory-commit` at RETROSPECTIVE. Retrieval, not context stuffing; secrets never stored. See `references/memory.md`.

## Session Continuity

Run `brief` at session start; update `.quality-loop/progress.md` at PACKAGE/RETROSPECT.

## Control Plane (optional, observability)

Local read-only dashboard over sessions, model calls (exact tokens), spend, routing, and loop artifacts: `control-index` builds a disposable SQLite cache under `.quality-loop/control/`; `control-serve` serves it on 127.0.0.1. Opt-in hooks (`control_plane.enabled`). An index over evidence, never a gate. See `docs/control-plane.md`.

## Verify (one command)

```bash
python3 scripts/quality_loop.py verify agent-record.json --base origin/main --red-green
```

Full command catalog (incl. `memory-*` / `control-*`): `references/tool-contracts.md`. Drop-in prompt for skill-less agents: `assets/prompts/drop-in-prompt.md`.

## References (load on demand only)

- `references/lifecycle.md` — detailed states, risk gates, quality gates by task type.
- `references/agentic-orchestration.md` — roles, model heuristics, mission topology, per-platform mapping.
- `references/reviewer-checklists.md` — fresh-context, simplicity, security review prompts.
- `references/tool-contracts.md` — helper command catalog and tool contracts.
- `references/memory.md` — persistent per-project lessons memory.
- `references/enforcement-matrix.md` — deterministic vs advisory enforcement per rule.
