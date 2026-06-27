# Persistent Per-Project Memory for the Coding Quality Loop

**Status:** Approved design (2026-06-27)
**Author:** Zain (with Claude)
**Scope:** Add a persistent, per-project memory subsystem to the `coding-quality-loop` skill, with two optional loop-integrated backends (Honcho, Graphify), without bloating agent context and without breaking the dependency-free, portable core.

---

## 1. Problem / Gap

The Coding Quality Loop is **stateless across tasks**. Every task produces a standalone
`agent-record.json` and ephemeral mission artifacts, then forgets everything. Three concrete gaps:

1. **No persistent, queryable per-project store.** A lesson learned in task *N* is invisible to task
   *N+1* unless a human hand-edits `AGENTS.md` / `CLAUDE.md`. The "durable harness changes over chat
   corrections" value is enforced only *within* a single task (via `verify-gates` requiring
   `harness_update` when `repeated_failure` is set) and never carried forward.
2. **No recall path.** Nothing reads prior outcomes at INTAKE / CONTEXT MAP to warn "this module
   broke twice before", "this codebase forbids new dependencies", or "the last migration here needed
   a backfill".
3. **The RETROSPECTIVE `harness_update` is prose nobody re-applies.** It is an attestation, not a
   persisted, recallable fact.

The fix is a memory layer that is **written at the right moment** and **read on demand into a tiny
budget**, wired into the existing record + `verify-gates` + eval machinery rather than bolted beside
it.

## 2. Non-negotiables (inherited from the project)

- **Dependency-free core.** The always-on default tier must be 100% Python stdlib.
- **Portable by construction.** Works identically across Claude Code, Codex, Cursor, Pi, standalone.
- **Anti-bloat.** Retrieval, never stuffing. The only auto-loaded surface is a tiny index.
- **Progressive disclosure.** Detail is paged in by key, never loaded whole.
- **Single Agent Skill package.** The repo stays one skill (root `SKILL.md` + sibling folders);
  no nested independently-triggerable sub-skills that would fragment the package or fire on
  unrelated prompts.

## 3. Decisions (locked with user)

| Fork | Decision |
|---|---|
| Backend tiers | **Files core + build both adapters** (Honcho, Graphify). |
| Storage location | **Checked-in default** (`.quality-loop/memory/`), **machine-local override** via config. |
| Memory scope | **Distilled lessons only** (no repo-map cache as memory, no `agent-record.json` archive). |
| Write trigger | **Manual / agent-decides.** Writes happen at RETROSPECTIVE when the agent judges a lesson worth keeping. `verify-gates` stays **advisory** about memory (no new hard block). |
| Packaging | **Bundled in this repo.** |
| Coupling | **Loop-integrated only** — backends are components of the loop's memory interface, not standalone skills. |

### 3.1 Key reconciliation: Graphify vs. lessons-only

Graphify is a *code-graph / repo-map* tool, not a lessons store. "Build both adapters" + "lessons
only" is reconciled by splitting the interface into **two orthogonal capabilities**:

- **lessons-store** — persists and recalls distilled lessons. Backends: `files` (default) | `honcho`.
- **graph-relevance** — an *optional enricher* that maps changed files to related code entities so
  recall pulls lessons tagged to *related* code (not just literal path matches), and feeds the
  CONTEXT MAP step. Backends: `none` (default) | `graphify`.

Graphify therefore never stores lessons; it amplifies relevance and accelerates the context map.

## 4. Architecture

