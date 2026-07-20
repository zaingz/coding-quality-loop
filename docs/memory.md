# Project memory

> Most coding agents relearn the same lesson every session. The loop keeps a tiny
> per-project ledger of distilled lessons and recalls them on the next task.

## What it is

A **per-project ledger** of durable lessons: failure modes, conventions like "no new
dependencies in this module", and gotchas like "this file broke twice for the same
reason". Written down once, recalled every time the same shape of task comes back.

The design constraints are strict, on purpose:

- **Retrieval, not context stuffing.** Only a ≤40-line index auto-loads. Recall is
  budget-capped and scoped to the current task's goal and files.
- **Read-only recall.** Recalling a lesson writes nothing — no hit-count bump, no
  `lessons.jsonl` or `MEMORY.md` rewrite. The working tree stays byte-identical
  (eval-pinned). Hit-bumping is an explicit opt-in (`--bump`) meant for
  RETROSPECT time, when you know which recalled lessons actually helped.
- **Distilled, not raw transcripts.** A lesson is a short, actionable rule with a
  scope, not a paste of the chat that produced it.
- **Redacted before it is written.** Secrets and boundary keywords are stripped at
  commit time. Nothing sensitive lands in `.quality-loop/memory/`.
- **Attributed.** Every row written since v6 carries best-effort provenance
  (`source: {task_id, git_author}`). Recall marks rows without it as
  `[unattributed]` — a cheap poisoning defense: you can see which advice nobody
  signed.
- **Advisory, not gating.** Memory adds no new gate. If recall fails or the store is
  empty, the loop runs exactly as it would without memory.
- **Git-diffable and team-shared by default.** The stdlib backend is checked in under
  `.quality-loop/memory/`. A PR can review it like any other file.

## How to use it

```bash
# recall relevant prior lessons before mapping a change (read-only)
python3 scripts/quality_loop.py memory-recall \
  --goal "fix checkout retry" \
  --files src/payments/charge.py \
  --risk high

# at retrospective: keep a lesson worth remembering, and credit what helped
python3 scripts/quality_loop.py memory-commit .quality-loop/agent-record.json
python3 scripts/quality_loop.py memory-recall --goal "fix checkout retry" --bump

# record how the shipped change fared (surfaced at the next session brief)
python3 scripts/quality_loop.py memory-commit --outcome reverted \
  --note "rolled back: double-charge on retry"

# housekeeping: dedupe, age out, cap the ledger, flag stale scopes
python3 scripts/quality_loop.py memory-prune
```

- `memory-recall` scores lessons against the goal and files and prints a digest
  within a char budget. The budget comes from `--budget` when passed, else from
  `memory.recall_budget_chars` in `quality-loop.config.json` (default 1500) —
  the CLI flag always wins.
- `memory-commit` distills lessons from a record's retrospective fields (or takes
  `--lesson` verbatim), redacts secrets, stamps provenance, and appends to the
  ledger (dedup by id). With `--outcome clean|regressed|reverted [--note ...]` it
  appends a `kind=outcome` row instead.
- `memory-prune` dedupes near-identical lessons, ages out zero-hit lessons past
  the age window, caps the ledger — and prints lessons whose `scope_globs` match
  **zero files in the current tree** as *stale candidates* (flagged for review,
  never auto-deleted).

## Recall: one pool, a floor, and loud provenance

**One pool.** Project lessons (`.quality-loop/memory/`) and cross-project global
lessons (`~/.quality-loop/global/`, written with `memory-commit --global`) compete
in a single ranked pool under one budget. Global lessons get a small constant
score prior instead of a reserved quota, so a non-matching global store never
shrinks project recall. Global rows keep the `[global]` prefix in the digest.

**Relevance floor.** A lesson is recalled only when it shares **≥2 meaningful
tokens** with the goal **or** one of its `scope_globs` matches a named file.
Generic words (`test`, `tests`, `error`, `file`, `code`, `run`, `add`, `use`, …)
are stoplisted, so "fix failing tests" no longer drags in every lesson that
mentions tests once.

