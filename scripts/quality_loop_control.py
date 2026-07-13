"""Control plane: a local, stdlib-only observability index + dashboard server.

One place to see what the agents are doing: sessions, model calls with exact
token usage, tool calls, routing, token spend, hook events, and every CQL
artifact (records, reviews, minimality decisions, escalations, memory lessons,
progress). Three design rules keep it inside the repo's doctrine:

1. **Index over evidence, never a gate.** The DB is a disposable cache built
   from sources of truth (host transcripts + CQL artifacts). Deleting
   ``.quality-loop/control/`` loses nothing; ``control-index`` rebuilds it.
2. **Local only.** SQLite file, server hard-bound to 127.0.0.1, GET-only API,
   zero dependencies. No hosted anything.
3. **Metadata, not conversation bodies.** Model/token/tool metadata, truncated
   tool targets, and a short session title are stored; message content is not.

Token spend is reported in tokens. USD appears only when the user supplies
their own prices in ``control_plane.prices`` — this repo ships no vendor price
data (decaying vendor data is documentation-only by doctrine; see ROADMAP).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import signal
import sqlite3
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import quality_loop_core as qlcore
import quality_loop_routing as qlroute

DEFAULT_PORT = 4477
DEFAULT_RETENTION_DAYS = 90
# Seconds between automatic reindex passes triggered by API requests.
INDEX_DEBOUNCE_SECS = 3.0
TITLE_MAX = 160
TARGET_MAX = 200
CONTROL_KEYS = {
    "enabled", "port", "autostart", "prices", "retention_days", "note", "description",
}
# The only rate keys _cost() reads. Validation rejects anything else so a typo
# ("input_per_mtok_" etc.) fails loudly instead of silently pricing at $0.
PRICE_RATE_KEYS = {
    "input_per_mtok", "output_per_mtok", "cache_read_per_mtok", "cache_creation_per_mtok",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions(
  id TEXT PRIMARY KEY,
  host TEXT NOT NULL DEFAULT 'claude-code',
  source TEXT NOT NULL DEFAULT 'transcript',
  title TEXT,
  agent_name TEXT,
  cwd TEXT,
  git_branch TEXT,
  app_version TEXT,
  started_at TEXT,
  last_activity_at TEXT,
  ended_at TEXT,
  transcript_path TEXT,
  team TEXT
);
CREATE TABLE IF NOT EXISTS model_calls(
  uuid TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  ts TEXT,
  model TEXT,
  agent TEXT,
  sidechain INTEGER NOT NULL DEFAULT 0,
  input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  cache_read_tokens INTEGER NOT NULL DEFAULT 0,
  cache_creation_tokens INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_model_calls_session ON model_calls(session_id);
CREATE INDEX IF NOT EXISTS ix_model_calls_ts ON model_calls(ts);
CREATE TABLE IF NOT EXISTS tool_calls(
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  ts TEXT,
  tool TEXT,
  target TEXT,
  agent TEXT,
  sidechain INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'sent'
);
CREATE INDEX IF NOT EXISTS ix_tool_calls_session ON tool_calls(session_id);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  host TEXT,
  ts TEXT,
  name TEXT,
  detail TEXT
);
CREATE TABLE IF NOT EXISTS artifacts(
  key TEXT PRIMARY KEY,
  source_path TEXT NOT NULL,
  kind TEXT NOT NULL,
  ts TEXT,
  title TEXT,
  detail TEXT
);
CREATE INDEX IF NOT EXISTS ix_artifacts_kind ON artifacts(kind);
CREATE TABLE IF NOT EXISTS file_state(
  path TEXT PRIMARY KEY,
  offset INTEGER NOT NULL DEFAULT 0,
  mtime REAL NOT NULL DEFAULT 0,
  head_hash TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
"""


# ---------------------------------------------------------------------------
# Paths + config
# ---------------------------------------------------------------------------

def control_dir(root: Path) -> Path:
    return root / ".quality-loop" / "control"


def db_path(root: Path) -> Path:
    return control_dir(root) / "control.db"


def server_state_path(root: Path) -> Path:
    return control_dir(root) / "server.json"


def ingest_error_log(root: Path) -> Path:
    return control_dir(root) / "ingest-errors.log"


def _ensure_control_dir(root: Path) -> Path:
    cdir = control_dir(root)
    cdir.mkdir(parents=True, exist_ok=True)
    # Self-ignoring directory: control data (DB, pidfile, logs) must never land
    # in a commit or the attestation hash, with zero user action.
    gi = cdir / ".gitignore"
    if not gi.is_file():
        gi.write_text("*\n", encoding="utf-8")
    return cdir


def load_control_config(root: Path) -> dict[str, Any]:
    cfg_path = root / "quality-loop.config.json"
    if not cfg_path.is_file():
        return {}
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):  # ValueError covers JSON and unicode errors
        return {}
    block = cfg.get("control_plane") if isinstance(cfg, dict) else None
    return block if isinstance(block, dict) else {}


def validate_control_plane(block: Any) -> list[str]:
    """Shape-validate a config ``control_plane`` block (used by check-config)."""
    if not isinstance(block, dict):
        return ["control_plane must be an object"]
    errors: list[str] = []
    for key in block:
        if key not in CONTROL_KEYS:
            errors.append(f"control_plane has unknown key: {key!r}")
    for key in ("enabled", "autostart"):
        if key in block and not isinstance(block[key], bool):
            errors.append(f"control_plane.{key} must be a boolean")
    for key in ("note", "description"):
        if key in block and not isinstance(block[key], str):
            errors.append(f"control_plane.{key} must be a string")
    port = block.get("port")
    if port is not None and (not isinstance(port, int) or isinstance(port, bool) or not 1024 <= port <= 65535):
        errors.append("control_plane.port must be an integer in 1024..65535")
    days = block.get("retention_days")
    if days is not None and (not isinstance(days, int) or isinstance(days, bool) or days < 1):
        errors.append("control_plane.retention_days must be a positive integer")
    prices = block.get("prices")
    if prices is not None:
        if not isinstance(prices, dict):
            errors.append("control_plane.prices must be an object of model -> rate object")
        else:
            for model, rates in prices.items():
                if not isinstance(rates, dict):
                    errors.append(f"control_plane.prices[{model!r}] must be an object")
                    continue
                for rk, rv in rates.items():
                    if rk not in PRICE_RATE_KEYS:
                        errors.append(
                            f"control_plane.prices[{model!r}] has unknown price key: {rk!r} "
                            f"(valid: {', '.join(sorted(PRICE_RATE_KEYS))})"
                        )
                    if (not isinstance(rv, (int, float)) or isinstance(rv, bool)
                            or not math.isfinite(rv) or rv < 0):
                        errors.append(
                            f"control_plane.prices[{model!r}].{rk} must be a finite non-negative number"
                        )
    return errors


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

# Bump when _SCHEMA (or row semantics, e.g. the model_calls dedupe key)
# changes shape. The DB is a disposable cache over sources of truth, so
# migration IS rebuild: anything else risks serving stale/mis-keyed rows.
# v3: added the codex rollout adapter (host='codex') -> force one clean rebuild
# so existing caches ingest Codex sessions uniformly.
# v4: added the droid/GLM wrapper adapter (host='droid').
# v5: capture teamName -> sessions.team so a session can list its sub-agents.
# v6: also link codex sub-agents (parent_thread_id) into sessions.team.
# v7: finding/delegation artifact kinds + tool_calls.target passes secret
#     redaction before storage (rebuild re-redacts any old raw targets).
SCHEMA_VERSION = 7


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    # Concurrent writers exist by design (server threads + hook ingest);
    # WAL + a busy timeout make them wait instead of raising "database is locked".
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def open_db(root: Path) -> sqlite3.Connection:
    _ensure_control_dir(root)
    path = db_path(root)
    conn = _connect(path)
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version != SCHEMA_VERSION:
        has_tables = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
        if has_tables:
            # A cache written by another schema revision: rebuild from scratch
            # rather than crash on missing columns or serve mis-keyed rows.
            conn.close()
            for suffix in ("", "-wal", "-shm"):
                try:
                    Path(str(path) + suffix).unlink()
                except OSError:
                    pass
            conn = _connect(path)
        conn.execute(f"PRAGMA user_version={SCHEMA_VERSION:d}")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    return conn


