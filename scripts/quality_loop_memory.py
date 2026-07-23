#!/usr/bin/env python3
"""Files-backed, stdlib-only lessons memory for the Coding Quality Loop.

The default (and only dependency-free) lessons-store backend. This module is
the reference implementation and the offline eval target.
"""

from __future__ import annotations

import difflib
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

import quality_loop_core as qlcore

LESSON_KINDS = {"failure_mode", "convention", "gotcha", "preference"}
OUTCOMES = ("clean", "regressed", "reverted")
RISK_TIERS = {"low", "medium", "high"}
# Small constant prior added to global-store lessons in the single ranked pool:
# they compete on score against project lessons instead of holding a quota.
GLOBAL_PRIOR = 0.5
_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


def slugify(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", path).strip("-")


def effective_location(explicit: str | None, cwd: Path | None = None) -> str:
    """An explicit --location always wins; otherwise the root config's
    memory.location; otherwise checked_in. Round-2 review (2026-07-23) caught
    the half-wiring this closes: init-record's preview honored the config
    while every documented memory command and brief defaulted to checked_in,
    so a configured-local repo committed lessons to a store recall never read."""
    if explicit:
        return explicit
    config = qlcore.load_gate_config(cwd)
    location = (config.get("memory") or {}).get("location")
    return location if location in ("checked_in", "local") else "checked_in"


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


def resolve_global_memory_dir(home: Path | None = None) -> Path:
    home = home or Path.home()
    return home / ".quality-loop" / "global"


def lesson_id(text: str) -> str:
    return hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:12]


