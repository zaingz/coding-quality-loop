# Project memory

> Most coding agents relearn the same lesson every session. The loop can keep a tiny
> per-project ledger of distilled lessons and recall them on the next task. New in v1.4.0.

<div align="center">

<img src="images/memory-flow.png" alt="Project memory: recall on intake, commit on retrospective, budget-capped and redacted" width="900">

</div>

## What it is

A **per-project ledger** of durable lessons: failure modes, conventions like "no new
dependencies in this module", and gotchas like "this file broke twice for the same
reason". Written down once, recalled every time the same shape of task comes back.

The design constraints are strict, on purpose:

- **Retrieval, not context stuffing.** Only a ≤40-line index auto-loads. Recall is
  budget-capped and scoped to the current task's goal and files.
- **Distilled, not raw transcripts.** A lesson is a short, actionable rule with a
  scope, not a paste of the chat that produced it.
- **Redacted before it is written.** Secrets and boundary keywords are stripped at
  commit time. Nothing sensitive lands in `.quality-loop/memory/`.
- **Advisory, not gating.** Memory adds no new gate. If recall fails or the store is
  empty, the loop runs exactly as it would without memory.
- **Git-diffable and team-shared by default.** The stdlib backend is checked in under
  `.quality-loop/memory/`. A PR can review it like any other file.

## How to use it

```bash
# recall relevant prior lessons before mapping a change
python3 scripts/quality_loop.py memory-recall \
  --goal "fix checkout retry" \
  --files src/payments/charge.py \
  --risk high

# at retrospective, keep a lesson worth remembering
python3 scripts/quality_loop.py memory-commit agent-record.json

# housekeeping: dedupe, age out, cap the ledger
python3 scripts/quality_loop.py memory-prune
```

`memory-recall` respects a **token budget** and scopes results to the goal and files.
`memory-commit` distills a lesson from the record's retrospective and durable-harness
field, redacting secrets before write. `memory-prune` dedupes near-identical lessons,
ages out unused ones, and caps the ledger to keep the index small.

The index is regenerated on every recall and every commit. It stays ≤ 40 lines even with
multi-line lessons — the eval suite pins this invariant.

## The lesson schema

Each lesson is a small JSON object under `.quality-loop/memory/lessons/`, shaped by
[`assets/lesson.schema.json`](../assets/lesson.schema.json):

```jsonc
{
  "id": "2026-06-payments-idempotency",
  "created_at": "2026-06-14T09:12:33Z",
  "scope": {
    "goals": ["retry", "idempotency", "payments"],
    "files": ["src/payments/**", "tests/payments/**"]
  },
  "risk_hint": "high",
  "lesson": "Retry paths in src/payments/ must be idempotent by charge_id. Two prior bugs came from re-charging on partial failure.",
  "source_record": ".quality-loop/records/2026-06-14-charge-retry.json",
  "hits": 3
}
```

Scope and risk hint drive relevance. The `hits` counter is the anti-bloat lever: unused
lessons age out; lessons that keep getting recalled stay.

## Backends

### 1. Files (default, checked-in)

- **What**: stdlib-only. Lessons and index live under `.quality-loop/memory/`.
- **Why**: no dependencies, git-diffable, team-shared, works offline.
- **When**: the default. Turn nothing on. It just works.

## What the eval suite proves

The **memory** eval suite (`python3 evals/run_memory_evals.py`, 27/27 cases) pins:

- The index stays ≤ 40 lines even with multi-line lessons.
- Recall respects the token budget and returns nothing over it.
- Secrets are redacted before they land in a lesson file.
- Concurrency-safe writes (no partial files, no lost updates).
- Prune preserves the newer of two near-identical lessons and ages out zero-hit lessons
  older than the configured window.

## Turning it off

Memory is fully optional. Omit the `memory` block in the config, or delete the
`.quality-loop/memory/` folder, and the loop runs exactly as it did before v1.4.0.

## Design non-goals

- **Not a long-term chat log.** Do not paste raw transcripts. Distill.
- **Not a knowledge base.** For onboarding docs and architecture notes, use `docs/`
  or a wiki.
- **Not a substitute for tests or types.** If a lesson keeps recurring, promote it
  to a rule, a hook, or a test.