def _meta_get(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def _meta_set(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def _touch_session(
    conn: sqlite3.Connection,
    session_id: str,
    ts: str | None,
    *,
    host: str = "claude-code",
    source: str = "transcript",
    **fields: Any,
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO sessions(id, host, source, started_at, last_activity_at) "
        "VALUES(?,?,?,?,?)",
        (session_id, host, source, ts, ts),
    )
    if ts:
        conn.execute(
            "UPDATE sessions SET "
            "started_at = CASE WHEN started_at IS NULL OR started_at > ? THEN ? ELSE started_at END, "
            "last_activity_at = CASE WHEN last_activity_at IS NULL OR last_activity_at < ? THEN ? ELSE last_activity_at END "
            "WHERE id = ?",
            (ts, ts, ts, ts, session_id),
        )
    for col, val in fields.items():
        if val is None:
            continue
        if col not in {"title", "agent_name", "cwd", "git_branch", "app_version", "ended_at", "transcript_path", "team"}:
            continue
        conn.execute(
            f"UPDATE sessions SET {col}=? WHERE id=? AND ({col} IS NULL OR {col}='')",
            (val, session_id),
        )


# ---------------------------------------------------------------------------
# Transcript adapter (claude-code)
# ---------------------------------------------------------------------------

def project_slug(root: Path) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", str(root))


def claude_projects_root() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude")) / "projects"


def transcript_dirs(root: Path, all_projects: bool = False) -> list[tuple[Path, bool]]:
    """(directory, needs_cwd_check) pairs for this repo's transcripts.

    Hosts slug the project dir by session CWD, so work started from a repo
    SUBDIRECTORY lands under a longer slug (repo/sub -> '<slug>-sub'). Those
    prefix-matched dirs are included, but slug flattening is ambiguous — a
    sibling checkout named 'repo-sub' produces the same slug — so their files
    only count after a per-file cwd check proves they belong to this root.
    """
    base = claude_projects_root()
    if not base.is_dir():
        return []
    if all_projects:
        return sorted((p, False) for p in base.iterdir() if p.is_dir())
    slug = project_slug(root)
    out: list[tuple[Path, bool]] = []
    exact = base / slug
    if exact.is_dir():
        out.append((exact, False))
    prefix = slug + "-"
    out.extend(sorted(
        (p, True) for p in base.iterdir() if p.is_dir() and p.name.startswith(prefix)
    ))
    return out


def _file_in_root(path: Path, root: Path) -> bool:
    """True when the first cwd-bearing line places this transcript inside
    ``root``. Files with no cwd in the first 64KB stay unattributed."""
    try:
        with path.open("rb") as fh:
            head = fh.read(65536)
    except OSError:
        return False
    for raw in head.splitlines():
        try:
            line = json.loads(raw.decode("utf-8", errors="replace"))
        except ValueError:
            continue
        cwd = line.get("cwd") if isinstance(line, dict) else None
        if isinstance(cwd, str) and cwd:
            try:
                return Path(cwd).resolve().is_relative_to(root.resolve())
            except OSError:
                return False
    return False


def _redact_target(value: str) -> str:
    """A tool target (command line, path, url) may contain a secret typed at the
    prompt. Reuse the project's memory redaction before storage, then truncate —
    redact first so a key that straddles the truncation point is still caught."""
    return qlcore.redact(value)[:TARGET_MAX]


def _summarize_tool_input(tool: str, tool_input: Any) -> str:
    if not isinstance(tool_input, dict):
        return ""
    for key in ("file_path", "command", "path", "url", "pattern", "query", "skill", "description", "prompt", "subject"):
        val = tool_input.get(key)
        if isinstance(val, str) and val.strip():
            return _redact_target(val.strip())
    return ""


def _first_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                return item["text"]
    return ""


def _clean_title(text: str) -> str:
    text = text.strip()
    # Skip machine wrappers (hook output, teammate envelopes, local-command
    # caveats) so the title is the human's prompt, not harness plumbing.
    if not text or text.startswith("<") or text.startswith("Caveat:"):
        return ""
    return re.sub(r"\s+", " ", text)[:TITLE_MAX]


def _purge_transcript_rows(conn: sqlite3.Connection, path: Path) -> None:
    """Drop every row derived from one transcript file (rewrite/removal)."""
    ids = [r["id"] for r in conn.execute(
        "SELECT id FROM sessions WHERE transcript_path=?", (str(path),))]
    for sid in ids:
        conn.execute("DELETE FROM model_calls WHERE session_id=?", (sid,))
        conn.execute("DELETE FROM tool_calls WHERE session_id=?", (sid,))
    conn.execute("DELETE FROM sessions WHERE transcript_path=? AND source='transcript'", (str(path),))


def _index_transcript_file(conn: sqlite3.Connection, path: Path) -> dict[str, int]:
    stats = {"lines": 0, "skipped": 0, "model_calls": 0, "tool_calls": 0}
    try:
        st = path.stat()
    except OSError:
        return stats  # vanished between glob and stat; next pass reconciles
    row = conn.execute(
        "SELECT offset, mtime, head_hash FROM file_state WHERE path=?", (str(path),)
    ).fetchone()
    offset = row["offset"] if row else 0
    if row and st.st_mtime == row["mtime"] and st.st_size == offset:
        return stats
    fallback_session = path.stem
    with path.open("rb") as fh:
        # A changed head or a shrunken file means the file was REWRITTEN, not
        # appended: resuming from the old offset would index garbage and keep
        # rows whose source lines no longer exist. Purge and rescan instead.
        # The hash covers min(512, indexed_offset) bytes — a prefix that an
        # append can never change — and the same span is recomputed below.
        # Known limit: a rewrite that preserves that prefix AND does not
        # shrink the file is indistinguishable from an append (transcripts
        # are append-only in practice; cql: full-content hashing is the
        # upgrade path if a host ever rewrites tails in place).
        if row:
            span = min(512, row["offset"])
            head_hash = hashlib.sha256(fh.read(span)).hexdigest() if span else ""
            if (row["head_hash"] and head_hash != row["head_hash"]) or st.st_size < offset:
                _purge_transcript_rows(conn, path)
                offset = 0
        fh.seek(offset)
        blob = fh.read()
    # Only complete lines are consumed; a partial trailing line stays unread
    # until the writer finishes it (transcripts are append-only).
    end = blob.rfind(b"\n")
    if end < 0:
        return stats
    new_offset = offset + end + 1
    for raw in blob[: end + 1].splitlines():
        if not raw.strip():
            continue
        stats["lines"] += 1
        try:
            line = json.loads(raw.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, ValueError):
            stats["skipped"] += 1
            continue
        if not isinstance(line, dict):
            stats["skipped"] += 1
            continue
        try:
            _index_line(conn, line, fallback_session, str(path), stats)
        except (sqlite3.Error, TypeError, ValueError, AttributeError):
            # One hostile/unexpected line shape must degrade to "one fewer
            # row", never to a dead index pass — the docs promise this.
            stats["skipped"] += 1
    with path.open("rb") as fh:
        stored_hash = hashlib.sha256(fh.read(min(512, new_offset))).hexdigest()
    conn.execute(
        "INSERT INTO file_state(path, offset, mtime, head_hash) VALUES(?,?,?,?) "
        "ON CONFLICT(path) DO UPDATE SET offset=excluded.offset, mtime=excluded.mtime, "
        "head_hash=excluded.head_hash",
        (str(path), new_offset, st.st_mtime, stored_hash),
    )
    return stats


def _index_line(
    conn: sqlite3.Connection, line: dict, fallback_session: str, tpath: str, stats: dict[str, int]
) -> None:
    ltype = line.get("type")
    session_id = str(line.get("sessionId") or line.get("session_id") or fallback_session)
    ts = line.get("timestamp")
    ts = ts if isinstance(ts, str) else None
    if ltype == "summary":
        summary = line.get("summary")
        if isinstance(summary, str) and summary.strip():
            # A summary is the best title available; it may arrive after the
            # first prompt, so overwrite rather than fill-if-empty.
            _touch_session(conn, fallback_session, None)
            conn.execute(
                "UPDATE sessions SET title=? WHERE id=?",
                (summary.strip()[:TITLE_MAX], fallback_session),
            )
        return
    if ltype not in ("assistant", "user"):
        return
    message = line.get("message") if isinstance(line.get("message"), dict) else {}
    sidechain = 1 if line.get("isSidechain") else 0
    agent = line.get("agentName") if isinstance(line.get("agentName"), str) else None
    # teamName ("session-<parent-prefix>") links a spawned sub-agent session back
    # to the session that spawned it, so a parent can list its sub-agents.
    team = line.get("teamName") if isinstance(line.get("teamName"), str) else None
    _touch_session(
        conn,
        session_id,
        ts,
        cwd=line.get("cwd"),
        git_branch=line.get("gitBranch"),
        app_version=line.get("version"),
        agent_name=agent,
        transcript_path=tpath,
        team=team,
    )
    if ltype == "assistant":
        usage = message.get("usage") if isinstance(message.get("usage"), dict) else {}
        uuid = line.get("uuid")
        # ONE row per API response, not per transcript line: hosts write one
        # JSONL line per content block, each repeating the same message.id and
        # the same usage — keying on the line uuid would multiply token totals
        # by the block count (~3-4x observed). message.id (then requestId) is
        # the API-response identity; the line uuid is only a last resort.
        # Dedupe is GLOBAL on purpose: a call duplicated into a forked/resumed
        # session file counts once (spend is per API call), attributed to
        # whichever file indexed it first.
        call_key = message.get("id") or line.get("requestId") or uuid
        if isinstance(call_key, str) and (usage or message.get("model")):
            cur = conn.execute(
                "INSERT OR IGNORE INTO model_calls(uuid, session_id, ts, model, agent, sidechain, "
                "input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    call_key, session_id, ts, message.get("model"), agent, sidechain,
                    _as_int(usage.get("input_tokens")),
                    _as_int(usage.get("output_tokens")),
                    _as_int(usage.get("cache_read_input_tokens")),
                    _as_int(usage.get("cache_creation_input_tokens")),
                ),
            )
            stats["model_calls"] += cur.rowcount if cur.rowcount > 0 else 0
        content = message.get("content")
        if isinstance(content, list):
            for item in content:
                if not (isinstance(item, dict) and item.get("type") == "tool_use"):
                    continue
                tool_id = item.get("id")
                if not isinstance(tool_id, str):
                    continue
                cur = conn.execute(
                    "INSERT OR IGNORE INTO tool_calls(id, session_id, ts, tool, target, agent, sidechain) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (
                        tool_id, session_id, ts, item.get("name"),
                        _summarize_tool_input(str(item.get("name")), item.get("input")),
                        agent, sidechain,
                    ),
                )
                stats["tool_calls"] += cur.rowcount if cur.rowcount > 0 else 0
        return
    # user line: tool results update status; the first real prompt titles the session
    content = message.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_result":
                tool_id = item.get("tool_use_id")
                if isinstance(tool_id, str):
                    status = "error" if item.get("is_error") else "ok"
                    conn.execute(
                        "UPDATE tool_calls SET status=? WHERE id=? AND status='sent'",
                        (status, tool_id),
                    )
    title = _clean_title(_first_text(content))
    if title:
        conn.execute(
            "UPDATE sessions SET title=? WHERE id=? AND (title IS NULL OR title='')",
            (title, session_id),
        )


def _as_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


# ---------------------------------------------------------------------------
# Rollout adapter (codex)
# ---------------------------------------------------------------------------
# OpenAI Codex CLI persists one append-only JSONL "rollout" per session under
# ~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl; each line is a
# RolloutLine {timestamp, type, payload}. Unlike claude-code (one dir per cwd),
# codex pools every project in one date tree, so scoping is a per-file
# session_meta.cwd check. The incremental machinery mirrors the transcript
# adapter: offset+head-hash caching, purge-on-rewrite, complete lines only.
# One model_call per token_count event -- info.last_token_usage is a verified
# per-call delta (summing it reproduces total_token_usage exactly) -- attributed
# to the model from the most recent turn_context.

_CODEX_UUID_RE = re.compile(
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$"
)


def codex_sessions_root() -> Path:
    return Path(os.environ.get("CODEX_SESSIONS_DIR") or (Path.home() / ".codex" / "sessions"))


def codex_rollout_files() -> list[Path]:
    base = codex_sessions_root()
    if not base.is_dir():
        return []
    return sorted(base.glob("*/*/*/rollout-*.jsonl"))


def _codex_session_id(path: Path) -> str:
    m = _CODEX_UUID_RE.search(path.stem)
    return m.group(1) if m else path.stem


