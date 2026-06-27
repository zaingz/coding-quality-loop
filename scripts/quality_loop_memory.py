#!/usr/bin/env python3
"""Files-backed, stdlib-only lessons memory for the Coding Quality Loop.

The default (and only dependency-free) lessons-store backend. Honcho and
Graphify are documented in references/ and driven by the agent over MCP/CLI;
this module is the reference implementation and the offline eval target.
"""

from __future__ import annotations

import difflib
import fnmatch
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

LESSON_KINDS = {"failure_mode", "convention", "gotcha", "preference"}
RISK_TIERS = {"low", "medium", "high"}
_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


def slugify(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", path).strip("-")


def resolve_memory_dir(
    location: str = "checked_in",
    cwd: Path | None = None,
    home: Path | None = None,
) -> Path:
    cwd = cwd or Path.cwd()
    home = home or Path.home()
    if location == "local":
        return home / ".quality-loop" / slugify(str(cwd.resolve()))
    return cwd / ".quality-loop" / "memory"


def lesson_id(text: str) -> str:
    return hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:12]


_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "you", "are", "not", "but",
    "its", "into", "from", "was", "were", "has", "have", "had", "will", "your",
    "our", "their", "them", "then", "than", "out", "via", "per", "off", "all",
    "any", "can", "may", "use", "using", "add", "fix", "must", "should", "when",
    "where", "which", "while", "here", "there",
}


def _tokens(text: str) -> set[str]:
    return {
        w.lower()
        for w in _WORD_RE.findall(text or "")
        if len(w) > 2 and w.lower() not in _STOPWORDS
    }


def _safe_int(value: Any, default: int = 0) -> int:
    """Coerce a possibly hand-edited JSONL value to int without crashing."""
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clean_lesson_text(text: Any) -> str:
    """Collapse internal whitespace (keeps MEMORY.md one physical line per
    lesson) and redact secrets before a lesson is persisted to the checked-in
    store. Redaction reuses the project's existing patterns; if the main module
    is unavailable, whitespace collapsing still applies."""
    collapsed = " ".join(str(text or "").split())
    try:
        from quality_loop import redact
    except ImportError:
        return collapsed
    return redact(collapsed)


def normalize_lesson(raw: dict[str, Any], created: str) -> dict[str, Any]:
    text = _clean_lesson_text(raw.get("lesson", ""))
    kind = raw.get("kind") if raw.get("kind") in LESSON_KINDS else "gotcha"
    risk = raw.get("risk_tier") if raw.get("risk_tier") in RISK_TIERS else "low"
    hits_raw = raw.get("hits", 0)
    hits = 0 if isinstance(hits_raw, bool) else int(hits_raw) if isinstance(hits_raw, int) else 0
    return {
        "id": raw.get("id") or lesson_id(text),
        "created": raw.get("created") or created,
        "source_task_id": str(raw.get("source_task_id", "")),
        "kind": kind,
        "risk_tier": risk,
        "scope_globs": [str(g) for g in raw.get("scope_globs", []) if str(g).strip()],
        "keywords": [str(k).lower() for k in raw.get("keywords", []) if str(k).strip()],
        "lesson": text,
        "hits": hits,
    }


def load_lessons(mem_dir: Path) -> list[dict[str, Any]]:
    path = mem_dir / "lessons.jsonl"
    if not path.is_file():
        return []
    lessons: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and str(obj.get("lesson", "")).strip():
            lessons.append(obj)
    return lessons