_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "you", "are", "not", "but",
    "its", "into", "from", "was", "were", "has", "have", "had", "will", "your",
    "our", "their", "them", "then", "than", "out", "via", "per", "off", "all",
    "any", "can", "may", "use", "using", "add", "fix", "must", "should", "when",
    "where", "which", "while", "here", "there",
    "test", "tests", "error", "file", "code", "run",
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
    store. Redaction reuses the shared quality_loop_core patterns."""
    collapsed = " ".join(str(text or "").split())
    return qlcore.redact(collapsed)


def normalize_lesson(raw: dict[str, Any], created: str) -> dict[str, Any]:
    text = _clean_lesson_text(raw.get("lesson", ""))
    kind = raw.get("kind") if raw.get("kind") in LESSON_KINDS or raw.get("kind") == "outcome" else "gotcha"
    risk = raw.get("risk_tier") if raw.get("risk_tier") in RISK_TIERS else "low"
    hits = _safe_int(raw.get("hits", 0))
    row = {
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
    if raw.get("outcome") in OUTCOMES:
        row["outcome"] = raw["outcome"]
    source = raw.get("source")
    if isinstance(source, dict):
        src = {
            k: str(v).strip()
            for k, v in source.items()
            if k in ("task_id", "git_author") and str(v).strip()
        }
        if src:
            row["source"] = src
    return row


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
    body = "".join(json.dumps(l, sort_keys=True) + "\n" for l in lessons)
    # One atomic write for the whole package (unique temp file per writer +
    # os.replace, temp cleaned up on failure). See quality_loop_core.
    qlcore.atomic_write_text(mem_dir / "lessons.jsonl", body)


def score_lesson(lesson: dict[str, Any], goal_tokens: set[str], files: list[str], risk: str) -> float:
    if lesson.get("kind") == "outcome":
        return 0.0  # outcome rows are shipped-status feedback for brief, not recallable advice
    keywords = {str(k).lower() for k in lesson.get("keywords", [])} | _tokens(lesson.get("lesson", ""))
    keyword_overlap = len(goal_tokens & keywords) if goal_tokens else 0
    path_match = False
    for glob in lesson.get("scope_globs", []):
        if glob == "**":
            continue  # repo-wide membership is not a concrete relevance signal
        if any(fnmatch.fnmatch(f, glob) for f in files):
            path_match = True
            break
    if keyword_overlap < 2 and not path_match:
        return 0.0  # relevance floor: >=2 shared tokens or a scope_glob hit
    score = 2.0 * keyword_overlap
    if path_match:
        score += 3.0
    if risk and lesson.get("risk_tier") == risk:
        score += 1.0
    score += min(_safe_int(lesson.get("hits", 0)), 5) * 0.1
    return score


def has_provenance(lesson: dict[str, Any]) -> bool:
    return isinstance(lesson.get("source"), dict) and bool(lesson.get("source"))


def render_line(lesson: dict[str, Any], global_: bool = False, mark_provenance: bool = False) -> str:
    prefix = "[global] " if global_ else ""
    marker = "" if not mark_provenance or has_provenance(lesson) else " [unattributed]"
    return (
        f"- {prefix}[{lesson.get('kind', '?')}/{lesson.get('risk_tier', '?')}]"
        f"{marker} {str(lesson.get('lesson', '')).strip()}"
    )


def recall_pool(
    project_lessons: list[dict[str, Any]],
    global_lessons: list[dict[str, Any]],
    goal: str,
    files: list[str],
    risk: str,
    budget_chars: int,
) -> list[tuple[dict[str, Any], bool]]:
    """One ranked pool under one budget. Global lessons compete on score with a
    small constant prior (GLOBAL_PRIOR) instead of a reserved quota, so a
    non-matching global store never shrinks project recall."""
    goal_tokens = _tokens(goal)
    scored: list[tuple[float, str, dict[str, Any], bool]] = []
    for l in project_lessons:
        s = score_lesson(l, goal_tokens, files, risk)
        if s > 0:
            scored.append((s, str(l.get("id", "")), l, False))
    for l in global_lessons:
        s = score_lesson(l, goal_tokens, files, risk)
        if s > 0:
            scored.append((s + GLOBAL_PRIOR, str(l.get("id", "")), l, True))
    scored.sort(key=lambda t: (-t[0], t[1]))
    selected: list[tuple[dict[str, Any], bool]] = []
    used = 0
    for _, _, l, g in scored:
        line_len = len(render_line(l, global_=g, mark_provenance=True)) + 1
        if selected and used + line_len > budget_chars:
            break
        selected.append((l, g))
        used += line_len
    return selected


def recall(
    lessons: list[dict[str, Any]],
    goal: str,
    files: list[str],
    risk: str,
    budget_chars: int,
) -> list[dict[str, Any]]:
    return [l for l, _ in recall_pool(lessons, [], goal, files, risk, budget_chars)]


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


def _config_recall_budget(cwd: Path | None = None) -> int | None:
    """memory.recall_budget_chars from the canonical root config, or None."""
    path = (cwd or Path.cwd()) / "quality-loop.config.json"
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    memory = config.get("memory") if isinstance(config, dict) else None
    budget = memory.get("recall_budget_chars") if isinstance(memory, dict) else None
    if isinstance(budget, int) and not isinstance(budget, bool) and budget > 0:
        return budget
    return None


def cmd_recall(args: Any) -> int:
    raw_budget = getattr(args, "budget", None)
    if raw_budget is None:  # explicit --budget wins; config supplies the default
        raw_budget = _config_recall_budget() or 1500
    budget = max(1, _safe_int(raw_budget, 1500))
    mem_dir = resolve_memory_dir(effective_location(args.location))
    global_dir = resolve_global_memory_dir()
    pairs = recall_pool(
        load_lessons(mem_dir), load_lessons(global_dir),
        args.goal or "", _split_files(args.files), args.risk, budget,
    )
    if pairs and getattr(args, "bump", False):
        # Recall is read-only by default; --bump is the RETROSPECT-time opt-in.
        project_ids = [str(l.get("id", "")) for l, g in pairs if not g]
        global_ids = [str(l.get("id", "")) for l, g in pairs if g]
        if project_ids:
            bump_hits(mem_dir, project_ids)
        if global_ids:
            bump_hits(global_dir, global_ids)
    if args.json:
        print(json.dumps([l for l, _ in pairs], indent=2))
    elif pairs:
        body = "\n".join(render_line(l, global_=g, mark_provenance=True) for l, g in pairs)
        print(body[:budget].rstrip() if len(body) > budget else body)
    else:
        print("No prior lessons matched.")
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


def _git_author() -> str | None:
    """Best-effort `git config user.name`; None when git/config is absent."""
    try:
        proc = subprocess.run(
            ["git", "config", "user.name"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    name = (proc.stdout or "").strip()
    return name or None


def provenance(task_id: str = "") -> dict[str, str]:
    """source object for newly written rows; absent fields are omitted."""
    src: dict[str, str] = {}
    if str(task_id).strip():
        src["task_id"] = str(task_id).strip()
    author = _git_author()
    if author:
        src["git_author"] = author
    return src


def outcome_row(
    outcome: str, note: str, record: dict[str, Any], created: str,
    override_scope: list[str] | None = None,
) -> dict[str, Any]:
    text = _clean_lesson_text(note) or f"task shipped {outcome}"
    task_id = str(record.get("task_id", ""))
    return normalize_lesson(
        {
            "id": lesson_id(f"outcome {outcome} {task_id} {created} {text}"),
            "kind": "outcome",
            "outcome": outcome,
            "lesson": text,
            "risk_tier": record.get("risk_tier"),
            "scope_globs": override_scope or files_to_globs(_record_files(record)),
            "source_task_id": task_id,
        },
        created,
    )


def outcome_lines(lessons: list[dict[str, Any]], limit: int = 3) -> list[str]:
    """Most recent shipped-outcome rows, newest first, for the session brief."""
    indexed = [
        (str(l.get("created", "")), i, l)
        for i, l in enumerate(lessons)
        if l.get("kind") == "outcome"
    ]
    indexed.sort(key=lambda t: (t[0], t[1]), reverse=True)
    lines: list[str] = []
    for pos, (_, _, l) in enumerate(indexed[:limit]):
        label = "last shipped" if pos == 0 else "prior"
        lines.append(f"{label}: {l.get('outcome', '?')} — {str(l.get('lesson', '')).strip()}")
    return lines


def cmd_commit(args: Any) -> int:
    outcome = getattr(args, "outcome", None)
    if outcome is not None and outcome not in OUTCOMES:
        print(f"error: --outcome must be one of {list(OUTCOMES)}, got {outcome!r}", file=sys.stderr)
        return 1
    record_path = Path(args.record) if getattr(args, "record", None) else None
    if record_path:
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error: could not read record {args.record!r}: {exc}", file=sys.stderr)
            return 1
        if not isinstance(record, dict):
            print(f"error: record {args.record!r} is not a JSON object", file=sys.stderr)
            return 1
    elif getattr(args, "lesson", None) or outcome:
        record = {"task_id": "manual", "risk_tier": "low"}
    else:
        print("error: a record path, --lesson, or --outcome is required", file=sys.stderr)
        return 1
    mem_dir = resolve_global_memory_dir() if getattr(args, "global_store", False) else resolve_memory_dir(effective_location(args.location))
    created = date.today().isoformat()
    override_scope = [args.scope] if getattr(args, "scope", None) else None
    if outcome:
        rows = [outcome_row(outcome, getattr(args, "note", "") or "", record, created, override_scope)]
    else:
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
    source = provenance(str(record.get("task_id", "")))
    if source:
        for row in rows:
            row["source"] = source
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


def _tree_files(cwd: Path | None = None, cap: int = 20000) -> list[str]:
    """Repo-relative files in the current tree: `git ls-files`, else a capped
    walk that skips dot-directories. Best-effort; empty list on failure."""
    cwd = cwd or Path.cwd()
    try:
        proc = subprocess.run(
            ["git", "ls-files"], cwd=cwd, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, timeout=15, check=False,
        )
        if proc.returncode == 0:
            files = [f.strip() for f in proc.stdout.splitlines() if f.strip()]
            if files:
                return files[:cap]
    except (OSError, subprocess.SubprocessError):
        pass
    files = []
    for root, dirs, names in os.walk(cwd):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        rel_root = os.path.relpath(root, cwd)
        for n in names:
            rel = n if rel_root == "." else f"{rel_root}/{n}"
            files.append(rel.replace(os.sep, "/"))
            if len(files) >= cap:
                return files
    return files


def stale_candidates(
    lessons: list[dict[str, Any]], tree_files: list[str]
) -> list[dict[str, Any]]:
    """Lessons whose scope_globs match ZERO files in the current tree. Flagged
    for review at prune time, never auto-deleted."""
    stale: list[dict[str, Any]] = []
    for l in lessons:
        globs = [str(g) for g in l.get("scope_globs", []) if str(g).strip()]
        if not globs:
            continue
        if any(g == "**" or any(fnmatch.fnmatch(f, g) for f in tree_files) for g in globs):
            continue
        stale.append(l)
    return stale


def cmd_prune(args: Any) -> int:
    mem_dir = resolve_global_memory_dir() if getattr(args, "global_store", False) else resolve_memory_dir(effective_location(args.location))
    lessons = load_lessons(mem_dir)
    kept = prune(lessons, max_n=args.max, max_age_days=args.max_age_days)
    save_lessons(mem_dir, kept)
    write_index(mem_dir, kept)
    print(f"pruned {len(lessons) - len(kept)} lesson(s); {len(kept)} remain")
    stale = stale_candidates(kept, _tree_files())
    for l in stale:
        print(
            f"stale candidate (scope_globs match no file in the current tree): "
            f"[{l.get('id', '?')}] {str(l.get('lesson', ''))[:80]}"
        )
    if stale:
        print(f"{len(stale)} stale candidate(s) kept — fix their scope_globs or delete the rows")
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
    if memory.get("lessons_store", "files") != "files":
        errors.append("memory.lessons_store must be 'files'")
    if memory.get("location", "checked_in") not in {"checked_in", "local"}:
        errors.append("memory.location must be 'checked_in' or 'local'")
    budget = memory.get("recall_budget_chars", 1500)
    if isinstance(budget, bool) or not isinstance(budget, int) or budget <= 0:
        errors.append("memory.recall_budget_chars must be a positive integer")
    return errors


def cmd_status(args: Any) -> int:
    location = effective_location(args.location)
    mem_dir = resolve_memory_dir(location)
    lessons = load_lessons(mem_dir)
    global_dir = resolve_global_memory_dir()
    global_lessons = load_lessons(global_dir)
    status: dict[str, Any] = {
        "memory_dir": str(mem_dir),
        "exists": (mem_dir / "lessons.jsonl").is_file(),
        "location": location,
        "lesson_count": len(lessons),
        "kinds": count_kinds(lessons),
        "global_dir": str(global_dir),
        "global_lesson_count": len(global_lessons),
    }
    print(json.dumps(status, indent=2))
    return 0
