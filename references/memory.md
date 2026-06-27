# Persistent Project Memory

The Coding Quality Loop is stateless across tasks unless this memory layer is on.
Memory holds **distilled lessons only** — crisp conclusions (failure modes, conventions,
gotchas, preferences), never transcripts or diffs. It is read on demand into a hard budget
and written when a lesson is worth keeping. It is advisory: it never replaces tests, review,
or the runtime gates.

## Two capabilities (one interface)

| Capability | What it does | Backends | Default |
|---|---|---|---|
| `lessons_store` | persist + recall lessons | `files`, `honcho` | `files` |
| `graph_relevance` | widen recall + feed CONTEXT MAP from a code graph | `none`, `graphify` | `none` |

Select via `assets/quality-loop.config.example.json` -> `memory`. A missing or offline
adapter degrades to `files` / `none`; a task never blocks on memory infrastructure.

## The contract (backend-agnostic)

- **recall(goal, files, risk, budget)** -> a budget-capped, relevance-scoped digest of prior
  lessons. Files backend: `python3 scripts/quality_loop.py memory-recall --goal "..."
  --files a,b --risk medium --budget 1500`.
- **commit(record [, --lesson])** -> distills `harness_update`, `minimality_decision`, and
  `review_findings` from an agent record into lesson rows. Files backend:
  `python3 scripts/quality_loop.py memory-commit agent-record.json`. The record path is always required; `--lesson` overrides what is distilled from it.
- **prune()** -> dedup + age-out + cap. Files backend:
  `python3 scripts/quality_loop.py memory-prune`.

## Storage

- Default (checked-in): `.quality-loop/memory/lessons.jsonl` + a <=40-line `MEMORY.md`
  index (the only surface a host may auto-load).
- Override (machine-local): `memory.location="local"` -> `~/.quality-loop/<project-slug>/`.
- Paths resolve relative to the **current working directory** — run the CLI from the repo root, or set `memory.location: "local"` to anchor at `~/.quality-loop/<project-slug>/`.
- `graphify-out/` is always gitignored (regenerable cache, not memory).

## Lifecycle wiring (manual, advisory)

- CONTEXT MAP: if `graph_relevance="graphify"`, build/query the graph for the map (see
  `memory-graphify.md`).
- INTAKE / CONTEXT MAP: run `recall` and consider the digest. Recommended, not gated.
- RETROSPECTIVE: run `commit` when a lesson is worth keeping. `verify-gates` stays advisory
  about memory — there is no new hard block.

## Anti-bloat rules

Retrieval, never stuffing. Only the <=40-line `MEMORY.md` auto-loads. Recall is
relevance-scoped (keyword + path-glob + risk) and hard-capped by budget. Store conclusions,
not history. Prune periodically. Hit-counts curate: recalled lessons rise, unused ones age out.

See `memory-honcho.md` and `memory-graphify.md` for the optional backends.
