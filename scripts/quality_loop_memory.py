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


def _tokens(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(text or "") if len(w) > 2}


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