```
                         ┌─────────────────────────────────────────────┐
                         │  SKILL.md  "Persistent Project Memory" §      │
                         │  lifecycle wiring: CONTEXT MAP / INTAKE /     │
                         │  RETROSPECTIVE  (manual, advisory)            │
                         └───────────────┬─────────────────────────────┘
                                         │ instructs
              ┌──────────────────────────┼───────────────────────────────┐
              ▼                          ▼                                ▼
   ┌────────────────────┐   ┌──────────────────────────┐   ┌──────────────────────────┐
   │ lessons-store: files│   │ lessons-store: honcho     │   │ graph-relevance: graphify │
   │ quality_loop.py     │   │ references/memory-honcho  │   │ references/memory-graphify│
   │ (stdlib, det.)      │   │ agent drives Honcho MCP   │   │ agent drives graphify CLI │
   │ recall/commit/prune │   │ search/conclusions/msgs   │   │ +MCP; populates repo_map  │
   └─────────┬──────────┘   └─────────────┬────────────┘   └─────────────┬────────────┘
             │                            │                              │
             ▼                            ▼                              ▼
   .quality-loop/memory/         configured Honcho            graphify-out/ (gitignored,
   lessons.jsonl + MEMORY.md     workspace/peer/session       regenerable cache)
```

- The **contract** (recall / commit / prune semantics) is backend-agnostic, defined once in
  `references/memory.md`. `files` is the reference implementation and the offline eval target.
- **Selection** via `assets/quality-loop.config*.json` → a new `memory` block. A missing or offline
  adapter **degrades gracefully** to `files` / `none`; a task never blocks on memory infrastructure.
- The engine for the default tier lives entirely in the stdlib CLI, so hosts call it inline. Honcho
  and Graphify are reached through MCP/CLI tools the **agent** invokes per the reference modules
  (a stdlib Python script cannot call MCP), which is exactly why they are documented as skill-style
  modules rather than script functions.

## 5. Store layout & lesson schema

### 5.1 Location
- **Default (checked-in):** `.quality-loop/memory/`
  - `lessons.jsonl` — append-only, one lesson per line, human-diffable, PR-reviewable.
  - `MEMORY.md` — auto-generated slim index, **≤ 40 lines** (mirrors Claude Code's
    ≤200-line/25KB auto-load rule). Lists the top-N most-relevant / most-hit lessons. The only
    surface a host may auto-load.
- **Override (machine-local):** `memory.location = "local"` → `~/.quality-loop/<project-slug>/`,
  where `<project-slug>` = absolute cwd path with non-alphanumeric characters replaced by `-`
  (same convention Claude Code uses). No repo noise; lost on clone; not team-shared.
- **Graphify cache:** `graphify-out/` — always **gitignored** (large, regenerable), independent of
  the lessons location.

### 5.2 Lesson row (`assets/lesson.schema.json`)
```json
{
  "id": "string (stable, content-derived or uuid)",
  "created": "ISO-8601 date",
  "source_task_id": "string (provenance: which agent-record produced it)",
  "kind": "failure_mode | convention | gotcha | preference",
  "risk_tier": "low | medium | high",
  "scope_globs": ["src/payments/**", "..."],
  "keywords": ["retry", "idempotency", "..."],
  "lesson": "one crisp sentence; a conclusion, not a transcript",
  "hits": 0
}
```
- Only distilled conclusions are stored — never raw diffs, transcripts, or full records.
- `hits` increments when a lesson is recalled and surfaced, enabling a self-curation loop
  (never-recalled lessons age out during prune).

## 6. CLI surface (files backend — stdlib, eval-pinned)

New `scripts/quality_loop.py` subcommands:

- `memory-recall --goal "<g>" --files a,b,c --risk medium --budget 1500 [--location ...] [--json]`
  Scores lessons by keyword overlap (`difflib`), path-glob match against changed files (`fnmatch`),
  and risk-tier match. Returns the top-N within a **hard char/token budget**, truncating
  lowest-scored items first. Bumps `hits` on returned rows. Prints a compact digest (or JSON).
- `memory-commit <agent-record.json> [--lesson "<text>" --kind ... --scope ... ]`
  Distills the record's `harness_update`, `review_findings`, and `minimality_decision` into one or
  more lesson rows; appends to `lessons.jsonl`; regenerates `MEMORY.md`. Agent-invoked.
- `memory-prune [--max N] [--max-age-days D]`
  Dedups near-identical lessons (difflib ratio threshold) and caps the set by recency + `hits`.
- `memory-status`
  Reports active backends (from config), lesson count, index freshness, and any adapter that is
  configured but unreachable (so the fallback is visible).

All subcommands are deterministic, stdout-only, and never require network or third-party packages.

