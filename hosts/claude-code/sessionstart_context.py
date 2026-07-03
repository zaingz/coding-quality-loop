#!/usr/bin/env python3
"""SessionStart hook: inject compact Quality Loop memory and record status."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def _input() -> dict[str, Any]:
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _root(data: dict[str, Any]) -> Path:
    cwd = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd())
    proc = subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return Path(proc.stdout.strip()) if proc.returncode == 0 and proc.stdout.strip() else cwd


def _record_status(root: Path) -> str:
    for path in (root / ".quality-loop" / "agent-record.json", root / "agent-record.json"):
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return f"Quality Loop record is invalid JSON: {path}"
            if isinstance(data, dict):
                return "Quality Loop record: task_id=%s status=%s risk=%s" % (
                    data.get("task_id", "?"), data.get("status", "?"), data.get("risk_tier", "?")
                )
    return "Quality Loop record: none found"


def _brief_output(root: Path) -> str:
    proc = subprocess.run(
        [sys.executable, str(root / "scripts" / "quality_loop.py"), "brief", "--cwd", str(root)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        cwd=str(root),
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 and proc.stdout.strip() else ""


def main() -> int:
    root = _root(_input())
    brief = _brief_output(root)
    parts: list[str] = []
    if brief:
        parts.append("Quality Loop briefing:\n" + brief[:6000])
    else:
        parts.append(_record_status(root))
    memory = root / ".quality-loop" / "memory" / "MEMORY.md"
    if memory.is_file():
        parts.append("Project memory index:\n" + memory.read_text(encoding="utf-8")[:4000])
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n\n".join(parts),
        }
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
