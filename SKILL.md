---
name: coding-quality-loop
description: "Use when a coding agent must turn a software goal, bug, issue, or refactor into a small, verified, independently reviewed code change."
license: MIT
compatibility: "Portable Markdown skill with optional Python helper scripts. Requires git for diff checks; Python 3.10+ for bundled validation utilities."
metadata:
  author: zaingz
  version: "6.3.1"
---

# Coding Quality Loop

Goal: the smallest correct change, with evidence a human can trust, review, revert, or merge. This file is the only always-loaded text. Load `references/` only when needed. Workers never load either.

## Orchestrator Layer

The main session is the **orchestrator**. It thinks hard and makes every decision; workers only execute.

- Orchestrator owns: task class, context map, contract, right-size rung, plan, model routing, verdict on findings, stop-if-unsafe.
- Workers (implementer, reviewer) receive a **brief, not context**: goal, contract slice, files, commands, done-check. One screen max. No skill text, no references, no repository tour.
- Delegate only to frontier models on Claude Code or Codex (see Routing). Droid is a supported install target outside the routed kernel; delegation to Droid is allowed only when an explicit harness routes it. The reviewer must be fresh context and cannot be the implementer. Different-family review is the portable default; an explicit higher-level harness may pin the same model across separate hosts/sessions when deterministic gates and supervisor verification retain final truth.

## Task Class (pick the smallest safe)

- **tiny** — typo, one-liner. Edit, run the smallest check. No artifacts.
- **small** — local bug, one module. Mini map, minimal fix, targeted test.
- **medium** — multi-file, feature, migration, auth/payment/data risk. Contract, plan, right-size gate, independent review, completion record.
- **mission** — multi-day, multi-repo. Orchestrator + workers + validators, shared artifacts in `.quality-loop/`.

Risk trumps size: any change touching a risk boundary (auth, payments, secrets, PII, migrations, upload/download, network, shell, dependencies) is medium+ regardless of diff size. This is the canonical risk-boundary list; every other surface points here.

## Lifecycle

`PLAN -> EXECUTE -> REVIEW`, each phase closed by its gate.
Machine sub-steps (records/configs): `INTAKE`, `EXPLORE`, `MINIMALITY_GATE`, `PLAN` | `IMPLEMENT_SLICE`, `VERIFY` | `REVIEW`, `PACKAGE`, `RETROSPECT`.

**PLAN** — Contract: one-sentence goal, acceptance criteria, constraints, non-goals, assumptions, risk tier, task class, verification plan. Ask only if the answer changes architecture, data safety, security, or user-visible behavior. Map narrowly: entry points, callers, tests, config — findings, not a tour. Medium+: validation contract pairs each acceptance criterion (as an object: `{"criterion": ..., "proving_command": ...}`) with the concrete check that proves it.

**Right-size gate** — choose the highest valid rung (machine enum in parentheses):
`1 no change (skip) · 2 delete (delete) · 3 reuse (reuse) · 4 stdlib (stdlib) · 5 native (native) · 6 installed dependency (existing_dependency) · 7 one-liner (one_liner) · 8 minimal new code (minimal_new_code)`
A new dependency, framework, queue, cache, service, migration, or abstraction must justify why every lower rung fails. Never traded away: security, trust-boundary validation, authorization, accessibility, data-loss protection, required behavior (canonical non-negotiables list). Minimal diff is not minimal architecture — do not monolith; benchmarked hot paths get a worst-case-complexity and p50/p95 commitment at plan time.

**EXECUTE** — one coherent slice at a time. Boring code, existing conventions, small diffs, no speculative abstraction, no unrelated cleanup. Tests move with the behavior. Mark known shortcuts inline with a `cql:` comment naming the ceiling and upgrade path. Verify: smallest sufficient checks first; record exact commands and results; add each command to `.quality-loop/allowed-commands` (one command per line, matched exactly; `#` comments and glob patterns allowed) so `run-evidence` can re-execute it. Bug fix = RED then GREEN. Never weaken, skip, or delete tests to reach green. If a helper script is broken, report and stop — never repair the gate.