## 7. Backend modules

### 7.1 `references/memory-honcho.md` (lessons-store: honcho)
- **Config:** `{ workspace_id, peer_id, session_template, target_peer }` — fully config-driven so it
  slots into whatever Honcho governance the host already has. (E.g., a workspace whose rules forbid
  creating new peer IDs: the adapter uses the configured peer, never invents one.)
- **Recall (INTAKE):** `search` / `query_conclusions` scoped to the configured peer/workspace
  (cheap, raw-record recall). `chat` (LLM reasoning over the representation) only when explicitly
  needed — it costs an LLM call.
- **Commit (RETROSPECTIVE):** one compact `add_messages_to_session` pair (request + verified
  outcome) with metadata `{ repo, task_id, risk, files, verdict }`. This mirrors the
  completion-record shape Honcho already stores in practice (verified against the live `coding`
  workspace, where stored messages carry `repo` / `files` / `tests` / `verified` / `blocked_on`).
- **Consolidation:** `schedule_dream` at most weekly or per milestone — never per task.
- **Privacy:** the managed cloud egresses distilled lessons to a third party. The config step must
  disclose this; self-host or the `files` backend is the path for sensitive IP.

### 7.2 `references/memory-graphify.md` (graph-relevance: graphify)
- **Build (CONTEXT MAP):** `graphify . --update` (incremental via SHA256 + stat cache). Output to
  the gitignored `graphify-out/`.
- **Query:** budgeted `graphify query "<goal>"` or MCP `get_neighbors` / `god_nodes` /
  `shortest_path` (token_budget ~2000). Results populate `agent-record.json` `repo_map` fields
  (`entry_points`, `likely_files`, `callers_checked`).
- **Relevance amplification:** map changed files → graph neighbors / community → broaden which
  lessons match during recall.
- **Isolation:** heavy dependencies (numpy / networkx / tree-sitter parsers) live only in this
  optional path; the default tier never imports them. Install is opt-in (`uv tool install graphifyy`).
- **Caveat:** Graphify community IDs are not stable across re-runs (Leiden); lesson anchoring must
  key on stable entity labels, not community IDs. License is unverified upstream; adapter isolation
  means it never touches the core regardless.

## 8. Lifecycle wiring (manual / advisory)

- **CONTEXT MAP** — if `graph_relevance = graphify`, build/query the graph to produce the map;
  otherwise existing behavior is unchanged.
- **INTAKE / CONTEXT MAP** — run `memory-recall` (or Honcho `search`) to inject a tiny,
  relevance-scoped digest of prior lessons. **Recommended SKILL step, not gated.**
- **RETROSPECTIVE** — the agent calls `memory-commit` when a lesson is worth keeping. `verify-gates`
  remains **advisory** with respect to memory: it does **not** add a new hard block. (The win is the
  existence of a real persistent store + recall path, not stronger enforcement — per the user's
  "manual / agent-decides" choice.)
- **Claude Code hooks (optional):** a thin `SessionStart` wrapper may shell `memory-recall` and inject
  `MEMORY.md` via `additionalContext`. Documented in `examples/claude-code/`, never required.
  Non-CC hosts invoke the same CLI inline per `SKILL.md` / `AGENTS.md` instructions.

## 9. Config schema additions

`assets/quality-loop.config*.json` gains a `memory` block:
```json
{
  "memory": {
    "lessons_store": "files",        // files | honcho
    "graph_relevance": "none",       // none | graphify
    "location": "checked_in",        // checked_in | local
    "recall_budget_chars": 1500,
    "honcho": { "workspace_id": null, "peer_id": null, "session_template": null, "target_peer": null },
    "graphify": { "out_dir": "graphify-out", "token_budget": 2000 }
  }
}
```
`check-config` is extended to validate the `memory` block (enum values, fallback rules), keeping the
config self-documenting and offline-verifiable.

## 10. Anti-bloat tactics (held throughout)

