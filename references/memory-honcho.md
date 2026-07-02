# Memory backend: Honcho (`lessons_store = honcho`)

[Honcho](https://honcho.dev) is a reasoning-based agent memory service. Since
v2.2 the Coding Quality Loop ships a **runnable adapter**
(`scripts/quality_loop_honcho.py`) that implements the same recall/commit
contract as the files backend, so the loop's behavior is identical whether the
underlying store is JSONL on disk or Honcho over HTTP.

## Configuration

Set `memory.lessons_store = "honcho"` in your quality-loop config and add a
`memory.honcho` block:

```json
{
  "memory": {
    "lessons_store": "honcho",
    "honcho": {
      "workspace_id": "acme-payments",
      "peer_id": "quality-loop-bot",
      "session_template": "ql-lessons",
      "base_url": "http://localhost:8000"
    }
  }
}
```

Secrets are never read from the config file. Provide them via environment:

- `HONCHO_API_KEY` — required **only for the managed cloud**. Optional for
  self-hosted / local Honcho when `AUTH_USE_AUTH=false` in the server's env.
- `HONCHO_BASE_URL` — optional (self-hosted / managed cloud).
- `HONCHO_WORKSPACE_ID`, `HONCHO_PEER_ID` — optional overrides.

`check-config` validates the block (`workspace_id` and `peer_id` are required
when `lessons_store = "honcho"`).

### Zero-config local mode (recommended for solo & OSS use)

The adapter defaults `base_url` to `http://localhost:8000` when neither the
config nor `HONCHO_BASE_URL` provides one, and it will connect **without an
API key** to any URL that resolves to a local endpoint (`localhost`,
`127.0.0.1`, `0.0.0.0`, `host.docker.internal`, `::1`, or a `.local` host).
The typical zero-config setup is:

```bash
# 1. Run Honcho locally with auth disabled
git clone https://github.com/plastic-labs/honcho && cd honcho
AUTH_USE_AUTH=false docker compose up

# 2. In your project, point the loop at it and omit HONCHO_API_KEY
cat > ql.config.json <<'JSON'
{ "memory": { "lessons_store": "honcho",
  "honcho": { "workspace_id": "me", "peer_id": "quality-loop" } } }
JSON
python scripts/quality_loop.py memory-recall --config ql.config.json --task-id t1
```

No secret ever leaves your machine. For managed Honcho
(`https://api.honcho.dev`) or any non-local URL, `HONCHO_API_KEY` is still
required and the adapter refuses to connect keyless — this is a safety rail,
not a bug.

## Contract

- `memory-recall --config ql.config.json` transparently routes to the Honcho
  adapter and calls Honcho's cheap `search` retrieval scoped to `peer_id` /
  `workspace_id`. `query_conclusions` is available for reasoning-time recall
  and `chat` is reserved for the rare case that requires an LLM call. The
  returned messages are re-ranked locally with the exact same scorer the
  files backend uses (`keyword_overlap * 2 + path_match * 3 + risk_match +
  min(hits, 5) * 0.1`), so backend selection never changes recall ordering.
- `memory-commit … --config ql.config.json` **dual-writes**: the files backend
  is written first (source of truth, offline-safe, review-friendly), then the
  same rows are mirrored via `add_messages_to_session` if Honcho is available.
  This preserves the audit trail for CI and gives Honcho users reasoning-time
  recall. Run `schedule_dream` at most weekly for consolidation, never per task.
- If the SDK is not installed, the API key is missing, or a network call
  fails, the adapter **degrades silently to files** and prints a single-line
  notice on stderr. The loop never breaks because Honcho is unreachable.

## Boundary redaction

Every lesson egressed to Honcho passes through `redact()` a second time inside
the adapter — including the `keywords` array. This is defense in depth on top
of `normalize_lesson`'s in-store redaction. See the entropy-based and OpenAI
hyphenated-key redaction fixes shipped alongside this adapter.

## Runtime dependency

The [`honcho-ai`](https://pypi.org/project/honcho-ai/) SDK is imported lazily
inside `_client()`. Users on the files backend never need it installed. Users
on the Honcho backend install it with `pip install honcho-ai`.

## Privacy

The Honcho managed cloud egresses distilled lessons to a third party. Disclose
this at config time. For sensitive IP, use a self-hosted Honcho or the default
`files` backend. Never store secrets, tokens, or raw sensitive logs as
lessons — the redactor is a safety net, not a policy.
