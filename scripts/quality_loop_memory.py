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


def normalize_lesson(raw: dict[str, Any], created: str) -> dict[str, Any]:
    text = str(raw.get("lesson", "")).strip()
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
    tmp = path.with_name("lessons.jsonl.tmp")
    tmp.write_text(
        "".join(json.dumps(l, sort_keys=True) + "\n" for l in lessons),
        encoding="utf-8",
    )
    os.replace(tmp, path)


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
    score += min(int(lesson.get("hits", 0)), 5) * 0.1
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
        key=lambda x: (int(x.get("hits", 0)), str(x.get("created", ""))),
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
            l["hits"] = int(l.get("hits", 0)) + 1
    save_lessons(mem_dir, lessons)
    write_index(mem_dir, lessons)


def _split_files(value: str | None) -> list[str]:
    return [f.strip() for f in (value or "").split(",") if f.strip()]


def cmd_recall(args: Any) -> int:
    mem_dir = resolve_memory_dir(args.location)
    lessons = load_lessons(mem_dir)
    selected = recall(lessons, args.goal or "", _split_files(args.files), args.risk, args.budget)
    if selected:
        bump_hits(mem_dir, [str(l.get("id", "")) for l in selected])
    if args.json:
        print(json.dumps(selected, indent=2))
    else:
        print(format_digest(selected, args.budget))
    return 0