**REVIEW** — medium+: a fresh-context reviewer checks the diff against the contract, executes tests when possible (`ran_checks: true|false`), and flags stubs as blocking. Use a different model family by default; an explicit higher-level harness may use the same model only in a separate host/session. The implementer is never the final validator. Security review at any risk boundary (canonical list: §Task Class). User-facing work carries a product floor: keyboard operable, labeled inputs, no `prompt()`/`confirm()` primary flows. Bridge: in-scope findings become fix tasks; out-of-scope findings become follow-ups, not blockers. Before attestation, re-run the right-size gate on the final diff to confirm nothing crept in. `attest-review` is the final act on the diff; any later code edit requires re-attestation. Package: goal, files changed, right-size decision, evidence, risks, rollback, follow-ups. Teardown: PACKAGE archives the record to `docs/records/vX.Y.Z-agent-record.json` and removes the live file, so a record left identical to its content at the resolved base ref is closed and the Stop gate does not re-verify it. After the change merges, record the shipped outcome with `record outcome <clean|regressed|reverted>` — advisory, never a gate, and tallied back into `brief` so the loop learns which releases held.

**RETROSPECTIVE** — every repeated mistake becomes a durable harness change (a rule, a test, a hook, an eval case), never a repeated chat correction. On recurring verification failure, record `repeated_failure: true` and the fix in `harness_update`. A lesson is promoted into a shipped checklist only after it recurs across >=2 distinct tasks; a single-incident lesson goes to project memory, not the checklist.

## Hard Rules

1. Map before edit. 2. Write "done" first (medium+). 3. Existing code before new code. 4. The implementer cannot be the final validator. 5. No success claim without evidence. 6. Don't game the tests — RED then GREEN, never weakened. 7. Stop at risk boundaries. 8. Delete when deletion is the simplest correct solution.

Each hard rule has a deterministic owner; see `references/enforcement-matrix.md`.

## Stock Routing

| Role | Capability class |
|---|---|
| plan / orchestrate | frontier reasoning |
| implement | strong code-specialized |
| independent + security review | strong reasoning, **different family** |
| map / summarize | fast / cheap |

Escalate a model tier only on a recorded failing check — never on a "stuck" or "done" self-report. Record per-role models in `models_used`. Dated model menu and pre-validated variants: `assets/routing/README.md` (apply with `setup-models`, validate with `check-config`).

## Persistent Project Memory (optional, advisory)

`memory-recall` at INTAKE; `memory-commit` at RETROSPECTIVE. Retrieval, not context stuffing; secrets never stored. See `references/memory.md`.

## Session Continuity

Run `brief` at session start; update `.quality-loop/progress.md` at PACKAGE/RETROSPECT.

## Verify (one command)

```bash
python3 scripts/quality_loop.py verify .quality-loop/agent-record.json --red-green
```

`--base` defaults to the auto merge-base of the origin/main ladder (override with the config `base` key or the `QUALITY_LOOP_BASE` env var); pass the flag only to override those. Full command catalog (incl. `memory-*`): `references/tool-contracts.md`. Control plane: opt-in add-on installed via `install.py --with-control-plane`; see `docs/control-plane.md`. Drop-in prompt for skill-less agents: `assets/prompts/drop-in-prompt.md`.

## References (load on demand only)

- `references/lifecycle.md` — detailed states, risk gates, quality gates by task type.
- `references/agentic-orchestration.md` — roles, model heuristics, mission topology, per-platform mapping.
- `references/reviewer-checklists.md` — fresh-context, simplicity, security review prompts.
- `references/tool-contracts.md` — helper command catalog and tool contracts.
- `references/memory.md` — persistent per-project lessons memory.
- `references/enforcement-matrix.md` — deterministic vs advisory enforcement per rule.
