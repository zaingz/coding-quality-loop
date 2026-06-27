# Memory backend: Honcho (lessons_store = honcho)

Honcho is an optional, reasoning-based lessons store. It is **agent-driven over MCP** — a
stdlib script cannot call MCP, so the loop drives Honcho's tools per this module. It does not
change the loop's contract; it implements `recall` and `commit` for lessons.

## Configuration

`memory.honcho` in the config is fully driven by you, so the adapter slots into whatever
Honcho governance already exists (e.g. a workspace whose rules forbid creating new peer IDs):

- `workspace_id` — the Honcho workspace for this project.
- `peer_id` — the peer the lessons are attributed to / queried about (never invent one if the
  workspace forbids it).
- `session_template` — naming for the session, e.g. `ql-<repo>-lessons`.
- `target_peer` — optional, when modelling one peer's view of another.

## recall (INTAKE / CONTEXT MAP)

Use the cheap retrieval path first: `search` (raw records) or `query_conclusions` scoped to
`peer_id` / `workspace_id`. Use `chat` (reasoning over the representation) only when needed —
it costs an LLM call. Keep the injected digest within the same budget as the files backend.

## commit (RETROSPECTIVE)

Write one compact `add_messages_to_session` pair (user request + verified outcome) with
metadata `{repo, task_id, risk, files, verdict}`. This mirrors the completion-record shape
Honcho already stores in practice. Run `schedule_dream` at most weekly or per milestone for
consolidation — never per task.

## Privacy

The Honcho managed cloud egresses distilled lessons to a third party. Disclose this at config
time. For sensitive IP, use a self-hosted Honcho or the default `files` backend. Never store
secrets, tokens, or raw sensitive logs as lessons.
