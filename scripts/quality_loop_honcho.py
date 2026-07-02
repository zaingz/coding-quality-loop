#!/usr/bin/env python3
"""Honcho-backed lessons store (optional runtime dep).

Honcho (https://honcho.dev) is a reasoning-based agent memory service. This
module implements the same recall/commit contract as the files backend so the
Coding Quality Loop can degrade gracefully:

- Config `memory.lessons_store = "honcho"` activates this adapter.
- If the `honcho-ai` SDK is not installed OR the API key is unavailable OR the
  network call fails, we fall back to the files backend and print a one-line
  degradation notice on stderr. The loop must never break because a network
  memory backend is unreachable.
- Every lesson egressed to Honcho is first passed through the project redactor,
  so the redaction fix in scripts/quality_loop.py is enforced at the boundary.

The SDK is imported lazily inside `_client()` so importing this module has zero
runtime cost when Honcho is not configured. See references/memory-honcho.md for
the workspace/peer/session model this adapter mirrors.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

import quality_loop_memory as qlmem


# Metadata key we stamp on every lesson so we can round-trip lessons committed
# by this adapter without confusing them with arbitrary session messages.
_LESSON_TAG = "coding_quality_loop.lesson.v1"


def _fallback_notice(reason: str) -> None:
    sys.stderr.write(f"honcho backend unavailable ({reason}); falling back to files backend\n")


# Default endpoint for a local `docker compose up` Honcho instance. When users
# self-host with `AUTH_USE_AUTH=false` (see the Honcho self-hosting guide) the
# API accepts requests with no key at all. We default to this so the common
# case "I ran honcho locally" needs zero configuration.
_DEFAULT_LOCAL_BASE_URL = "http://localhost:8000"


def _resolve_config(config: dict[str, Any] | None) -> dict[str, Any]:
    """Merge env + config into an adapter-ready dict.

    Precedence: env > config-file. Secrets (api_key) always come from env,
    never from a committed config, to avoid accidental commits.

    Local-first defaults: when neither env nor config provides a base_url we
    use `http://localhost:8000`. When neither provides an api_key AND the URL
    is local we send no auth header, which is what a self-hosted Honcho with
    `AUTH_USE_AUTH=false` expects. Managed cloud still requires a key.
    """
    cfg = dict((config or {}).get("honcho") or {})
    api_key = os.environ.get("HONCHO_API_KEY", "").strip()
    base_url = (
        os.environ.get("HONCHO_BASE_URL", "").strip()
        or str(cfg.get("base_url") or "").strip()
        or _DEFAULT_LOCAL_BASE_URL
    )
    workspace_id = cfg.get("workspace_id") or os.environ.get("HONCHO_WORKSPACE_ID", "")
    peer_id = cfg.get("peer_id") or os.environ.get("HONCHO_PEER_ID", "")
    session_template = cfg.get("session_template", "ql-lessons")
    return {
        "api_key": api_key,
        "base_url": base_url,
        "workspace_id": str(workspace_id or "").strip(),
        "peer_id": str(peer_id or "").strip(),
        "session_template": str(session_template).strip() or "ql-lessons",
    }


def _is_local_base_url(base_url: str) -> bool:
    """True for base URLs that point at a local / self-hosted instance.

    Used to decide when a missing api_key is acceptable. Matches on hostnames
    rather than a scheme so `http://127.0.0.1:8000`, `http://localhost:8000`,
    and `http://host.docker.internal:8000` all qualify. This keeps the managed
    cloud path strict (api_key required) while removing friction locally.
    """
    lowered = base_url.lower()
    markers = ("localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal", ".local", "://[::1]")
    return any(m in lowered for m in markers)


def _client(cfg: dict[str, Any]):
    """Return (client, None) or (None, reason) if unavailable.

    Local base URLs allow an empty api_key. Non-local base URLs still require
    a key so we never silently ship a keyless request to the managed cloud.

    Accepts either a resolved cfg (produced by `_resolve_config`) or a raw
    Honcho config block; missing keys fall back to the same defaults as
    `_resolve_config` so direct callers never KeyError.
    """
    workspace_id = str(cfg.get("workspace_id") or "").strip()
    peer_id = str(cfg.get("peer_id") or "").strip()
    if not workspace_id or not peer_id:
        return None, "honcho.workspace_id and honcho.peer_id required"
    base_url = str(cfg.get("base_url") or "").strip() or _DEFAULT_LOCAL_BASE_URL
    api_key = str(cfg.get("api_key") or "").strip()
    is_local = _is_local_base_url(base_url)
    if not api_key and not is_local:
        return None, (
            f"HONCHO_API_KEY not set and base_url {base_url!r} is not a "
            "recognised local endpoint; managed Honcho requires an API key"
        )
    try:
        # Lazy import: the module is optional. `honcho-ai` is the pypi name of the
        # official Python SDK; keep the import inside the function so consumers
        # with only the files backend never need it installed.
        from honcho import Honcho  # type: ignore
    except ImportError as exc:
        return None, f"honcho-ai SDK not installed ({exc})"
    kwargs: dict[str, Any] = {
        "base_url": base_url,
        "workspace_id": workspace_id,
    }
    # Only pass api_key when we actually have one. Some self-hosted deployments
    # reject a bare `Authorization: Bearer ` header even with auth disabled, so
    # omitting the kwarg is safer than passing an empty string.
    if api_key:
        kwargs["api_key"] = api_key
    try:
        return Honcho(**kwargs), None
    except Exception as exc:  # SDK surface may vary; degrade rather than crash.
        return None, f"honcho client init failed: {exc}"


def _session_name(cfg: dict[str, Any]) -> str:
    # One session per project. `cwd` name gives a stable, human-legible label
    # without leaking the full path.
    return f"{cfg['session_template']}-{Path.cwd().name}"


def _lesson_to_message(lesson: dict[str, Any]) -> dict[str, Any]:
    """Render a lesson as a Honcho message with metadata for retrieval."""
    return {
        "content": qlmem.render_line(lesson),
        "metadata": {
            "tag": _LESSON_TAG,
            "id": lesson.get("id"),
            "kind": lesson.get("kind"),
            "risk_tier": lesson.get("risk_tier"),
            "scope_globs": lesson.get("scope_globs", []),
            "keywords": lesson.get("keywords", []),
            "source_task_id": lesson.get("source_task_id", ""),
            "created": lesson.get("created", ""),
            "hits": int(lesson.get("hits", 0) or 0),
        },
    }


def _message_to_lesson(msg: Any) -> dict[str, Any] | None:
    """Best-effort reverse of _lesson_to_message.

    Honcho SDK message objects expose `.content` and `.metadata`; we defensively
    handle plain dicts too. Anything without our tag is skipped.
    """
    metadata = getattr(msg, "metadata", None) or (msg.get("metadata") if isinstance(msg, dict) else None) or {}
    if metadata.get("tag") != _LESSON_TAG:
        return None
    content = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else "") or ""
    # Content is the rendered digest line; recover the raw lesson body if we can,
    # but fall back to content so we always return something searchable.
    lesson_text = content
    if content.startswith("- [") and "] " in content:
        lesson_text = content.split("] ", 1)[1]
    return {
        "id": metadata.get("id"),
        "created": metadata.get("created", ""),
        "source_task_id": metadata.get("source_task_id", ""),
        "kind": metadata.get("kind", "gotcha"),
        "risk_tier": metadata.get("risk_tier", "low"),
        "scope_globs": list(metadata.get("scope_globs") or []),
        "keywords": list(metadata.get("keywords") or []),
        "lesson": lesson_text,
        "hits": int(metadata.get("hits", 0) or 0),
    }


class HonchoBackend:
    """Adapter with the same shape as the files backend recall/commit API.

    Purposely narrow: two methods that mirror the CLI subcommands. Anything the
    files backend does that Honcho cannot (atomic dedup, disk-hit counting) is
    delegated back to the files fallback rather than emulated.
    """

    def __init__(self, config: dict[str, Any] | None):
        self.cfg = _resolve_config(config)
        self.client, self.error = _client(self.cfg)

    @property
    def available(self) -> bool:
        return self.client is not None

    def recall(self, goal: str, files: list[str], risk: str, budget_chars: int) -> list[dict[str, Any]]:
        """Search the Honcho session for our tagged lessons, then rerank locally.

        We use Honcho's `search` (cheap retrieval) rather than `chat` (LLM call)
        per references/memory-honcho.md. The local rerank is important: Honcho
        may not know our path-glob / risk-tier scoring, so we fetch a candidate
        set and pipe it through the exact same `qlmem.recall` we use for files.
        This keeps the recall contract identical across backends.
        """
        assert self.client is not None
        try:
            session = self.client.peer(self.cfg["peer_id"]).session(_session_name(self.cfg))
            # SDK convention: session.search(query) returns iterable of messages.
            results = session.search(goal or "*")
        except Exception as exc:
            _fallback_notice(f"honcho search failed: {exc}")
            return []
        lessons: list[dict[str, Any]] = []
        for msg in results or []:
            lesson = _message_to_lesson(msg)
            if lesson and lesson.get("lesson"):
                lessons.append(lesson)
        # Reuse the files-backend scorer for identical ranking semantics.
        return qlmem.recall(lessons, goal, files, risk, budget_chars)

    def commit(self, lessons: list[dict[str, Any]]) -> int:
        """Post one message-per-lesson.

        Every lesson has already been through `qlmem.normalize_lesson` (which
        applies the project redactor); we re-run the redactor here as a
        defense-in-depth boundary check before egress.
        """
        assert self.client is not None
        try:
            from quality_loop import redact
        except ImportError:
            def redact(x: str) -> str:  # type: ignore
                return x
        posted = 0
        try:
            session = self.client.peer(self.cfg["peer_id"]).session(_session_name(self.cfg))
        except Exception as exc:
            _fallback_notice(f"honcho session open failed: {exc}")
            return 0
        for lesson in lessons:
            # Redact both the lesson text and any keyword tokens at the boundary.
            safe = dict(lesson)
            safe["lesson"] = redact(str(lesson.get("lesson", "")))
            safe["keywords"] = [redact(str(k)) for k in lesson.get("keywords", []) if str(k).strip()]
            message = _lesson_to_message(safe)
            try:
                session.add_messages([message])
                posted += 1
            except Exception as exc:
                _fallback_notice(f"honcho commit skipped one lesson: {exc}")
        return posted


def _load_config(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fallback_notice(f"could not read {path}: {exc}")
        return None


def _use_honcho(config: dict[str, Any] | None) -> bool:
    memory = (config or {}).get("memory") or {}
    return memory.get("lessons_store") == "honcho"


def cmd_recall_honcho(args: Any) -> int:
    """Drop-in replacement for `qlmem.cmd_recall` when Honcho is configured.

    Contract: same stdout format (json or human digest), same exit code, same
    budget semantics. If Honcho is not available, we transparently defer to the
    files backend — the loop never surfaces a hard failure to the caller.
    """
    config = _load_config(getattr(args, "config", None))
    if not _use_honcho(config):
        return qlmem.cmd_recall(args)
    backend = HonchoBackend((config or {}).get("memory"))
    if not backend.available:
        _fallback_notice(backend.error or "unknown")
        return qlmem.cmd_recall(args)
    goal = args.goal or ""
    files = qlmem._split_files(args.files)
    budget = max(1, qlmem._safe_int(getattr(args, "budget", 1500), 1500))
    lessons = backend.recall(goal, files, args.risk, budget)
    if getattr(args, "json", False):
        print(json.dumps(lessons, indent=2))
    else:
        print(qlmem.format_digest(lessons, budget))
    return 0


def cmd_commit_honcho(args: Any) -> int:
    """Distill an agent record and mirror lessons into Honcho.

    Design choice: dual-write. We always run the files commit first (source of
    truth, offline-safe) and then mirror the same rows to Honcho if configured.
    This keeps the files audit trail intact for review and CI while giving
    Honcho users the reasoning-time recall path.
    """
    rc = qlmem.cmd_commit(args)
    if rc != 0:
        return rc
    config = _load_config(getattr(args, "config", None))
    if not _use_honcho(config):
        return 0
    backend = HonchoBackend((config or {}).get("memory"))
    if not backend.available:
        _fallback_notice(backend.error or "unknown")
        return 0
    record_path = Path(args.record)
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    override_scope = [args.scope] if getattr(args, "scope", None) else None
    rows = qlmem.distill_record(
        record,
        date.today().isoformat(),
        override_lesson=getattr(args, "lesson", None),
        override_kind=getattr(args, "kind", None),
        override_scope=override_scope,
    )
    posted = backend.commit(rows)
    if posted:
        print(f"mirrored {posted} lesson(s) to Honcho session '{_session_name(backend.cfg)}'")
    return 0