1. Retrieval, never stuffing — memory enters context only via a budget-capped `recall` call.
2. Slim auto-load surface only — the single auto-loaded artifact is the ≤40-line `MEMORY.md`.
3. Relevance scoping at recall — keyword + path-glob + risk; top-N within budget.
4. Distill at write — store crisp conclusions, never transcripts/diffs.
5. Hard budget caps with truncation — fixed, predictable context cost regardless of project age.
6. Periodic consolidation — `memory-prune` (files) / `schedule_dream` (honcho), never per task.
7. Progressive disclosure tiers — frontmatter → SKILL.md → MEMORY.md index → targeted recall →
   single lesson detail.
8. Hit-count self-curation — recalled lessons gain weight; never-recalled ones age out.

## 11. Portability

The portable contract is **"a CLI over a checked-in directory"**. Hooks (Claude Code only) and MCP
(Honcho/Graphify) are accelerators layered on top, never the substrate. The `files` backend behaves
identically on every host. Optional adapters are reached over MCP (itself cross-host) and degrade to
`files` / `none` when absent, so moving from an MCP-rich host to a bare runtime keeps working.

## 12. Files touched

**New:**
- `references/memory.md` — capability model + backend-agnostic contract + lifecycle wiring.
- `references/memory-honcho.md` — Honcho lessons-store module.
- `references/memory-graphify.md` — Graphify graph-relevance module.
- `assets/lesson.schema.json` — lesson row schema.
- `.quality-loop/memory/` — seed (`lessons.jsonl` empty, `MEMORY.md` stub).
- `.gitignore` — add `graphify-out/`.

**Edited:**
- `SKILL.md` — new "Persistent Project Memory" section + lifecycle references.
- `scripts/quality_loop.py` — `memory-recall`, `memory-commit`, `memory-prune`, `memory-status`;
  `check-config` extended for the `memory` block.
- `assets/quality-loop.config.example.json` + `assets/quality-loop.config.schema.json` — `memory` block.
- `evals/` — new cases: recall determinism + budget enforcement, commit distillation, config validation.
- `README.md` — concise memory section.

## 13. Testing / evals

- **Files backend (deterministic):** unit-level eval cases pinning
  (a) recall ranking + budget truncation are deterministic for a fixed `lessons.jsonl`;
  (b) `memory-commit` distills a record into a well-formed lesson row;
  (c) `memory-prune` dedups and caps;
  (d) `check-config` accepts/rejects `memory` blocks correctly.
- **Adapters:** documented manual verification (MCP-dependent); not part of the dependency-free CI.
  CI remains green with zero third-party deps.
- All new Python keeps the project's stdlib-only, type-annotated style; existing
  `9/9 + 26/26` suites must stay green.

## 14. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Keyword/glob recall misses cross-vocabulary lessons | Honcho adapter (reasoning recall) for users who opt in; hit-count curation. |
| Ledger drifts noisy over time | `memory-prune` + hit-count aging; lessons-only scope keeps volume low. |
| Honcho cloud egress of code lessons | Config-time disclosure; `files` default; self-host path documented. |
| Graphify heavy deps / unverified license | Strictly optional, adapter-isolated; core never imports it. |
| Two backends → two trust profiles | `memory-status` + config disclosure make the active profile explicit. |
| Manual writes mean lessons can slip | Accepted per user choice; recall step is recommended; can be tightened to gated later without interface change. |

## 15. Non-goals

- Not a repo-map *cache as memory* (graph cache is regenerable, gitignored, not a lesson store).
- Not an `agent-record.json` archive / analytics warehouse.
- Not a new deterministic hard gate (writes stay advisory).
- Not a standalone Honcho/Graphify skill (loop-integrated only).
- Not a semantic-embedding recall in the default tier (would break dependency-free).

## 16. Success criteria

- Default tier adds **zero** third-party dependencies; existing CI stays green.
- A lesson committed in task *N* is recalled, within budget, at INTAKE of task *N+1* in the same
  project — demonstrated end to end with the `files` backend.
- Switching `lessons_store` / `graph_relevance` in config changes behavior **without** any edit to
  `SKILL.md` or eval cases.
- Auto-loaded memory surface stays ≤ 40 lines; recall output respects its budget.
- Honcho and Graphify modules are usable as loop backends with config only (no code change).
