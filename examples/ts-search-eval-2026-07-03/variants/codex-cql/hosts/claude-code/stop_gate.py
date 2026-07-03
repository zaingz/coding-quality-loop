#!/usr/bin/env python3
"""Stop hook: block premature completion when package/done gates fail."""

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


def _record_path(root: Path) -> Path | None:
    env = os.environ.get("QUALITY_LOOP_RECORD")
    candidates = [Path(env)] if env else []
    candidates += [root / ".quality-loop" / "agent-record.json", root / "agent-record.json"]
    return next((p for p in candidates if p and p.is_file()), None)


def _status(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""
    return str(data.get("status", "")) if isinstance(data, dict) else ""


def _block(reason: str) -> int:
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


def main() -> int:
    data = _input()
    if data.get("stop_hook_active"):
        return 0
    root = _root(data)
    record = _record_path(root)
    if record is None or _status(record) not in {"package", "done"}:
        return 0
    proc = subprocess.run(
        ["python3", str(root / "scripts" / "quality_loop.py"), "verify-gates", str(record), "--against-diff", "--base", os.environ.get("QUALITY_LOOP_BASE", "HEAD")],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(root),
        check=False,
    )
    if proc.returncode == 0:
        return 0
    detail = (proc.stdout + proc.stderr).strip()[:4000]
    return _block("Quality Loop stop gate failed; fix or record an explicit waiver before stopping.\n" + detail)


if __name__ == "__main__":
    raise SystemExit(main())