def append_lesson(mem_dir: Path, lesson: dict[str, Any]) -> None:
    mem_dir.mkdir(parents=True, exist_ok=True)
    with (mem_dir / "lessons.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(lesson, sort_keys=True) + "\n")


def save_lessons(mem_dir: Path, lessons: list[dict[str, Any]]) -> None:
    mem_dir.mkdir(parents=True, exist_ok=True)
    path = mem_dir / "lessons.jsonl"
    body = "".join(json.dumps(l, sort_keys=True) + "\n" for l in lessons)
    # Unique temp file per writer (matches quality_loop.write_json) so concurrent
    # writers cannot clobber a shared temp path before the atomic os.replace.
    with tempfile.NamedTemporaryFile(
        "w", delete=False, dir=mem_dir, prefix="lessons.", suffix=".tmp", encoding="utf-8"
    ) as fh:
        fh.write(body)
        tmp_path = Path(fh.name)
    os.replace(tmp_path, path)


def score_lesson(lesson: dict[str, Any], goal_tokens: set[str], files: list[str], risk: str) -> float:
    keywords = {str(k).lower() for k in lesson.get("keywords", [])} | _tokens(lesson.get("lesson", ""))
    keyword_overlap = len(goal_tokens & keywords) if goal_tokens else 0
    path_match = False
    for glob in lesson.get("scope_globs", []):
        if glob == "**":
            continue  # repo-wide membership is not a concrete relevance signal
        if any(fnmatch.fnmatch(f, glob) for f in files):
            path_match = True
            break
    if keyword_overlap == 0 and not path_match:
        return 0.0  # no concrete relevance -> not recalled
    score = 2.0 * keyword_overlap
    if path_match:
        score += 3.0
    if risk and lesson.get("risk_tier") == risk:
        score += 1.0
    score += min(_safe_int(lesson.get("hits", 0)), 5) * 0.1
    return score


def render_line(lesson: dict[str, Any]) -> str:
    return f"- [{lesson.get('kind', '?')}/{lesson.get('risk_tier', '?')}] {str(lesson.get('lesson', '')).strip()}"


def recall(
    lessons: list[dict[str, Any]],
    goal: str,
    files: list[str],
    risk: str,
    budget_chars: int,
) -> list[dict[str, Any]]:
    goal_tokens = _tokens(goal)
    scored = [(score_lesson(l, goal_tokens, files, risk), l) for l in lessons]
    scored = [(s, l) for s, l in scored if s > 0]
    scored.sort(key=lambda sl: (-sl[0], str(sl[1].get("id", ""))))
    selected: list[dict[str, Any]] = []
    used = 0
    for _, l in scored:
        line_len = len(render_line(l)) + 1
        if selected and used + line_len > budget_chars:
            break
        selected.append(l)
        used += line_len
    return selected


def format_digest(lessons: list[dict[str, Any]], budget_chars: int) -> str:
    if not lessons:
        return "No prior lessons matched."
    body = "\n".join(render_line(l) for l in lessons)
    if len(body) > budget_chars:
        body = body[:budget_chars].rstrip()
    return body


def write_index(mem_dir: Path, lessons: list[dict[str, Any]], max_lines: int = 40) -> None:
    mem_dir.mkdir(parents=True, exist_ok=True)
    ranked = sorted(
        lessons,
        key=lambda x: (_safe_int(x.get("hits", 0)), str(x.get("created", ""))),
        reverse=True,
    )
    header = [
        "# Project Memory (index)",
        "",
        f"{len(lessons)} lesson(s). Recall detail with: python3 scripts/quality_loop.py memory-recall.",
        "",
    ]
    body_budget = max(max_lines - len(header), 0)
    body = [render_line(l) for l in ranked[:body_budget]]
    (mem_dir / "MEMORY.md").write_text("\n".join(header + body) + "\n", encoding="utf-8")


def bump_hits(mem_dir: Path, ids: list[str]) -> None:
    idset = set(ids)
    lessons = load_lessons(mem_dir)
    for l in lessons:
        if l.get("id") in idset:
            l["hits"] = _safe_int(l.get("hits", 0)) + 1
    save_lessons(mem_dir, lessons)
    write_index(mem_dir, lessons)


def _split_files(value: str | None) -> list[str]:
    return [f.strip() for f in (value or "").split(",") if f.strip()]


def cmd_recall(args: Any) -> int:
    budget = max(1, _safe_int(getattr(args, "budget", 1500), 1500))
    mem_dir = resolve_memory_dir(args.location)
    lessons = load_lessons(mem_dir)
    selected = recall(lessons, args.goal or "", _split_files(args.files), args.risk, budget)
    if selected and not getattr(args, "no_bump", False):
        bump_hits(mem_dir, [str(l.get("id", "")) for l in selected])
    if args.json:
        print(json.dumps(selected, indent=2))
    else:
        print(format_digest(selected, budget))
    return 0


def artifact_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        parts = [
            str(v).strip()
            for v in value.values()
            if isinstance(v, (str, int, float)) and not isinstance(v, bool) and str(v).strip()
        ]
        return "; ".join(parts)
    return ""


def files_to_globs(files: list[str]) -> list[str]:
    globs: list[str] = []
    for f in files:
        directory = "/".join(f.split("/")[:-1])
        glob = (directory + "/**") if directory else f
        if glob and glob not in globs:
            globs.append(glob)
    return globs or ["**"]


def _make_row(
    lesson: str, kind: str, risk: str, scope: list[str], task_id: str
) -> dict[str, Any]:
    return {
        "lesson": lesson,
        "kind": kind,
        "risk_tier": risk,
        "scope_globs": scope,
        "keywords": sorted(_tokens(_clean_lesson_text(lesson)))[:12],
        "source_task_id": task_id,
    }


def _record_files(record: dict[str, Any]) -> list[str]:
    files: list[str] = []
    repo_map = record.get("repo_map") or {}
    for key in ("likely_files", "entry_points"):
        for entry in repo_map.get(key, []) or []:
            path = str(entry).split(":")[0].strip()
            if path and path not in files:
                files.append(path)
    return files


def distill_record(
    record: dict[str, Any],
    created: str,
    override_lesson: str | None = None,
    override_kind: str | None = None,
    override_scope: list[str] | None = None,
) -> list[dict[str, Any]]:
    risk = record.get("risk_tier") if record.get("risk_tier") in RISK_TIERS else "low"
    task_id = str(record.get("task_id", ""))
    scope = override_scope or files_to_globs(_record_files(record))
    raw_rows: list[dict[str, Any]] = []

    if override_lesson and override_lesson.strip():
        raw_rows.append(_make_row(override_lesson.strip(), override_kind or "gotcha", risk, scope, task_id))
    else:
        harness = artifact_text(record.get("harness_update"))
        if harness:
            kind = "failure_mode" if record.get("repeated_failure") else "convention"
            raw_rows.append(_make_row(harness, kind, risk, scope, task_id))
        decision = record.get("minimality_decision") or {}
        reason = str(decision.get("reason", "")).strip()
        if reason:
            rung = decision.get("rung", "")
            raw_rows.append(
                _make_row(f"Prefer rung '{rung}': {reason}", "preference", risk, scope, task_id)
            )
        for finding in record.get("review_findings", []) or []:
            text = finding if isinstance(finding, str) else artifact_text(finding)
            text = str(text).strip()
            if text and "approv" not in text.lower():
                raw_rows.append(_make_row(f"Review note: {text}", "gotcha", risk, scope, task_id))

    return [normalize_lesson(r, created) for r in raw_rows if str(r.get("lesson", "")).strip()]


def cmd_commit(args: Any) -> int:
    record_path = Path(args.record)
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: could not read record {args.record!r}: {exc}", file=sys.stderr)
        return 1
    if not isinstance(record, dict):
        print(f"error: record {args.record!r} is not a JSON object", file=sys.stderr)
        return 1
    mem_dir = resolve_memory_dir(args.location)
    created = date.today().isoformat()
    override_scope = [args.scope] if getattr(args, "scope", None) else None
    rows = distill_record(
        record, created,
        override_lesson=getattr(args, "lesson", None),
        override_kind=getattr(args, "kind", None),
        override_scope=override_scope,
    )
    if not rows:
        print(
            "no lesson distilled (record has no harness_update/minimality/review and no --lesson)",
            file=sys.stderr,
        )
        return 1
    existing = load_lessons(mem_dir)
    existing_ids = {l.get("id") for l in existing}
    added = 0
    for row in rows:
        if row["id"] in existing_ids:
            continue
        append_lesson(mem_dir, row)
        existing.append(row)
        existing_ids.add(row["id"])
        added += 1
    write_index(mem_dir, existing)
    print(f"committed {added} lesson(s) to {mem_dir / 'lessons.jsonl'}")
    return 0


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def prune(
    lessons: list[dict[str, Any]],
    max_n: int = 200,
    max_age_days: int = 365,
    now: date | None = None,
) -> list[dict[str, Any]]:
    now = now or date.today()
    fresh: list[dict[str, Any]] = []
    for l in lessons:
        created = _parse_date(l.get("created"))
        if created and _safe_int(l.get("hits", 0)) == 0 and (now - created).days > max_age_days:
            continue
        fresh.append(l)
    deduped: list[dict[str, Any]] = []
    for l in sorted(fresh, key=lambda x: (_safe_int(x.get("hits", 0)), str(x.get("created", ""))), reverse=True):
        text = str(l.get("lesson", ""))
        if any(
            difflib.SequenceMatcher(None, text, str(k.get("lesson", ""))).ratio() >= 0.92
            for k in deduped
        ):
            continue
        deduped.append(l)
    deduped.sort(key=lambda x: (_safe_int(x.get("hits", 0)), str(x.get("created", ""))), reverse=True)
    return deduped[:max_n]


def cmd_prune(args: Any) -> int:
    mem_dir = resolve_memory_dir(args.location)
    lessons = load_lessons(mem_dir)
    kept = prune(lessons, max_n=args.max, max_age_days=args.max_age_days)
    save_lessons(mem_dir, kept)
    write_index(mem_dir, kept)
    print(f"pruned {len(lessons) - len(kept)} lesson(s); {len(kept)} remain")
    return 0


def count_kinds(lessons: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for l in lessons:
        kind = str(l.get("kind", "?"))
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def validate_memory_config(memory: Any) -> list[str]:
    if not isinstance(memory, dict):
        return ["memory must be an object"]
    errors: list[str] = []
    if memory.get("lessons_store", "files") not in {"files", "honcho"}:
        errors.append("memory.lessons_store must be 'files' or 'honcho'")
    if memory.get("graph_relevance", "none") not in {"none", "graphify"}:
        errors.append("memory.graph_relevance must be 'none' or 'graphify'")
    if memory.get("location", "checked_in") not in {"checked_in", "local"}:
        errors.append("memory.location must be 'checked_in' or 'local'")
    budget = memory.get("recall_budget_chars", 1500)
    if isinstance(budget, bool) or not isinstance(budget, int) or budget <= 0:
        errors.append("memory.recall_budget_chars must be a positive integer")
    return errors


def cmd_status(args: Any) -> int:
    lessons_store, graph_relevance, location = "files", "none", args.location
    config_error = None
    config_path = getattr(args, "config", None)
    if config_path:
        try:
            cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
            mem_cfg = cfg.get("memory") or {}
            lessons_store = mem_cfg.get("lessons_store", "files")
            graph_relevance = mem_cfg.get("graph_relevance", "none")
            location = mem_cfg.get("location", args.location)
        except (OSError, json.JSONDecodeError) as exc:
            config_error = f"could not read {config_path}: {exc}"
    mem_dir = resolve_memory_dir(location)
    lessons = load_lessons(mem_dir)
    status: dict[str, Any] = {
        "memory_dir": str(mem_dir),
        "exists": (mem_dir / "lessons.jsonl").is_file(),
        "location": location,
        "lessons_store": lessons_store,
        "graph_relevance": graph_relevance,
        "lesson_count": len(lessons),
        "kinds": count_kinds(lessons),
        "note": "files is the coded backend; honcho/graphify are agent-driven and degrade to files when unavailable",
    }
    if config_error:
        status["config_error"] = config_error
    print(json.dumps(status, indent=2))
    return 0