**Provenance markers.** Rows lacking a `source` object render with an
`[unattributed]` marker in recall output. Old rows stay valid; they are just
visibly unsigned.

## The lesson schema (lessons.jsonl)

The store is a single JSONL file — `.quality-loop/memory/lessons.jsonl`, one JSON
object per line — plus a regenerated ≤40-line `MEMORY.md` index. Rows are shaped
by [`assets/lesson.schema.json`](../assets/lesson.schema.json):

```jsonc
{
  "id": "1f6f9a2b3c4d",                      // sha1 prefix of the lesson text
  "created": "2026-07-20",                   // ISO date the row was written
  "source_task_id": "t-42",                  // task the lesson came from ("" if none)
  "kind": "failure_mode",                    // failure_mode | convention | gotcha | preference | outcome
  "risk_tier": "high",                       // low | medium | high
  "scope_globs": ["src/payments/**"],        // where the lesson applies
  "keywords": ["idempotent", "retry"],       // lowercase recall tokens
  "lesson": "Retry paths must be idempotent by charge_id.",
  "hits": 3,                                 // bumped only by --bump / retrospect
  "source": {                                // v6 provenance; absent on old rows
    "task_id": "t-42",
    "git_author": "Zain Zafar"
  }
}
```

`kind=outcome` rows additionally carry `"outcome": "clean" | "regressed" |
"reverted"`; their `lesson` field holds the `--note` text. They are shipped-status
feedback for the session brief (`last shipped: reverted — <note>`), and are never
returned by recall.

The `hits` counter is the anti-bloat lever: unused lessons age out at prune time;
lessons that keep earning `--bump` credit stay.

## Backends

### Files (default, checked-in)

- **What**: stdlib-only. `lessons.jsonl` + `MEMORY.md` under `.quality-loop/memory/`.
- **Why**: no dependencies, git-diffable, team-shared, works offline.
- **When**: the default. Turn nothing on. It just works.

A global store at `~/.quality-loop/global/` uses the same format for
cross-project conventions (`memory-commit --global`).

## Coexisting with Claude Code auto-memory

Claude Code keeps its own auto-memory (`MEMORY.md` in the project's Claude
directory). The two stores have different jobs — keep them that way:

- **Claude Code MEMORY.md**: build/environment facts — how to run the tests,
  toolchain quirks, directory layout, credentials *locations* (never values).
- **CQL lessons**: quality-loop conclusions — failure modes, review findings
  worth keeping, minimality preferences, shipped outcomes.

Don't mirror one into the other; a fact in both drifts in one. Combined
injection budget at session start: CQL's brief recalls lessons under an 800-char
budget by default and the CQL index stays ≤40 lines; keep Claude Code's
auto-memory similarly lean (its index is also a ≤40-ish-line file) so the two
together stay under roughly 2 KB of injected context.

## What the eval suite proves

The **memory** eval suite (`python3 evals/run_memory_evals.py`, 32 cases) pins,
among others:

- Default recall leaves the working tree **byte-identical**; `--bump` is the only
  write path, and it works.
- One pool: an empty global store changes nothing; non-matching global lessons
  don't shrink project recall; matching ones merge with the `[global]` prefix.
- The relevance floor and stoplist ("fix failing tests" recalls nothing spurious).
- `--outcome` rows carry provenance and render as `last shipped: …` lines.
- Recall marks unattributed rows; committed rows carry `source`.
- Prune flags stale-scope lessons without deleting them.
- `recall_budget_chars` is honored; an explicit `--budget` wins.
- Secrets are redacted before persistence; the index stays ≤40 lines.

## Turning it off

Memory is fully optional. Omit the `memory` block in the config, or delete the
`.quality-loop/memory/` folder, and the loop runs exactly as it did before v1.4.0.

## Design non-goals

- **Not a long-term chat log.** Do not paste raw transcripts. Distill.
- **Not a knowledge base.** For onboarding docs and architecture notes, use `docs/`
  or a wiki.
- **Not a substitute for tests or types.** If a lesson keeps recurring, promote it
  to a rule, a hook, or a test.
