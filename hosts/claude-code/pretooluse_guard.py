#!/usr/bin/env python3
"""Claude Code/Codex PreToolUse guard for dangerous commands, harness tampering, and secret writes."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from hooklib import deny_pretool, json_input, load_json, project_root

# Every pattern is anchored to a command position (start of string/line or right
# after ; & | $( or a backtick) so quoted or read-only mentions — e.g.
# grep -rn "git reset --hard" docs/ or echo "never rm -rf" — do not match.
_CMD = r"(?:^|[;&|\n]|\$\(|`)\s*(?:sudo\s+)?"
# Rest of the same command segment: never crosses into the next command.
_SEG = r"[^;&|\n]*"
# Flag tokens (short flags combined or separate, plus long forms), matched
# order-insensitively via segment-scoped lookaheads. Long options are excluded
# from the short-flag branch because their second dash is not a letter.
_RECURSIVE_FLAG = r"[ \t]-(?:[a-zA-Z]*r|-recursive\b)"
_FORCE_FLAG = r"[ \t]-(?:[a-zA-Z]*f|-force\b)"

DESTRUCTIVE = [
    # rm with BOTH a recursive and a force flag, in any order (-rf, -fr, -r -f,
    # --recursive --force, ...). `rm -r build && cp -f a b` must NOT match: the
    # force flag belongs to a different command segment.
    re.compile(_CMD + rf"rm(?={_SEG}{_RECURSIVE_FLAG})(?={_SEG}{_FORCE_FLAG})"),
    re.compile(_CMD + rf"git\s+reset(?={_SEG}[ \t]--hard\b)"),
    re.compile(_CMD + rf"git\s+clean(?={_SEG}{_FORCE_FLAG})"),
    # `git checkout -- <path>` discards working-tree changes (bare -- token).
    re.compile(_CMD + rf"git\s+checkout(?={_SEG}[ \t]--(?:[ \t]|$))"),
    re.compile(_CMD + rf"git\s+push(?={_SEG}{_FORCE_FLAG})"),
    re.compile(_CMD + r"drop\s+database\b", re.I),
    re.compile(_CMD + r"truncate\s+table\b", re.I),
]
# Deletion of the active record / loop state (protect_harness-gated below).
RECORD_DESTRUCTIVE = [
    re.compile(_CMD + rf"rm(?={_SEG}(?:agent-record\.json|\.quality-loop\b|quality-loop\.config\.json))"),
]
EDIT_TOOLS = {"Write", "Edit", "apply_patch"}

# Repo-relative paths whose edit is denied while protect_harness is on.
HARNESS_RECORD_FILES = {
    ".quality-loop/agent-record.json",
    "agent-record.json",
    "quality-loop.config.json",
    ".quality-loop/config.json",
}


def _config(root: Path) -> dict:
    """Load the loop config: root quality-loop.config.json is canonical; the old
    .quality-loop/config.json is read as a one-release fallback with a warning."""
    canonical = root / "quality-loop.config.json"
    if canonical.is_file():
        return load_json(canonical)
    legacy = root / ".quality-loop" / "config.json"
    if legacy.is_file():
        print(
            "quality-loop: .quality-loop/config.json is deprecated — move it to quality-loop.config.json at the repo root",
            file=sys.stderr,
        )
        return load_json(legacy)
    return {}


def _protected_target(root: Path, tool_input: dict) -> str | None:
    """Repo-relative path of an edit target that is harness or record, else None."""
    raw = str(tool_input.get("file_path") or tool_input.get("path") or "")
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    try:
        rel = path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    rel_posix = rel.as_posix()
    if rel_posix in HARNESS_RECORD_FILES:
        return rel_posix
    if rel.parts[:1] == ("scripts",) and rel.name.startswith("quality_loop") and rel.name.endswith(".py"):
        return rel_posix
    if rel.parts[:2] == ("hosts", "claude-code") and rel.name.endswith(".py"):
        return rel_posix
    return None


def _scan_text(root: Path, tool_input: dict) -> str | None:
    """Deny reason when scan-text found secret-like content; None otherwise.

    Only a real findings exit (1) denies. A missing or broken runtime allows
    with a stderr warning naming the actual problem — never a fabricated block.
    """
    text = "\n".join(str(tool_input.get(k, "")) for k in ("content", "new_string", "command"))
    if not text:
        return None
    script = root / "scripts" / "quality_loop.py"
    if not script.is_file():
        print(
            "quality-loop: CQL runtime missing at scripts/quality_loop.py — secret scan skipped; "
            "run cql init or python3 scripts/install.py",
            file=sys.stderr,
        )
        return None
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "scan-text", "--stdin"],
            input=text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(root),
            check=False,
        )
    except OSError as exc:
        print(f"quality-loop: secret scan skipped — could not run {script}: {exc}", file=sys.stderr)
        return None
    if proc.returncode == 0:
        return None
    if proc.returncode == 1:
        detail = (proc.stdout + proc.stderr).strip()[:1500]
        return (
            "secret-like text blocked by Quality Loop scan-text; remove the secret "
            "(load it from an env var or secrets manager) and retry.\n" + detail
        )
    print(
        f"quality-loop: secret scan skipped — scan-text failed (exit {proc.returncode}): "
        f"{(proc.stderr or proc.stdout).strip()[:300]}",
        file=sys.stderr,
    )
    return None


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
    return (
        "edit blocked: required Quality Loop config needs medium/high work to pass PLAN + "
        "MINIMALITY_GATE first. Record a plan and a minimality_decision in the agent record "
        "and advance status to implement, then retry."
    )


def main() -> int:
    data = json_input()
    root = project_root(data)
    tool = str(data.get("tool_name", ""))
    tool_input = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    cfg = _config(root)
    protect = cfg.get("protect_harness") is not False  # default ON
    if tool == "Bash":
        command = str(tool_input.get("command", ""))
        if any(p.search(command) for p in DESTRUCTIVE):
            return deny_pretool("destructive Bash command blocked by Quality Loop pretooluse_guard")
        if protect and any(p.search(command) for p in RECORD_DESTRUCTIVE):
            return deny_pretool(
                "destructive Bash command blocked: it would delete the Quality Loop record or "
                ".quality-loop state, erasing the loop's tamper-evident audit trail. If the loop "
                "should leave this repo, ask the user to remove it deliberately."
            )
    if tool in EDIT_TOOLS:
        if protect and (target := _protected_target(root, tool_input)):
            return deny_pretool(
                f"edit blocked: {target} is Quality Loop harness/record — tamper-evidence depends "
                "on the agent under review not modifying its own gates, record, or config. If this "
                "file genuinely needs to change, ask the user to make or approve the change."
            )
        if finding := _scan_text(root, tool_input):
            return deny_pretool(finding)
        if cfg.get("enforcement") == "required" and (finding := _edit_before_plan_block(root)):
            return deny_pretool(finding)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