def _codex_meta(first_line: bytes) -> dict[str, Any] | None:
    try:
        line = json.loads(first_line.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, ValueError):
        return None
    if isinstance(line, dict) and line.get("type") == "session_meta":
        payload = line.get("payload")
        return payload if isinstance(payload, dict) else None
    return None


def _codex_lineage(meta: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (parent_thread_id, agent_label) for a codex rollout's session_meta.

    A spawned sub-agent carries its parent + nickname/role either at the top of
    session_meta or nested under source.subagent.thread_spawn.
    """
    parent = meta.get("parent_thread_id")
    nickname = meta.get("agent_nickname")
    role = meta.get("agent_role")
    src = meta.get("source")
    if isinstance(src, dict):
        spawn = ((src.get("subagent") or {}).get("thread_spawn")) or {}
        if isinstance(spawn, dict):
            parent = parent or spawn.get("parent_thread_id")
            nickname = nickname or spawn.get("agent_nickname")
            role = role or spawn.get("agent_role")
    parent = parent if isinstance(parent, str) and parent else None
    label = None
    if isinstance(nickname, str) and nickname:
        label = f"{nickname} ({role})" if isinstance(role, str) and role else nickname
    elif isinstance(role, str) and role:
        label = role
    return parent, label


def _index_codex_line(
    conn: sqlite3.Connection, line: dict, session_id: str, model: str | None, stats: dict[str, int]
) -> str | None:
    """Handle one rollout line; returns the (possibly updated) current model."""
    ltype = line.get("type")
    ts = line.get("timestamp")
    ts = ts if isinstance(ts, str) else None
    payload = line.get("payload") if isinstance(line.get("payload"), dict) else {}
    if ltype == "turn_context":
        m = payload.get("model")
        return m if isinstance(m, str) and m else model
    if ltype == "event_msg":
        ptype = payload.get("type")
        if ptype == "token_count":
            info = payload.get("info") if isinstance(payload.get("info"), dict) else {}
            last = info.get("last_token_usage") if isinstance(info.get("last_token_usage"), dict) else {}
            total = info.get("total_token_usage") if isinstance(info.get("total_token_usage"), dict) else {}
            if last:
                # ts+cumulative-total keys the row intrinsically, so a rescan
                # after a rewrite repopulates the same rows (append-only in
                # practice; a rare same-ms collision drops one row, not the pass).
                key = f"cx:{session_id}:{ts}:{_as_int(total.get('total_tokens'))}"
                cur = conn.execute(
                    "INSERT OR IGNORE INTO model_calls(uuid, session_id, ts, model, agent, sidechain, "
                    "input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        key, session_id, ts, model, None, 0,
                        _as_int(last.get("input_tokens")),
                        _as_int(last.get("output_tokens")),
                        _as_int(last.get("cached_input_tokens")),
                        0,  # codex does not report cache-creation separately
                    ),
                )
                stats["model_calls"] += cur.rowcount if cur.rowcount > 0 else 0
        elif ptype == "user_message":
            title = _clean_title(payload.get("message") if isinstance(payload.get("message"), str) else "")
            if title:
                conn.execute(
                    "UPDATE sessions SET title=? WHERE id=? AND (title IS NULL OR title='')",
                    (title, session_id),
                )
        return model
    if ltype == "response_item":
        if payload.get("type") in ("function_call", "custom_tool_call"):
            call_id = payload.get("call_id") or payload.get("id")
            name = payload.get("name")
            if isinstance(call_id, str) and isinstance(name, str):
                raw = payload.get("input")
                if raw is None:
                    raw = payload.get("arguments")
                target = raw if isinstance(raw, str) else (json.dumps(raw) if raw else "")
                cur = conn.execute(
                    "INSERT OR IGNORE INTO tool_calls(id, session_id, ts, tool, target, agent, sidechain) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (f"cx:{call_id}", session_id, ts, name, _redact_target(target.strip()), None, 0),
                )
                stats["tool_calls"] += cur.rowcount if cur.rowcount > 0 else 0
    return model


def _index_codex_file(
    conn: sqlite3.Connection, path: Path, root: Path, all_projects: bool
) -> dict[str, int]:
    stats = {"lines": 0, "skipped": 0, "model_calls": 0, "tool_calls": 0}
    try:
        st = path.stat()
    except OSError:
        return stats
    row = conn.execute(
        "SELECT offset, mtime, head_hash FROM file_state WHERE path=?", (str(path),)
    ).fetchone()
    offset = row["offset"] if row else 0
    if row and st.st_mtime == row["mtime"] and st.st_size == offset:
        return stats
    session_id = _codex_session_id(path)
    with path.open("rb") as fh:
        if row:
            span = min(512, row["offset"])
            head_hash = hashlib.sha256(fh.read(span)).hexdigest() if span else ""
            if (row["head_hash"] and head_hash != row["head_hash"]) or st.st_size < offset:
                _purge_transcript_rows(conn, path)
                offset = 0
        fh.seek(0)
        first_line = fh.readline(1_000_000)
        fh.seek(offset)
        blob = fh.read()

    def _remember(new_off: int) -> None:
        with path.open("rb") as fh2:
            stored = hashlib.sha256(fh2.read(min(512, new_off))).hexdigest()
        conn.execute(
            "INSERT INTO file_state(path, offset, mtime, head_hash) VALUES(?,?,?,?) "
            "ON CONFLICT(path) DO UPDATE SET offset=excluded.offset, mtime=excluded.mtime, "
            "head_hash=excluded.head_hash",
            (str(path), new_off, st.st_mtime, stored),
        )

    meta = _codex_meta(first_line)
    cwd = str(meta["cwd"]) if isinstance(meta, dict) and meta.get("cwd") is not None else None
    if not all_projects and cwd != str(root):
        # Foreign project (or unreadable head): consume to the tail so the stat
        # check short-circuits future passes without re-reading the file.
        _remember(st.st_size)
        return stats

    git = meta.get("git") if isinstance(meta, dict) else None
    parent_tid, agent_label = _codex_lineage(meta)
    _touch_session(
        conn, session_id,
        meta.get("timestamp") if isinstance(meta.get("timestamp"), str) else None,
        host="codex", source="transcript",
        cwd=cwd,
        git_branch=(git.get("branch") if isinstance(git, dict) else None),
        app_version=meta.get("cli_version"),
        agent_name=agent_label,
        transcript_path=str(path),
        # Full parent id (codex ids are time-ordered, so an 8-char prefix would
        # collide across temporally-close sessions -- match the whole id).
        team=("session-" + parent_tid) if parent_tid else None,
    )

    model: str | None = None
    if offset > 0:  # append batch: the turn_context may predate this window
        seed = conn.execute(
            "SELECT model FROM model_calls WHERE session_id=? AND model IS NOT NULL "
            "ORDER BY ts DESC LIMIT 1", (session_id,)
        ).fetchone()
        model = seed["model"] if seed else None

    end = blob.rfind(b"\n")
    if end < 0:
        return stats  # no complete new line yet; retry next pass
    new_offset = offset + end + 1
    last_ts: str | None = None
    for raw in blob[: end + 1].splitlines():
        if not raw.strip():
            continue
        stats["lines"] += 1
        try:
            line = json.loads(raw.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, ValueError):
            stats["skipped"] += 1
            continue
        if not isinstance(line, dict):
            stats["skipped"] += 1
            continue
        lts = line.get("timestamp")
        if isinstance(lts, str):
            last_ts = lts
        try:
            model = _index_codex_line(conn, line, session_id, model, stats)
        except (sqlite3.Error, TypeError, ValueError, AttributeError):
            # One hostile line degrades to one fewer row, never a dead pass.
            stats["skipped"] += 1
    if last_ts:
        _touch_session(conn, session_id, last_ts, host="codex", source="transcript")
    _remember(new_offset)
    return stats


# ---------------------------------------------------------------------------
# Wrapper adapter (droid / GLM)
# ---------------------------------------------------------------------------
# Factory Droid runs the GLM executor via the `droid-glm-exec` wrapper, a
# separate process whose model + tokens never reach a claude-code transcript.
# Droid's own session .jsonl files carry neither a structured model nor token
# usage (verified) and are pruned to ~20, so the only durable, model-tagged
# source is the wrapper's own append-only log: one record per exec run with
# {ts, model, cwd, session_id, mode, exit_code, ok}. We surface those as
# host='droid' sessions so GLM delegation is visible; token counts are simply
# not available from Droid, so model_calls carry 0 tokens (a run == one call).

def droid_wrapper_log() -> Path:
    return Path(
        os.environ.get("DROID_WRAPPER_LOG")
        or (Path.home() / ".factory" / "monitoring" / "droid-wrapper.jsonl")
    )


def _under_root(cwd: str | None, root: Path) -> bool:
    if not cwd:
        return False
    root_s = str(root)
    return cwd == root_s or cwd.startswith(root_s + os.sep)


def _index_droid_wrapper(conn: sqlite3.Connection, root: Path, all_projects: bool) -> dict[str, int]:
    """Ingest droid-glm-exec runs from the wrapper log (idempotent via run key).

    The log is small and append-only; re-parsing it whole each pass with
    INSERT OR IGNORE keeps the code offset-free while staying dedup-safe.
    """
    stats = {"lines": 0, "skipped": 0, "model_calls": 0, "tool_calls": 0}
    log = droid_wrapper_log()
    if not log.is_file():
        return stats
    try:
        raw = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return stats
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        stats["lines"] += 1
        try:
            rec = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            stats["skipped"] += 1
            continue
        # One completed run per wrapper_end record (start-only runs are rare
        # crashes with no outcome; skip them rather than log a phantom call).
        if not isinstance(rec, dict) or rec.get("event") != "wrapper_end":
            continue
        cwd = rec.get("cwd") if isinstance(rec.get("cwd"), str) else None
        if not all_projects and not _under_root(cwd, root):
            continue
        session_id = rec.get("session_id")
        ts = rec.get("ts") if isinstance(rec.get("ts"), str) else None
        if not isinstance(session_id, str) or not ts:
            stats["skipped"] += 1
            continue
        session_id = f"droid:{session_id}"  # namespaced: droid + claude UUIDs can collide
        model = rec.get("model") if isinstance(rec.get("model"), str) else "glm"
        mode = rec.get("mode") if isinstance(rec.get("mode"), str) else None
        prompt = rec.get("prompt_file")
        title = Path(prompt).stem if isinstance(prompt, str) and prompt else (f"GLM {mode} run" if mode else "GLM run")
        _touch_session(
            conn, session_id, ts, host="droid", source="wrapper",
            cwd=cwd, agent_name=mode, title=title,
        )
        # No token usage is available from Droid; a run is one model call.
        key = f"dwr:{session_id}:{ts}"
        cur = conn.execute(
            "INSERT OR IGNORE INTO model_calls(uuid, session_id, ts, model, agent, sidechain, "
            "input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens) "
            "VALUES(?,?,?,?,?,?,0,0,0,0)",
            (key, session_id, ts, model, mode, 0),
        )
        stats["model_calls"] += cur.rowcount if cur.rowcount > 0 else 0
        status = "ok" if rec.get("ok") else "error"
        cur = conn.execute(
            "INSERT OR IGNORE INTO tool_calls(id, session_id, ts, tool, target, agent, sidechain, status) "
            "VALUES(?,?,?,?,?,?,0,?)",
            (key, session_id, ts, f"droid:{mode}" if mode else "droid",
             _redact_target(Path(prompt).name) if isinstance(prompt, str) and prompt else "", mode, status),
        )
        stats["tool_calls"] += cur.rowcount if cur.rowcount > 0 else 0
    return stats


# ---------------------------------------------------------------------------
# CQL artifact adapter (host-neutral: records, reviews, memory, progress)
# ---------------------------------------------------------------------------

def _artifact_sources(root: Path) -> list[Path]:
    sources = []
    live = root / ".quality-loop" / "agent-record.json"
    if live.is_file():
        sources.append(live)
    records_dir = root / "docs" / "records"
    if records_dir.is_dir():
        sources.extend(sorted(records_dir.glob("*.json")))
    lessons = root / ".quality-loop" / "memory" / "lessons.jsonl"
    if lessons.is_file():
        sources.append(lessons)
    delegations = root / ".quality-loop" / "delegations.jsonl"
    if delegations.is_file():
        sources.append(delegations)
    progress = root / ".quality-loop" / "progress.md"
    if progress.is_file():
        sources.append(progress)
    return sources


def _finding_parts(entry: Any) -> tuple[str, str]:
    """Normalize one finding (dict or string) into (severity, text). Findings
    come in as free-form strings or {severity/level, text/finding/message}."""
    if isinstance(entry, dict):
        text = (entry.get("text") or entry.get("finding") or entry.get("message")
                or entry.get("detail") or entry.get("title") or "")
        sev = entry.get("severity") or entry.get("level") or "info"
        return str(sev), str(text)
    return "info", str(entry)


def _ingest_record(conn: sqlite3.Connection, path: Path, rel: str, mtime_iso: str) -> None:
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    if not isinstance(record, dict):
        return
    task = str(record.get("task_id") or rel)

    def put(kind: str, idx: Any, title: str, detail: dict[str, Any]) -> None:
        conn.execute(
            "INSERT INTO artifacts(key, source_path, kind, ts, title, detail) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET ts=excluded.ts, title=excluded.title, detail=excluded.detail",
            (f"{rel}#{kind}#{idx}", rel, kind, mtime_iso, title[:TITLE_MAX], json.dumps(detail)[:4000]),
        )

    put("record", 0, task, {
        "status": record.get("status"), "risk_tier": record.get("risk_tier"),
        "task_class": record.get("task_class"), "goal": str(record.get("goal") or "")[:300],
        "commands_run": len(record.get("commands_run") or []),
        "live": rel.startswith(".quality-loop"),
    })
    # Findings are first-class: the finding TEXT + severity + which gate fired
    # is the loop's most valuable proof, so project each into its own artifact
    # (not just the count kept on the review row). Sources: the top-level
    # review_findings[] and either review dict's own findings[] (array form).
    finding_idx = 0

    def put_findings(source: str, reviewer: Any, entries: Any) -> None:
        nonlocal finding_idx
        if not isinstance(entries, list):
            return
        for entry in entries:
            severity, text = _finding_parts(entry)
            put("finding", finding_idx,
                f"{task}: [{severity}] {text[:80]}",
                {"severity": severity, "text": text[:300], "reviewer": reviewer,
                 "task_id": task, "source": source})
            finding_idx += 1

    review = record.get("independent_review")
    if isinstance(review, dict):
        put("review", 0, f"{task}: {review.get('verdict', '?')} by {review.get('reviewer', '?')}", {
            "verdict": review.get("verdict"), "reviewer": review.get("reviewer"),
            "fresh_context": review.get("fresh_context"), "ran_checks": review.get("ran_checks"),
            "attested": bool(review.get("diff_sha256")),
            "findings": len(record.get("review_findings") or []),
            "kind": "independent",
        })
        put_findings("independent_review", review.get("reviewer"), review.get("findings"))
    security = record.get("security_review")
    if isinstance(security, dict):
        put("review", 1, f"{task}: security {security.get('verdict', '?')} by {security.get('reviewer', '?')}", {
            "verdict": security.get("verdict"), "reviewer": security.get("reviewer"),
            "fresh_context": security.get("fresh_context"), "ran_checks": security.get("ran_checks"),
            "attested": bool(security.get("diff_sha256")),
            "findings": len(security.get("findings") or []),
            "kind": "security",
        })
        put_findings("security_review", security.get("reviewer"), security.get("findings"))
    # Top-level review_findings[]: reviewer defaults to the independent reviewer.
    ind_reviewer = review.get("reviewer") if isinstance(review, dict) else None
    put_findings("review_findings", ind_reviewer, record.get("review_findings"))
    decision = record.get("minimality_decision")
    if isinstance(decision, dict) and decision.get("rung"):
        put("decision", 0, f"{task}: rung={decision.get('rung')}", {
            "rung": decision.get("rung"), "reason": str(decision.get("reason") or "")[:500],
        })
    plan = record.get("plan")
    if isinstance(plan, list) and plan:
        put("plan", 0, f"{task}: plan ({len(plan)} steps)", {"steps": [str(s)[:200] for s in plan[:12]]})
    for i, esc in enumerate(record.get("escalations") or []):
        if isinstance(esc, dict):
            put("escalation", i, f"{task}: {esc.get('from_model', '?')} -> {esc.get('to_model', '?')}", {
                "step": esc.get("step"), "trigger": esc.get("trigger"),
                "failing_commands": esc.get("failing_commands"), "attempts": esc.get("attempts"),
            })
    for i, used in enumerate(record.get("models_used") or []):
        if isinstance(used, dict):
            put("models_used", i, f"{task}: {used.get('role', '?')} = {used.get('model', '?')}", dict(used))


def _ingest_lessons(conn: sqlite3.Connection, path: Path, rel: str, mtime_iso: str) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for i, raw in enumerate(lines):
        if not raw.strip():
            continue
        try:
            lesson = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(lesson, dict):
            continue
        title = str(lesson.get("lesson") or lesson.get("name") or "lesson")[:TITLE_MAX]
        conn.execute(
            "INSERT INTO artifacts(key, source_path, kind, ts, title, detail) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET ts=excluded.ts, title=excluded.title, detail=excluded.detail",
            (f"{rel}#memory#{i}", rel, "memory", lesson.get("created_at") or mtime_iso, title,
             json.dumps({k: lesson.get(k) for k in ("kind", "scope", "confidence", "task_id") if k in lesson})),
        )


_DELEGATION_FIELDS = ("ts", "task_id", "role", "host", "model", "brief_summary", "expected_agent_name")


def _ingest_delegations(conn: sqlite3.Connection, path: Path, rel: str, mtime_iso: str) -> int:
    """Ingest the orchestrator's append-only ``.quality-loop/delegations.jsonl``.

    One JSON object per line: ts, task_id, role, host, model, brief_summary,
    expected_agent_name. Mirrors the lessons/JSONL pattern. Malformed lines are
    skipped and counted (returned), never crash the pass — the ledger is written
    by hand/agent and a half-flushed line must not break indexing.
    """
    skipped = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return skipped
    for i, raw in enumerate(lines):
        if not raw.strip():
            continue
        try:
            entry = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            skipped += 1
            continue
        if not isinstance(entry, dict):
            skipped += 1
            continue
        task = str(entry.get("task_id") or "?")
        role = str(entry.get("role") or "?")
        expected = entry.get("expected_agent_name")
        detail = {k: entry.get(k) for k in _DELEGATION_FIELDS if k in entry}
        if isinstance(detail.get("brief_summary"), str):
            detail["brief_summary"] = detail["brief_summary"][:300]
        conn.execute(
            "INSERT INTO artifacts(key, source_path, kind, ts, title, detail) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET ts=excluded.ts, title=excluded.title, detail=excluded.detail",
            (f"{rel}#delegation#{i}", rel, "delegation",
             entry.get("ts") or mtime_iso,
             f"{task}: {role} -> {expected or '?'}"[:TITLE_MAX], json.dumps(detail)[:4000]),
        )
    return skipped


def index_artifacts(conn: sqlite3.Connection, root: Path, totals: dict[str, int] | None = None) -> int:
    changed = 0
    # Deleted artifact sources must not haunt the index.
    for row in conn.execute(
        "SELECT path FROM file_state WHERE path LIKE 'artifact:%'"
    ).fetchall():
        rel = row["path"][len("artifact:"):]
        if not (root / rel).exists():
            conn.execute("DELETE FROM artifacts WHERE source_path=?", (rel,))
            conn.execute("DELETE FROM file_state WHERE path=?", (row["path"],))
            changed += 1
    for path in _artifact_sources(root):
        rel = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
        try:
            st = path.stat()
        except OSError:
            continue  # vanished between listing and stat (e.g. record archived)
        row = conn.execute("SELECT mtime FROM file_state WHERE path=?", (f"artifact:{rel}",)).fetchone()
        if row and row["mtime"] == st.st_mtime:
            continue
        changed += 1
        conn.execute("DELETE FROM artifacts WHERE source_path=?", (rel,))
        mtime_iso = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
        if path.name == "lessons.jsonl":
            _ingest_lessons(conn, path, rel, mtime_iso)
        elif path.name == "delegations.jsonl":
            skipped = _ingest_delegations(conn, path, rel, mtime_iso)
            if totals is not None:
                totals["skipped"] += skipped
        elif path.suffix == ".json":
            _ingest_record(conn, path, rel, mtime_iso)
        elif path.name == "progress.md":
            try:
                body = path.read_text(encoding="utf-8")[:4000]
            except OSError:
                body = ""
            conn.execute(
                "INSERT INTO artifacts(key, source_path, kind, ts, title, detail) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET ts=excluded.ts, title=excluded.title, detail=excluded.detail",
                (f"{rel}#progress#0", rel, "progress", mtime_iso, "progress.md", json.dumps({"body": body})),
            )
        conn.execute(
            "INSERT INTO file_state(path, offset, mtime) VALUES(?,?,?) "
            "ON CONFLICT(path) DO UPDATE SET offset=excluded.offset, mtime=excluded.mtime",
            (f"artifact:{rel}", 0, st.st_mtime),
        )
    return changed


# ---------------------------------------------------------------------------
# Index driver
# ---------------------------------------------------------------------------

def index_all(root: Path, all_projects: bool = False) -> dict[str, Any]:
    conn = open_db(root)
    try:
        started = time.time()
        totals = {"files": 0, "lines": 0, "skipped": 0, "model_calls": 0, "tool_calls": 0}
        for tdir, needs_cwd_check in transcript_dirs(root, all_projects):
            for path in sorted(tdir.glob("*.jsonl")):
                if needs_cwd_check and not _file_in_root(path, root):
                    continue
                totals["files"] += 1
                fstats = _index_transcript_file(conn, path)
                for key in ("lines", "skipped", "model_calls", "tool_calls"):
                    totals[key] += fstats[key]
        # Rollout adapter: Codex CLI sessions (host='codex'), scoped to this
        # repo by session_meta.cwd (all_projects lifts the scope).
        for path in codex_rollout_files():
            fstats = _index_codex_file(conn, path, root, all_projects)
            if fstats["lines"]:
                totals["files"] += 1
            for key in ("lines", "skipped", "model_calls", "tool_calls"):
                totals[key] += fstats[key]
        # Wrapper adapter: Droid/GLM exec runs (host='droid'), scoped by cwd.
        dstats = _index_droid_wrapper(conn, root, all_projects)
        for key in ("lines", "skipped", "model_calls", "tool_calls"):
            totals[key] += dstats[key]
        # Deleted transcripts must not haunt the index.
        for row in conn.execute(
            "SELECT path FROM file_state WHERE path NOT LIKE 'artifact:%'"
        ).fetchall():
            if not Path(row["path"]).exists():
                _purge_transcript_rows(conn, Path(row["path"]))
                conn.execute("DELETE FROM file_state WHERE path=?", (row["path"],))
        totals["artifact_sources_changed"] = index_artifacts(conn, root, totals)
        block = load_control_config(root)
        days = block.get("retention_days")
        days = days if isinstance(days, int) and not isinstance(days, bool) and days >= 1 else DEFAULT_RETENTION_DAYS
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        totals["events_pruned"] = conn.execute("DELETE FROM events WHERE ts < ?", (cutoff,)).rowcount
        if totals["skipped"]:
            prior = int(_meta_get(conn, "skipped_lines") or 0)
            _meta_set(conn, "skipped_lines", str(prior + totals["skipped"]))
        _meta_set(conn, "last_index_at", datetime.now(timezone.utc).isoformat())
        _meta_set(conn, "last_index_monotonic", str(time.time()))
        totals["duration_ms"] = int((time.time() - started) * 1000)
        conn.commit()
        return totals
    finally:
        conn.close()


_INDEX_LOCK = threading.Lock()


def maybe_index(root: Path) -> None:
    """Debounced reindex used by the server: cheap no-op inside the window.

    The lock keeps concurrent request threads from stampeding into
    ``index_all`` together, and the window is claimed BEFORE the work starts
    so late arrivals see a fresh timestamp.
    """
    if not _INDEX_LOCK.acquire(blocking=False):
        return
    try:
        conn = open_db(root)
        try:
            last = float(_meta_get(conn, "last_index_monotonic") or 0.0)
            if time.time() - last < INDEX_DEBOUNCE_SECS:
                return
            _meta_set(conn, "last_index_monotonic", str(time.time()))
            conn.commit()
        finally:
            conn.close()
        index_all(root)
    finally:
        _INDEX_LOCK.release()


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def _price_for(model: str | None, prices: dict[str, Any]) -> dict[str, float] | None:
    if not model or not prices:
        return None
    lower = model.lower()
    best = None
    for key, rates in prices.items():
        if isinstance(rates, dict) and key.lower() in lower:
            if best is None or len(key) > len(best[0]):
                best = (key, rates)
    return best[1] if best else None


def _cost(row: dict[str, Any], rates: dict[str, float] | None) -> float | None:
    if not rates:
        return None
    per = {
        "input_tokens": rates.get("input_per_mtok", 0.0),
        "output_tokens": rates.get("output_per_mtok", 0.0),
        "cache_read_tokens": rates.get("cache_read_per_mtok", 0.0),
        "cache_creation_tokens": rates.get("cache_creation_per_mtok", 0.0),
    }
    return round(sum(row.get(col, 0) * rate / 1_000_000 for col, rate in per.items()), 6)


def spend(conn: sqlite3.Connection, by: str = "model", prices: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    group = {
        "model": "COALESCE(model, 'unknown')",
        "day": "COALESCE(substr(ts, 1, 10), 'unknown')",
        "session": "session_id",
        "agent": "COALESCE(agent, 'main')",
    }.get(by, "COALESCE(model, 'unknown')")
    # Grouped per (key, model) so USD is priced per model even when the group
    # mixes models (a day or session with two models must not bill one price).
    rows = conn.execute(
        f"SELECT {group} AS key, COALESCE(model, 'unknown') AS model, COUNT(*) AS calls, "  # noqa: S608 - group is whitelisted above
        "SUM(input_tokens) AS input_tokens, SUM(output_tokens) AS output_tokens, "
        "SUM(cache_read_tokens) AS cache_read_tokens, SUM(cache_creation_tokens) AS cache_creation_tokens "
        f"FROM model_calls GROUP BY {group}, model"  # noqa: S608
    ).fetchall()
    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        sub = {k: row[k] if row[k] is not None else 0 for k in
               ("calls", "input_tokens", "output_tokens", "cache_read_tokens", "cache_creation_tokens")}
        sub_cost = _cost(sub, _price_for(row["model"], prices or {}))
        item = merged.setdefault(row["key"], {
            "key": row["key"], "calls": 0, "input_tokens": 0, "output_tokens": 0,
            "cache_read_tokens": 0, "cache_creation_tokens": 0, "cost_usd": None,
        })
        for k in ("calls", "input_tokens", "output_tokens", "cache_read_tokens", "cache_creation_tokens"):
            item[k] += sub[k]
        if sub_cost is not None:
            item["cost_usd"] = round((item["cost_usd"] or 0.0) + sub_cost, 6)
    return sorted(merged.values(), key=lambda item: -item["output_tokens"])


def overview(conn: sqlite3.Connection, prices: dict[str, Any] | None = None) -> dict[str, Any]:
    totals = dict(conn.execute(
        "SELECT COUNT(DISTINCT session_id) AS active_sessions, COUNT(*) AS model_calls, "
        "COALESCE(SUM(input_tokens),0) AS input_tokens, COALESCE(SUM(output_tokens),0) AS output_tokens, "
        "COALESCE(SUM(cache_read_tokens),0) AS cache_read_tokens, "
        "COALESCE(SUM(cache_creation_tokens),0) AS cache_creation_tokens FROM model_calls"
    ).fetchone())
    totals["sessions"] = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    totals["tool_calls"] = conn.execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0]
    by_model = spend(conn, "model", prices)
    costs = [r["cost_usd"] for r in by_model if r["cost_usd"] is not None]
    totals["cost_usd"] = round(sum(costs), 4) if costs else None
    by_day = sorted(spend(conn, "day", prices), key=lambda r: str(r["key"]), reverse=True)
    return {
        "totals": totals,
        # Most recent 30 days by DATE — a token-ordered slice would silently
        # drop recent quiet days once the history exceeds the window.
        "by_day": by_day[:30],
        "by_model": by_model,
        "last_index_at": _meta_get(conn, "last_index_at"),
        "skipped_lines": int(_meta_get(conn, "skipped_lines") or 0),
    }


def list_sessions(conn: sqlite3.Connection, limit: int = 200) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT s.*, "
        "(SELECT COUNT(*) FROM model_calls m WHERE m.session_id = s.id) AS model_calls, "
        "(SELECT COUNT(*) FROM tool_calls t WHERE t.session_id = s.id) AS tool_calls, "
        "(SELECT COALESCE(SUM(input_tokens),0) FROM model_calls m WHERE m.session_id = s.id) AS input_tokens, "
        "(SELECT COALESCE(SUM(output_tokens),0) FROM model_calls m WHERE m.session_id = s.id) AS output_tokens, "
        "(SELECT GROUP_CONCAT(DISTINCT model) FROM model_calls m WHERE m.session_id = s.id) AS models "
        "FROM sessions s ORDER BY COALESCE(s.last_activity_at, s.started_at) DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def session_detail(conn: sqlite3.Connection, session_id: str, prices: dict[str, Any] | None = None) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if row is None:
        return None
    models = conn.execute(
        "SELECT COALESCE(model,'unknown') AS key, COALESCE(agent,'main') AS agent, COUNT(*) AS calls, "
        "SUM(input_tokens) AS input_tokens, SUM(output_tokens) AS output_tokens, "
        "SUM(cache_read_tokens) AS cache_read_tokens, SUM(cache_creation_tokens) AS cache_creation_tokens "
        "FROM model_calls WHERE session_id=? GROUP BY key, agent ORDER BY output_tokens DESC",
        (session_id,),
    ).fetchall()
    model_rows = []
    for m in models:
        item = dict(m)
        for k in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_creation_tokens"):
            item[k] = item[k] or 0
        item["cost_usd"] = _cost(item, _price_for(m["key"], prices or {}))
        model_rows.append(item)
    tools = conn.execute(
        "SELECT ts, tool, target, agent, sidechain, status FROM tool_calls "
        "WHERE session_id=? ORDER BY ts DESC LIMIT 300",
        (session_id,),
    ).fetchall()
    events = conn.execute(
        "SELECT ts, name, detail FROM events WHERE session_id=? ORDER BY ts DESC LIMIT 100",
        (session_id,),
    ).fetchall()
    # Sub-agents: sessions this one spawned. Each child's team points back at the
    # parent -- claude uses "session-<parent 8-char prefix>", codex uses
    # "session-<full parent id>" (its ids are time-ordered, so a prefix collides).
    # Match either form so both hosts' children resolve.
    subagents = conn.execute(
        "SELECT s.id, s.agent_name, s.host, s.title, s.started_at, s.last_activity_at, "
        "(SELECT COUNT(*) FROM model_calls m WHERE m.session_id=s.id) AS model_calls, "
        "(SELECT COALESCE(SUM(output_tokens),0) FROM model_calls m WHERE m.session_id=s.id) AS output_tokens, "
        "(SELECT GROUP_CONCAT(DISTINCT model) FROM model_calls m WHERE m.session_id=s.id) AS models "
        "FROM sessions s WHERE (s.team = ? OR s.team = ?) AND s.id <> ? "
        "ORDER BY COALESCE(s.started_at, s.last_activity_at) ASC",
        ("session-" + session_id[:8], "session-" + session_id, session_id),
    ).fetchall()
    # Parent: the session named by this one's team token (if it was spawned).
    parent = None
    keys = row.keys()
    team = row["team"] if "team" in keys else None
    if isinstance(team, str) and team.startswith("session-"):
        ref = team[len("session-"):]
        prow = None
        if len(ref) >= 16:  # full id (codex): exact match, no prefix collision
            prow = conn.execute(
                "SELECT id, agent_name, title, host FROM sessions WHERE id = ? AND id <> ? LIMIT 1",
                (ref, session_id),
            ).fetchone()
        elif ref and not session_id.startswith(ref):  # 8-char prefix (claude)
            prow = conn.execute(
                "SELECT id, agent_name, title, host FROM sessions WHERE id LIKE ? AND id <> ? LIMIT 1",
                (ref + "%", session_id),
            ).fetchone()
        parent = dict(prow) if prow else None
    return {
        "session": dict(row),
        "models": model_rows,
        "tools": [dict(t) for t in tools],
        "events": [dict(e) for e in events],
        "subagents": [dict(s) for s in subagents],
        "parent": parent,
    }


def list_artifacts(conn: sqlite3.Connection, kinds: tuple[str, ...]) -> list[dict[str, Any]]:
    marks = ",".join("?" for _ in kinds)
    rows = conn.execute(
        f"SELECT source_path, kind, ts, title, detail FROM artifacts WHERE kind IN ({marks}) "  # noqa: S608
        "ORDER BY source_path, kind, key",
        kinds,
    ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        try:
            item["detail"] = json.loads(item["detail"]) if item["detail"] else {}
        except json.JSONDecodeError:
            item["detail"] = {}
        out.append(item)
    return out


def list_events(conn: sqlite3.Connection, limit: int = 200) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT session_id, host, ts, name, detail FROM events ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Query-time joins + aggregations (delegations, task timeline, loop metrics)
# ---------------------------------------------------------------------------
# Everything below is computed at request time from existing rows; nothing is
# stored. Keeping the joins out of the DB keeps the cache disposable and the
# joins honest (a stored join would silently rot when a source is reindexed).

# A delegation is matched to a session that started in this window around the
# delegation timestamp: the orchestrator records the delegation just before the
# worker's session begins, and a worker session rarely runs longer than an hour.
_DELEG_MATCH_BEFORE = timedelta(minutes=5)
_DELEG_MATCH_AFTER = timedelta(minutes=60)


def _parse_ts(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp to an aware UTC datetime, or None."""
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _session_tokens(conn: sqlite3.Connection, session_id: str) -> dict[str, int]:
    row = conn.execute(
        "SELECT COUNT(*) AS calls, COALESCE(SUM(input_tokens),0) AS input_tokens, "
        "COALESCE(SUM(output_tokens),0) AS output_tokens, "
        "COALESCE(SUM(cache_read_tokens),0) AS cache_read_tokens, "
        "COALESCE(SUM(cache_creation_tokens),0) AS cache_creation_tokens "
        "FROM model_calls WHERE session_id=?",
        (session_id,),
    ).fetchone()
    return {k: row[k] for k in ("calls", "input_tokens", "output_tokens",
                                "cache_read_tokens", "cache_creation_tokens")}


def _match_delegation(conn: sqlite3.Connection, expected: Any, ts: Any) -> dict[str, Any] | None:
    """Find the session a delegation ran in: agent_name == expected_agent_name
    AND started within [ts-5m, ts+60m]. Returns the session (+token totals) or
    None. When several match, the one nearest the delegation ts wins."""
    if not isinstance(expected, str) or not expected:
        return None
    when = _parse_ts(ts)
    rows = conn.execute(
        "SELECT id, host, agent_name, title, started_at, last_activity_at, ended_at "
        "FROM sessions WHERE agent_name=?",
        (expected,),
    ).fetchall()
    best: tuple[float, sqlite3.Row] | None = None
    for row in rows:
        started = _parse_ts(row["started_at"])
        if when is not None and started is not None:
            # Window is [ts-5m, ts+60m]: the session may start slightly before
            # the ledger line is flushed, but mostly after it.
            if not (when - _DELEG_MATCH_BEFORE <= started <= when + _DELEG_MATCH_AFTER):
                continue
            dist = abs((started - when).total_seconds())
        else:
            dist = 0.0
        if best is None or dist < best[0]:
            best = (dist, row)
    if best is None:
        return None
    row = best[1]
    out = dict(row)
    out["tokens"] = _session_tokens(conn, row["id"])
    return out


def delegations_with_sessions(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Every delegation artifact joined to its matched session at query time."""
    out = []
    for art in list_artifacts(conn, ("delegation",)):
        detail = art["detail"] if isinstance(art["detail"], dict) else {}
        matched = _match_delegation(conn, detail.get("expected_agent_name"),
                                    detail.get("ts") or art["ts"])
        item = {
            "task_id": detail.get("task_id"), "role": detail.get("role"),
            "host": detail.get("host"), "model": detail.get("model"),
            "brief_summary": detail.get("brief_summary"),
            "expected_agent_name": detail.get("expected_agent_name"),
            "ts": detail.get("ts") or art["ts"], "title": art["title"],
        }
        if matched:
            item["session"] = matched
            item["unmatched"] = False
        else:
            item["session"] = None
            item["unmatched"] = True
        out.append(item)
    return out


_TIMELINE_KINDS = ("record", "decision", "plan", "delegation", "escalation", "review", "finding")


def task_timeline(conn: sqlite3.Connection, task_id: str, prices: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Assemble a full audit timeline for one task_id from indexed artifacts
    (live record + docs/records history) + delegations + linked sessions/spend.
    Returns None when the task_id is unknown."""
    if not task_id:
        return None
    # The `record` artifact's title IS the task_id; find every source file that
    # carries a record for this task (live + any historical copies).
    record_arts = [a for a in list_artifacts(conn, ("record",)) if a["title"] == task_id]
    source_paths = {a["source_path"] for a in record_arts}
    # Delegations are matched by their own task_id field, not source file.
    delegations = [d for d in delegations_with_sessions(conn) if d.get("task_id") == task_id]
    if not source_paths and not delegations:
        return None
    events: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    escalations: list[dict[str, Any]] = []
    decision: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None
    for art in list_artifacts(conn, _TIMELINE_KINDS):
        if art["kind"] == "delegation":
            continue  # handled via delegations (adds the session join)
        if art["source_path"] not in source_paths:
            continue
        events.append({"ts": art["ts"], "kind": art["kind"], "title": art["title"],
                       "detail": art["detail"], "source_path": art["source_path"]})
        if art["kind"] == "review":
            reviews.append(art)
        elif art["kind"] == "finding":
            findings.append(art)
        elif art["kind"] == "escalation":
            escalations.append(art)
        elif art["kind"] == "decision":
            decision = art
        elif art["kind"] == "plan":
            plan = art
    for d in delegations:
        events.append({"ts": d["ts"], "kind": "delegation",
                       "title": d["title"], "detail": d})
    events.sort(key=lambda e: (str(e["ts"] or ""), e["kind"]))
    # Linked sessions: the matched sessions behind this task's delegations.
    sessions = [d["session"] for d in delegations if d.get("session")]
    spend_totals = {"calls": 0, "input_tokens": 0, "output_tokens": 0,
                    "cache_read_tokens": 0, "cache_creation_tokens": 0}
    for sess in sessions:
        for k in spend_totals:
            spend_totals[k] += sess.get("tokens", {}).get(k, 0)
    evidence_count = max((a["detail"].get("commands_run", 0) or 0 for a in record_arts), default=0)
    return {
        "task_id": task_id,
        "records": record_arts,
        "timeline": events,
        "reviews": reviews,
        "findings": findings,
        "escalations": escalations,
        "decision": decision,
        "plan": plan,
        "delegations": delegations,
        "evidence_count": evidence_count,
        "sessions": sessions,
        "spend": spend_totals,
    }


def _role_for_agent(agent: str | None, topo_agents: dict[str, Any]) -> str:
    """Map a transcript agent name to a CQL role via the routing topology.
    The topology's agent keys ARE the role names; 'main' is the orchestrator;
    anything else is 'other'."""
    if not agent or agent == "main":
        return "main"
    if agent in topo_agents:
        return agent
    return "other"


def loop_metrics(conn: sqlite3.Connection, root: Path, prices: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compute the loop KPIs the CQL skill defines. All query-time aggregation
    over existing rows; every ratio is division-by-zero safe (empty DB -> zeros)."""
    reviews = list_artifacts(conn, ("review",))
    verdicts: dict[str, int] = {}
    for r in reviews:
        v = str(r["detail"].get("verdict") or "unknown")
        verdicts[v] = verdicts.get(v, 0) + 1

    findings = list_artifacts(conn, ("finding",))
    by_severity: dict[str, int] = {}
    for f in findings:
        sev = str(f["detail"].get("severity") or "info")
        by_severity[sev] = by_severity.get(sev, 0) + 1

    escalation_arts = list_artifacts(conn, ("escalation",))
    repair_attempts = sum(int(e["detail"].get("attempts") or 0) for e in escalation_arts
                          if isinstance(e["detail"].get("attempts"), int))

    decisions = list_artifacts(conn, ("decision",))
    rungs: dict[str, int] = {}
    for d in decisions:
        rung = str(d["detail"].get("rung") or "unknown")
        rungs[rung] = rungs.get(rung, 0) + 1

    records = list_artifacts(conn, ("record",))
    with_evidence = sum(1 for r in records if (r["detail"].get("commands_run") or 0) > 0)
    evidence_rate = round(100.0 * with_evidence / len(records), 1) if records else 0.0

    # spend by role: agent_name -> role via routing topology.
    topo_agents: dict[str, Any] = {}
    cfg_path = root / "quality-loop.config.json"
    if cfg_path.is_file():
        try:
            config = json.loads(cfg_path.read_text(encoding="utf-8"))
            if isinstance(config, dict):
                topo_agents = qlroute.resolve_routing(config, None).get("agents", {}) or {}
        except (ValueError, OSError):
            topo_agents = {}
    by_role: dict[str, dict[str, Any]] = {}
    for row in spend(conn, "agent", prices):
        role = _role_for_agent(row["key"], topo_agents)
        item = by_role.setdefault(role, {"role": role, "calls": 0, "input_tokens": 0,
                                          "output_tokens": 0, "cache_read_tokens": 0,
                                          "cache_creation_tokens": 0, "cost_usd": None})
        for k in ("calls", "input_tokens", "output_tokens", "cache_read_tokens", "cache_creation_tokens"):
            item[k] += row.get(k, 0)
        if row.get("cost_usd") is not None:
            item["cost_usd"] = round((item["cost_usd"] or 0.0) + row["cost_usd"], 6)

    durations = []
    for s in conn.execute(
        "SELECT id, title, host, agent_name, started_at, last_activity_at, ended_at FROM sessions"
    ).fetchall():
        start = _parse_ts(s["started_at"])
        end = _parse_ts(s["ended_at"]) or _parse_ts(s["last_activity_at"])
        secs = round((end - start).total_seconds(), 1) if (start and end and end >= start) else None
        durations.append({"id": s["id"], "title": s["title"], "host": s["host"],
                          "agent_name": s["agent_name"], "duration_sec": secs})

    return {
        "verdict_distribution": verdicts,
        "findings_by_severity": by_severity,
        "escalations": len(escalation_arts),
        "repair_attempts": repair_attempts,
        "rung_distribution": rungs,
        "evidence_rate": {"records": len(records), "with_evidence": with_evidence,
                          "rate_pct": evidence_rate},
        "spend_by_role": sorted(by_role.values(), key=lambda r: -r["output_tokens"]),
        "session_durations": durations,
    }


# ---------------------------------------------------------------------------
# Hook ingest (never breaks a session)
# ---------------------------------------------------------------------------

def ingest_event(root: Path, payload: dict[str, Any], event: str, host: str = "claude-code") -> bool:
    """Record one host hook event. Returns False when the plane is disabled.

    Opt-in by design: without ``control_plane.enabled: true`` in the repo
    config, nothing is written — installing the hooks must not silently start
    collecting data.
    """
    block = load_control_config(root)
    if block.get("enabled") is not True:
        return False
    conn = open_db(root)
    try:
        ts = datetime.now(timezone.utc).isoformat()
        session_id = payload.get("session_id") or payload.get("sessionId")
        session_id = str(session_id) if session_id else None
        if session_id:
            _touch_session(conn, session_id, ts, host=host, source="hook",
                           cwd=payload.get("cwd"),
                           transcript_path=payload.get("transcript_path"))
            if event.lower() == "sessionend":
                conn.execute("UPDATE sessions SET ended_at=? WHERE id=?", (ts, session_id))
        detail = {k: payload.get(k) for k in ("source", "hook_event_name", "reason") if payload.get(k)}
        conn.execute(
            "INSERT INTO events(session_id, host, ts, name, detail) VALUES(?,?,?,?,?)",
            (session_id, host, ts, event, json.dumps(detail) if detail else None),
        )
        conn.commit()
        return True
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

def _dashboard_path() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "control-plane" / "dashboard.html"


_FALLBACK_PAGE = (
    "<!doctype html><meta charset='utf-8'><title>CQL control plane</title>"
    "<body style='font-family:system-ui;padding:2rem'><h1>Control plane is running</h1>"
    "<p>assets/control-plane/dashboard.html was not found next to scripts/. "
    "Re-run scripts/install.py (or copy the assets/ directory) to get the dashboard UI. "
    "The JSON API is live: <a href='/api/overview'>/api/overview</a></p></body>"
)


class _Handler(BaseHTTPRequestHandler):
    server_version = "CQLControlPlane"
    root: Path  # set by serve()

    def log_message(self, fmt: str, *args: Any) -> None:  # quiet by design
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, data: Any) -> None:
        self._send(code, json.dumps(data).encode("utf-8"), "application/json; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        self._json(405, {"error": "the control plane API is read-only (GET only)"})

    do_PUT = do_POST  # noqa: N815
    do_DELETE = do_POST  # noqa: N815
    do_PATCH = do_POST  # noqa: N815
    do_HEAD = do_POST  # noqa: N815 - docs promise 405 for everything non-GET
    do_OPTIONS = do_POST  # noqa: N815

    def _host_allowed(self) -> bool:
        """DNS-rebinding guard: a hostile page can point its own hostname at
        127.0.0.1 and read this unauthenticated API from a browser. Loopback
        spellings only; anything else gets 403."""
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]").lower()
        return host in ("", "127.0.0.1", "localhost", "::1")

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        try:
            if not self._host_allowed():
                self._json(403, {"error": "unrecognized Host header (DNS-rebinding guard); use http://127.0.0.1:<port>/"})
                return
            self._route()
        except BrokenPipeError:
            pass
        except Exception as exc:  # noqa: BLE001 - a bad request must not kill the server thread
            try:
                self._json(500, {"error": str(exc)[:500]})
            except Exception:  # noqa: BLE001
                pass

    def _limit(self, query: dict[str, str], default: int = 200) -> int | None:
        """Clamped limit param; None means the value was not an integer."""
        raw = query.get("limit", str(default)) or str(default)
        try:
            n = int(raw)
        except ValueError:
            return None
        return max(1, min(n, 1000))

    def _route(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        root = self.root
        if path == "/":
            page = _dashboard_path()
            body = page.read_bytes() if page.is_file() else _FALLBACK_PAGE.encode("utf-8")
            self._send(200, body, "text/html; charset=utf-8")
            return
        if path == "/healthz":
            conn = open_db(root)
            try:
                n = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            finally:
                conn.close()
            self._json(200, {"ok": True, "sessions": n, "root": str(root)})
            return
        if not path.startswith("/api/"):
            self._json(404, {"error": f"unknown path: {path}"})
            return
        maybe_index(root)
        prices = load_control_config(root).get("prices")
        prices = prices if isinstance(prices, dict) else {}
        conn = open_db(root)
        try:
            if path == "/api/overview":
                self._json(200, overview(conn, prices))
            elif path == "/api/sessions":
                limit = self._limit(query)
                if limit is None:
                    self._json(400, {"error": "limit must be an integer"})
                else:
                    self._json(200, {"sessions": list_sessions(conn, limit)})
            elif path == "/api/session":
                detail = session_detail(conn, query.get("id", ""), prices)
                self._json(200 if detail else 404, detail or {"error": "unknown session id"})
            elif path == "/api/spend":
                by = query.get("by", "model")
                if by not in ("model", "day", "session", "agent"):
                    self._json(400, {"error": "by must be one of model|day|session|agent"})
                else:
                    self._json(200, {"by": by, "rows": spend(conn, by, prices)})
            elif path == "/api/records":
                self._json(200, {"artifacts": list_artifacts(
                    conn, ("record", "review", "decision", "plan", "escalation", "models_used", "finding"))})
            elif path == "/api/delegations":
                self._json(200, {"delegations": delegations_with_sessions(conn)})
            elif path == "/api/task":
                task_id = query.get("task_id", "")
                if not task_id:
                    self._json(400, {"error": "task_id is required"})
                else:
                    timeline = task_timeline(conn, task_id, prices)
                    self._json(200 if timeline else 404,
                               timeline or {"error": f"unknown task_id: {task_id}"})
            elif path == "/api/metrics":
                self._json(200, loop_metrics(conn, root, prices))
            elif path == "/api/memory":
                lessons = list_artifacts(conn, ("memory",))
                progress = list_artifacts(conn, ("progress",))
                self._json(200, {"lessons": lessons, "progress": progress[0] if progress else None})
            elif path == "/api/events":
                limit = self._limit(query)
                if limit is None:
                    self._json(400, {"error": "limit must be an integer"})
                else:
                    self._json(200, {"events": list_events(conn, limit)})
            elif path == "/api/routing":
                self._json(200, _routing_snapshot(root))
            else:
                self._json(404, {"error": f"unknown API path: {path}"})
        finally:
            conn.close()


def _routing_snapshot(root: Path) -> dict[str, Any]:
    info = qlroute.brief_routing_info(root)
    snapshot: dict[str, Any] = {
        "configured": bool(info.get("configured")),
        "lines": info.get("lines") or [],
    }
    cfg_path = root / "quality-loop.config.json"
    if cfg_path.is_file():
        try:
            config = json.loads(cfg_path.read_text(encoding="utf-8"))
            if not isinstance(config, dict):
                return snapshot
            topo = qlroute.resolve_routing(config, None)
            snapshot["topology"] = {
                "default_host": topo["default_host"],
                "hosts_in_use": topo["hosts_in_use"],
                "agents": topo["agents"],
                "main_session": topo["main_session"],
                "allow_same_family": topo["allow_same_family"],
            }
        except (ValueError, OSError):
            pass
    return snapshot


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        # os.kill(pid, 0) on Windows calls TerminateProcess — it would KILL the
        # process it is probing. Query for liveness via a limited-rights handle.
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def server_state(root: Path) -> dict[str, Any] | None:
    """The recorded server state, or None. Removes stale state files."""
    path = server_state_path(root)
    if not path.is_file():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        state = None
    if not isinstance(state, dict) or not _pid_alive(int(state.get("pid") or -1)):
        try:
            path.unlink()
        except OSError:
            pass
        return None
    return state


def healthy_server(root: Path) -> dict[str, Any] | None:
    """Server state, but only if something behind the recorded port answers
    /healthz for THIS root. Pid-liveness alone is not identity — pids get
    recycled. A pid-alive-but-unresponsive state file is removed."""
    state = server_state(root)
    if not state:
        return None
    import urllib.request
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{int(state.get('port') or -1)}/healthz", timeout=3
        ) as res:
            health = json.loads(res.read().decode("utf-8"))
        if (isinstance(health, dict) and isinstance(health.get("root"), str)
                and Path(health["root"]).resolve() == root.resolve()):
            return state
    except (OSError, ValueError):
        pass
    try:
        server_state_path(root).unlink()
    except OSError:
        pass
    return None


def resolve_port(root: Path, cli_port: int | None) -> int:
    if cli_port:
        return cli_port
    block = load_control_config(root)
    port = block.get("port")
    if isinstance(port, int) and not isinstance(port, bool) and 1024 <= port <= 65535:
        return port
    return DEFAULT_PORT


def serve(root: Path, port: int) -> int:
    existing = healthy_server(root)
    if existing:
        print(f"control plane already running: pid={existing['pid']} http://127.0.0.1:{existing['port']}/")
        return 0
    handler = type("BoundHandler", (_Handler,), {"root": root})
    # Localhost is hard-coded on purpose: the API has no auth layer, so it must
    # never be reachable off-machine. The bind address is not configurable.
    # Bind BEFORE indexing: the port doubles as the double-start lock, so two
    # concurrent SessionStart autostarts cannot both index the same DB — the
    # loser dies here on EADDRINUSE before touching anything.
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    except OSError as exc:
        print(
            f"control plane: cannot bind 127.0.0.1:{port} ({exc.strerror or exc}). "
            "Another process owns the port — stop it (control-stop), pick another "
            "port (--port / control_plane.port), or check control-status.",
            file=sys.stderr,
        )
        return 1
    state = {
        "pid": os.getpid(),
        "port": port,
        "root": str(root),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    _ensure_control_dir(root)
    server_state_path(root).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    def _shutdown(signum: int, frame: Any) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _shutdown)
    # Index in the background so /healthz answers the moment the port is
    # bound — a slow first index must not look like an unresponsive server
    # to concurrent autostart guards. Early requests see a partial index
    # that converges; maybe_index keeps it fresh afterwards.
    threading.Thread(target=lambda: maybe_index(root), daemon=True).start()
    print(f"control plane: http://127.0.0.1:{port}/  (db: {db_path(root)})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        try:
            server_state_path(root).unlink()
        except OSError:
            pass
    return 0


# ---------------------------------------------------------------------------
# CLI commands (registered by quality_loop.py)
# ---------------------------------------------------------------------------

def _root_from(args: Any) -> Path:
    return Path(getattr(args, "cwd", None) or os.getcwd()).resolve()


def cmd_index(args: Any) -> int:
    root = _root_from(args)
    stats = index_all(root, all_projects=bool(getattr(args, "all_projects", False)))
    if getattr(args, "json", False):
        print(json.dumps(stats, indent=2))
    else:
        print(
            f"indexed {stats['files']} transcript file(s): "
            f"+{stats['model_calls']} model calls, +{stats['tool_calls']} tool calls, "
            f"{stats['artifact_sources_changed']} artifact source(s) refreshed, "
            f"{stats['skipped']} line(s) skipped, {stats['duration_ms']}ms"
        )
        print(f"db: {db_path(root)}")
    return 0


def cmd_serve(args: Any) -> int:
    root = _root_from(args)
    return serve(root, resolve_port(root, getattr(args, "port", None)))


def cmd_status(args: Any) -> int:
    root = _root_from(args)
    state = server_state(root)
    payload: dict[str, Any] = {
        "db": str(db_path(root)),
        "db_exists": db_path(root).is_file(),
        "server": state,
        "enabled": load_control_config(root).get("enabled") is True,
    }
    if payload["db_exists"]:
        conn = open_db(root)
        try:
            payload["sessions"] = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            payload["model_calls"] = conn.execute("SELECT COUNT(*) FROM model_calls").fetchone()[0]
            payload["last_index_at"] = _meta_get(conn, "last_index_at")
        finally:
            conn.close()
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2))
    else:
        print(f"db: {payload['db']} ({'present' if payload['db_exists'] else 'absent'})")
        if state:
            print(f"server: running pid={state['pid']} http://127.0.0.1:{state['port']}/")
        else:
            print("server: not running (start: python3 scripts/quality_loop.py control-serve)")
        print(f"config: control_plane.enabled={'true' if payload['enabled'] else 'false/absent'}")
        if payload["db_exists"]:
            print(f"sessions: {payload.get('sessions')}  model_calls: {payload.get('model_calls')}  "
                  f"last_index: {payload.get('last_index_at')}")
    return 0


def cmd_stop(args: Any) -> int:
    root = _root_from(args)
    if server_state(root) is None:
        print("control plane server is not running")
        return 0
    # A recycled PID must never get our SIGTERM: only kill a process that
    # answers /healthz for THIS root on the recorded port.
    state = healthy_server(root)
    if not state:
        print("no responsive control-plane server behind the recorded pid; removed stale state (nothing killed)")
        return 0
    os.kill(int(state["pid"]), signal.SIGTERM)
    print(f"sent SIGTERM to control plane server pid={state['pid']}")
    return 0


def _pick_record(records: list[dict[str, Any]]) -> dict[str, Any]:
    """The live record if present, else the first (historical) one."""
    for r in records:
        if r["detail"].get("live"):
            return r
    return records[0] if records else {"detail": {}}


def _fmt_tokens(spend_totals: dict[str, int]) -> str:
    return (f"{spend_totals.get('calls', 0)} calls, "
            f"{spend_totals.get('input_tokens', 0)} in / {spend_totals.get('output_tokens', 0)} out, "
            f"{spend_totals.get('cache_read_tokens', 0)} cache-read")


def render_report_md(bundle: dict[str, Any]) -> str:
    rec = _pick_record(bundle.get("records") or [])["detail"]
    lines = [f"# Audit report: {bundle['task_id']}", ""]
    lines.append(f"- Goal: {rec.get('goal') or '(unknown)'}")
    lines.append(f"- Status: {rec.get('status') or '(unknown)'}")
    lines.append(f"- Class / risk: {rec.get('task_class') or '?'} / {rec.get('risk_tier') or '?'}")
    decision = bundle.get("decision")
    if decision:
        d = decision["detail"]
        lines += ["", "## Minimality decision",
                  f"- Rung: {d.get('rung')}", f"- Reason: {d.get('reason')}"]
    plan = bundle.get("plan")
    if plan:
        lines += ["", "## Plan"]
        for i, step in enumerate(plan["detail"].get("steps") or [], 1):
            lines.append(f"{i}. {step}")
    delegations = bundle.get("delegations") or []
    if delegations:
        lines += ["", "## Delegations"]
        for d in delegations:
            head = f"- {d.get('role')} -> {d.get('expected_agent_name')} [{d.get('host')}/{d.get('model')}]"
            if d.get("brief_summary"):
                head += f": {d['brief_summary']}"
            lines.append(head)
            sess = d.get("session")
            if sess:
                t = sess.get("tokens", {})
                lines.append(f"    matched session {sess['id']} "
                             f"({t.get('input_tokens', 0)} in / {t.get('output_tokens', 0)} out)")
            else:
                lines.append("    unmatched (no session found in the delegation window)")
    lines += ["", "## Evidence", f"- Commands run: {bundle.get('evidence_count', 0)}"]
    reviews = bundle.get("reviews") or []
    lines += ["", "## Verdicts"]
    if reviews:
        for r in reviews:
            rd = r["detail"]
            lines.append(f"- {rd.get('kind', 'review')}: {rd.get('verdict')} by "
                         f"{rd.get('reviewer')} (findings: {rd.get('findings', 0)}, "
                         f"attested: {bool(rd.get('attested'))})")
    else:
        lines.append("- (none recorded)")
    findings = bundle.get("findings") or []
    lines += ["", "## Findings"]
    if findings:
        for f in findings:
            fd = f["detail"]
            lines.append(f"- [{fd.get('severity')}] {fd.get('text')} "
                         f"({fd.get('source')}, {fd.get('reviewer')})")
    else:
        lines.append("- (none recorded)")
    escalations = bundle.get("escalations") or []
    if escalations:
        lines += ["", "## Escalations"]
        for e in escalations:
            ed = e["detail"]
            lines.append(f"- {e['title']} (trigger: {ed.get('trigger')}, attempts: {ed.get('attempts')})")
    lines += ["", "## Spend (linked sessions)", f"- {_fmt_tokens(bundle.get('spend') or {})}"]
    sessions = bundle.get("sessions") or []
    lines += ["", "## Sessions"]
    if sessions:
        for s in sessions:
            t = s.get("tokens", {})
            lines.append(f"- {s['id']} [{s.get('host')}] {s.get('agent_name') or ''} "
                         f"({t.get('input_tokens', 0)} in / {t.get('output_tokens', 0)} out)")
    else:
        lines.append("- (no linked sessions)")
    return "\n".join(lines) + "\n"


def cmd_report(args: Any) -> int:
    """Emit a per-task audit bundle (markdown default, --json optional).

    Exit 0 on success; exit 2 with a helpful message when the task is unknown.
    """
    root = _root_from(args)
    task_id = str(getattr(args, "task_id", "") or "")
    if not task_id:
        print("control-report: --task-id is required", file=sys.stderr)
        return 2
    conn = open_db(root)
    try:
        prices = load_control_config(root).get("prices")
        prices = prices if isinstance(prices, dict) else {}
        bundle = task_timeline(conn, task_id, prices)
    finally:
        conn.close()
    if bundle is None:
        print(
            f"control-report: no task found with task_id={task_id!r}. "
            "Run 'control-index' first, or check the id against '/api/records' "
            "(the record artifact title is the task_id).",
            file=sys.stderr,
        )
        return 2
    if getattr(args, "json", False):
        print(json.dumps(bundle, indent=2))
    else:
        print(render_report_md(bundle), end="")
    return 0


def cmd_ingest(args: Any) -> int:
    """Hook entry point. Contract: NEVER fail the host session (always exit 0).

    This deliberately swallows all errors (logged to ingest-errors.log): a
    broken observability plane must degrade to "no data", never to a session
    that cannot start or stop. The gates live elsewhere and stay loud.
    """
    root = _root_from(args)
    try:
        # Opt-in is checked BEFORE anything is read or written: a disabled
        # repo must stay byte-identical even when the hook feeds us garbage.
        if load_control_config(root).get("enabled") is not True:
            return 0
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            payload = {}
        ingest_event(root, payload, str(getattr(args, "event", "") or "unknown"),
                     host=str(getattr(args, "host", "") or "claude-code"))
    except Exception as exc:  # noqa: BLE001 - see docstring
        try:
            _ensure_control_dir(root)
            with ingest_error_log(root).open("a", encoding="utf-8") as fh:
                fh.write(f"{datetime.now(timezone.utc).isoformat()} {exc!r}\n")
        except OSError:
            pass
    return 0
