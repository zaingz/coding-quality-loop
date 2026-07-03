#!/usr/bin/env python3
"""Claude Code/Codex PreToolUse guard for dangerous commands and secret writes."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from hooklib import deny_pretool, json_input, load_json, project_root

DESTRUCTIVE = [
    re.compile(r"\brm\s+-[^;\n]*r[^;\n]*f\b"),
    re.compile(r"\bgit\s+reset\s+--hard\b"),
    re.compile(r"\bgit\s+clean\s+-[^;\n]*f"),
    re.compile(r"\bdrop\s+database\b", re.I),
    re.compile(r"\btruncate\s+table\b", re.I),
]
EDIT_TOOLS = {"Write", "Edit", "apply_patch"}


def _scan_text(root: Path, tool_input: dict) -> str | None:
    text = "\n".join(str(tool_input.get(k, "")) for k in ("content", "new_string", "command"))
    if not text:
        return None
    proc = subprocess.run(
        ["python3", str(root / "scripts" / "quality_loop.py"), "scan-text", "--stdin"],
        input=text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(root),
        check=False,
    )
    return "secret-like text blocked by Quality Loop scan-text" if proc.returncode else None


def _record(root: Path) -> dict:
    for path in (root / ".quality-loop" / "agent-record.json", root / "agent-record.json"):
        if data := load_json(path):
            return data
    return {}


def _edit_before_plan_block(root: Path) -> str | None:
    rec = _record(root)
    if rec.get("risk_tier") not in {"medium", "high"}:
        return None
    ok_status = rec.get("status") in {"implement", "verify", "review", "package", "done", "iterating"}
    if ok_status and rec.get("minimality_decision"):
        return None
    return "edit blocked: required Quality Loop config needs medium/high work to pass PLAN + MINIMALITY_GATE first. Override: change .quality-loop/config.json enforcement to advisory."


def main() -> int:
    data = json_input()
    root = project_root(data)
    tool = str(data.get("tool_name", ""))
    tool_input = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    if tool == "Bash" and any(p.search(str(tool_input.get("command", ""))) for p in DESTRUCTIVE):
        return deny_pretool("destructive Bash command blocked by Quality Loop pretooluse_guard")
    if tool in EDIT_TOOLS and (finding := _scan_text(root, tool_input)):
        return deny_pretool(finding)
    required = load_json(root / ".quality-loop" / "config.json").get("enforcement") == "required"
    if tool in EDIT_TOOLS and required and (finding := _edit_before_plan_block(root)):
        return deny_pretool(finding)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
