# Persistent Project Memory

The Coding Quality Loop is stateless across tasks unless this memory layer is on.
Memory holds **distilled lessons only** — crisp conclusions (failure modes, conventions,
gotchas, preferences), never transcripts or diffs. It is read on demand into a hard budget
and written when a lesson is worth keeping. It is advisory: it never replaces tests, review,
or the runtime gates.

## Capability

| Capability | What it does | Backend |
|---|---|---|
| `lessons_store` | persist + recall lessons | `files` |

Select via `assets/quality-loop.config.example.json` -> `memory`.

## The contract

- **recall(goal, files, risk, budget)** -> a budget-capped, relevance-scoped digest of
  prior lessons. **Read-only by default**: recalling writes nothing — no hit-count bump,
  no `lessons.jsonl` or `MEMORY.md` rewrite; the working tree stays byte-identical.
  Files backend: `python3 scripts/quality_loop.py memory-recall --goal "..."
  --files a,b --risk medium --budget 1500`. Add `--bump` (RETROSPECT-time opt-in)
  to credit the recalled lessons that actually helped.
- **commit(record [, --lesson])** -> distills `harness_update`, `minimality_decision`, and
  `review_findings` from an agent record into lesson rows, redacts secrets, and stamps
  best-effort provenance (`source: {task_id, git_author}`). Files backend:
  `python3 scripts/quality_loop.py memory-commit agent-record.json`. With `--lesson`, the
  record path is optional (a manual lesson needs no record).
- **commit --outcome clean|regressed|reverted [--note ...]** -> records how shipped work
  fared as a `kind=outcome` row (surfaced by the next session brief as
  `last shipped: ...`; never returned by recall):
  `python3 scripts/quality_loop.py memory-commit --outcome reverted --note "rolled back: ..."`.
- **commit --global** -> writes to the cross-project global store
  (`~/.quality-loop/global/`) instead of the project store. Use for user-level
  conventions and preferences that apply across all projects:
  `python3 scripts/quality_loop.py memory-commit --lesson "<lesson>" --kind convention --global`.
- **prune()** -> dedup + age-out + cap, and flags lessons whose `scope_globs` match zero
  files in the current tree as *stale candidates* (flagged for review, never auto-deleted).
  Files backend: `python3 scripts/quality_loop.py memory-prune`. Add `--global` to prune
  the global store.

## Storage

- Default (checked-in): `.quality-loop/memory/lessons.jsonl` + a <=40-line `MEMORY.md`
  index (the only surface a host may auto-load).
- Row shape (one JSON object per line): `id`, `created`, `source_task_id`,
  `kind` (`failure_mode|convention|gotcha|preference|outcome`), `risk_tier`, `scope_globs`,
  `keywords`, `lesson`, `hits`, and (since v6) `source` provenance
  (`{task_id, git_author}`). Recall renders rows without `source` as
  `[unattributed]` — a cheap poisoning defense. Lesson text is
  whitespace-collapsed and secret-redacted before write; malformed or empty rows are
  skipped on load, never fatal. Full schema: `assets/lesson.schema.json`.
- Override (machine-local): `memory.location="local"` -> `~/.quality-loop/<project-slug>/`.
- Global (cross-project): `~/.quality-loop/global/lessons.jsonl` — user-level conventions
  and preferences that apply across all projects. Recall merges project + global lessons
  into a **single ranked pool under ONE budget** (global rows get a small constant score
  prior, not a reserved quota, and keep a `[global]` prefix in the digest — a non-matching
  global store never shrinks project recall).
- Paths resolve relative to the **current working directory** — run the CLI from the repo root, or set `memory.location: "local"` to anchor at `~/.quality-loop/<project-slug>/`.

## Lifecycle wiring (manual, advisory)

- INTAKE / CONTEXT MAP: run `recall` and consider the digest. Recommended, not gated.
- RETROSPECTIVE: run `commit` when a lesson is worth keeping, `commit --outcome` when
  shipped-work status is known, and `recall --bump` to credit the lessons that helped.
  `verify-gates` stays advisory about memory — there is no new hard block.

## Anti-bloat rules

Retrieval, never stuffing. Only the <=40-line `MEMORY.md` auto-loads. Recall is
relevance-scoped (keyword + path-glob + risk) with a relevance floor — a lesson needs >=2
meaningful shared tokens with the goal or a `scope_globs` match against a named file
(generic words are stoplisted) — and hard-capped by budget. Store conclusions, not
history. Prune periodically. Hit-counts curate: lessons that keep earning `--bump` credit
at RETROSPECT stay; unused ones age out (recall itself never increments anything).
