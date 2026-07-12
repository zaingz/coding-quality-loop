# Control plane — local observability for agent work

One place to monitor, observe, and learn what your agents are doing: every
session, every model call with exact token counts, tool calls, token spend,
routing, hook events, and every Quality Loop artifact (completion records,
independent reviews, minimality decisions, plans, escalations, memory
lessons, progress). Local files in, local dashboard out.

```bash
python3 scripts/quality_loop.py control-index    # build/update the index
python3 scripts/quality_loop.py control-serve    # open http://127.0.0.1:4477/
```

<img src="images/control-plane.png" alt="Control plane dashboard — overview with session totals, model calls, exact input/output/cache token tiles, an output-tokens-by-day bar chart, and a per-model breakdown table" width="900">

## Design rules (why this doesn't violate the repo's own doctrine)

1. **An index over evidence, never a gate.** The SQLite file at
   `.quality-loop/control/control.db` is a disposable cache built from
   sources of truth: host transcripts and CQL artifacts. Deleting the
   directory loses nothing rebuildable — `control-index` regenerates
   everything except recorded hook events, which exist only in the DB (stop
   the server first; a schema bump rebuilds the cache automatically the same
   way). No gate reads it.
2. **Local only.** Stdlib `sqlite3` + `http.server`, zero dependencies. The
   server is hard-bound to `127.0.0.1` (not configurable), serves **GET
   only** (anything else is 405), and has no auth because it has no remote
   surface to protect. This is not the "hosted service" the ROADMAP
   excludes — nothing leaves the machine.
3. **Metadata, not conversation bodies.** The index stores model ids, token
   counts, tool names, truncated tool targets (up to 200 chars of e.g. a file
   path, command line, or a sub-agent prompt excerpt — command lines can
   contain whatever you typed into them, secrets included), timestamps, and a
   short session title (the first 160 chars of the first prompt, or the
   host's own summary). Beyond those two deliberate excerpts, conversation
   content is not copied into the DB — and nothing in the index leaves the
   machine either way.
4. **Tokens are facts; dollars are yours.** Spend is reported in exact token
   counts from the host transcript. USD appears only if you fill
   `control_plane.prices` with your own rates — the repo ships no vendor
   price data (decaying vendor data stays documentation-only, per ROADMAP).
   The v3.0 decision to archive the *stats-report subcommand* stands: the
   `jq` recipe in `assets/routing/README.md` remains the scriptable report;
   this is a UI, not a gate or a report format.

## What it indexes

| Source | Becomes | Host coverage |
|---|---|---|
| `~/.claude/projects/<repo-slug>*/*.jsonl` (subdirectory slugs included after a per-file cwd check — sessions started from `repo/sub` land under a longer slug) | sessions, model calls (exact `usage` tokens, deduped per API response), tool calls with ok/error status, subagent attribution | Claude Code (transcript adapter) |
| `.quality-loop/agent-record.json` + `docs/records/*.json` | record / review / decision / plan / escalation / models_used artifacts | any host running the loop |
| `.quality-loop/memory/lessons.jsonl`, `.quality-loop/progress.md` | memory + progress artifacts | any host |
| Hook events via `control-ingest` | session start/end rows, live event feed | claude-code + codex wiring shipped; any host that can pipe JSON |

Honest labeling: only Claude Code gets deep transcript indexing today. Codex
sessions appear through the shipped hook wiring plus the CQL artifacts they
produce; Droid has no hook wiring yet, so its sessions appear through CQL
artifacts only — the loop's records are host-neutral by design, so reviews,
decisions, and `models_used` spend attribution show up regardless of which
harness did the work.

Indexing is incremental (per-file byte offsets; transcript files are
append-only) and deduplicated by message uuid — a full rescan never double
counts. Unparsable lines are counted and skipped, never fatal: a future
transcript format change degrades to "fewer rows", not a crash.

## Commands

| Command | What it does |
|---|---|
| `control-index [--all-projects] [--json]` | Incremental index build. `--all-projects` sweeps every project dir under `~/.claude/projects`, not just this repo's. |
| `control-serve [--port N]` | Index, then serve the dashboard + JSON API on `127.0.0.1`. Refuses to double-start (pidfile). |
| `control-status [--json]` | DB path, row counts, server state, enabled flag. |
| `control-stop` | SIGTERM the running server. |
| `control-ingest --event NAME` | Hook entry point: records one event from stdin JSON. No-op unless enabled; **always exits 0**. |

### JSON API (all GET, all local)

`/healthz`, `/api/overview`, `/api/sessions?limit=`, `/api/session?id=`,
`/api/spend?by=model|day|session|agent`, `/api/records`, `/api/memory`,
`/api/events?limit=`, `/api/routing`. The dashboard at `/` is a single
self-contained HTML file (no external requests, light/dark, keyboard
navigable) — an eval case pins the self-containment.

## Hooks: opt-in autostart

Nothing is collected until you opt in. In `quality-loop.config.json`:

```json
"control_plane": {
  "enabled": true,
  "autostart": true,
  "port": 4477,
  "retention_days": 90,
  "prices": {}
}
```

With `enabled: true`, the shipped `SessionStart`/`SessionEnd` hooks
(claude-code `settings.json` and codex `hooks.json` both wired by
`install.py`) record session events, and `autostart` launches the dashboard
server in the background on session start — guarded by a pidfile so a live
server is never double-started. With `enabled: false` (the example-config
default) the hooks write nothing and start nothing; explicit
`control-index`/`control-serve` always work regardless.

The ingest path **never fails a session**: every failure exits 0. A broken
or disabled config is a silent no-op (opt-in is checked before anything is
read or written); failures after the enabled check (malformed stdin, a
locked DB) are logged to `.quality-loop/control/ingest-errors.log`. Wall-clock is bounded by the
host's own hook timeout (10s in the shipped wiring; the shim caps its ingest
subprocess at 6s and its git lookup at 5s). A broken observability plane must
degrade to "no data", never to a session that cannot start. (This is the one
place in the repo that deliberately swallows errors; the gates stay loud.)

`prices` maps a model-id substring to your rates in USD per million tokens,
e.g. `{"fable": {"input_per_mtok": 20, "output_per_mtok": 100,
"cache_read_per_mtok": 2}}`. Longest matching substring wins.

## Privacy and threat model

- Everything stays on the machine: DB, server, dashboard. The bind address
  is hard-coded to loopback, there are no write endpoints, and requests with
  a non-loopback `Host` header are rejected with 403 (DNS-rebinding guard).
- Other processes running as your user can read the DB file and the
  localhost API — same trust boundary as the transcripts themselves, which
  is where the data already lives in plainer form.
- The DB directory self-gitignores (`.quality-loop/control/.gitignore` is
  written with `*` on creation), so control data can never land in a commit
  — and because it lives under `.quality-loop/`, it is excluded from the
  review attestation hash.
- To remove all collected data: `control-stop`, then delete
  `.quality-loop/control/`.

## Eval coverage

The 20-case `evals/run_control_evals.py` suite pins: exact token math,
incremental/rescan dedupe, malformed-line resilience, subagent attribution,
artifact ingestion, price arithmetic, every API endpoint, the 127.0.0.1
bind, GET-only enforcement, dashboard self-containment, ingest no-op when
disabled, exit-0 on garbage, the pidfile double-start guard, real autostart,
config validation, and installer wiring.
