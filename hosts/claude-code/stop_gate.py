#!/usr/bin/env python3
"""Stop hook: block premature completion when outcome gates fail.

Closes the silent-evasion vector (GV1): the gate used to fire only at the
self-reported statuses ``package``/``done``, so an agent that finished real work
but never advanced its status could stop entirely ungated.

Decision table (evaluated top to bottom):
  - no record                                  -> allow (repo may not use the loop)
  - stop_hook_active                            -> allow (never re-block our own stop)
  - record unreadable                           -> BLOCK (corruption must not lift the gate)
  - escalated + non-empty escalation_reason     -> allow (explicit, auditable pause)
  - status in {package, done}                   -> run gates; block on failure
  - {verify, review, reasonless escalated}
      + dirty tree                              -> run gates; block on failure
  - intake/explore/plan/implement/iterating     -> allow (mid-work stop)

Rationale for allowing the earlier statuses: a mid-work turn must be able to
stop to ask the user a question. The merge boundary is anchored separately by
CI (`verify --require-terminal`), so the only residual local evasion — parking
at `implement` with a dirty tree — stays visible in the record and is caught on
the PR. It is never silently ungated end-to-end.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# Statuses whose stop is gated whenever the working tree carries real changes.
# "escalated" appears here so that escalation WITHOUT a recorded reason gets no
# free pass — the reasoned valve is handled before this set is consulted.
DIRTY_GATED_STATUSES = {"verify", "review", "escalated"}
# Statuses that are always gated (the self-reported completion boundary).
TERMINAL_GATED_STATUSES = {"package", "done"}


def _input() -> dict[str, Any]:
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _root(data: dict[str, Any]) -> Path:
    cwd = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd())
    # A session hook must never crash: if git itself is unavailable, fall back
    # to cwd (the record lookup and dirty check then fail open by design).
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return cwd
    return Path(proc.stdout.strip()) if proc.returncode == 0 and proc.stdout.strip() else cwd


def _record_path(root: Path) -> Path | None:
    env = os.environ.get("QUALITY_LOOP_RECORD")
    candidates = [Path(env)] if env else []
    candidates += [root / ".quality-loop" / "agent-record.json", root / "agent-record.json"]
    return next((p for p in candidates if p and p.is_file()), None)


def _record(path: Path) -> dict[str, Any] | None:
    """Parse the record; None means present-but-unreadable, which fails CLOSED.

    A corrupt/undecodable record must block, not traceback: an uncaught
    exception exits non-2 and Claude Code treats that as allow, so one
    corrupted byte would otherwise reopen the silent-evasion vector.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _tree_is_dirty(root: Path) -> bool:
    """Cheap working-tree diff check: any tracked change or untracked (non-ignored)
    file. Mirrors the change set `verify-gates --against-diff` reasons over.

    Fails OPEN (not dirty) when git is broken or absent: a session hook must not
    lock an agent out of stopping because the environment lost git. The merge
    boundary stays anchored by CI, which runs the gates from a pinned copy."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return False
    return proc.returncode == 0 and bool(proc.stdout.strip())


def _run_gates(root: Path, record: Path) -> tuple[int, str]:
    """Run the diff-grounded gates exactly as the package/done path always has."""
    proc = subprocess.run(
        ["python3", str(root / "scripts" / "quality_loop.py"), "verify-gates", str(record), "--against-diff", "--base", os.environ.get("QUALITY_LOOP_BASE", "HEAD")],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(root),
        check=False,
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()[:4000]


def _block(reason: str) -> int:
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


def main() -> int:
    data = _input()
    if data.get("stop_hook_active"):
        return 0
    root = _root(data)
    record = _record_path(root)
    if record is None:
        return 0
    parsed = _record(record)
    if parsed is None:
        return _block(
            "Quality Loop record exists but is unreadable (invalid JSON/encoding or not an object). "
            "Repair .quality-loop/agent-record.json before stopping — an unreadable record does not lift the gate."
        )
    status = str(parsed.get("status", ""))
    if status == "escalated":
        reason = parsed.get("escalation_reason")
        if isinstance(reason, str) and reason.strip():
            return 0
        # No recorded reason: the pause is not auditable, so treat it like any
        # other non-terminal status — gated below when the tree is dirty.

    if status in TERMINAL_GATED_STATUSES:
        rc, detail = _run_gates(root, record)
        if rc == 0:
            return 0
        return _block(
            "Quality Loop stop gate failed; fix or record an explicit waiver before stopping.\n" + detail
        )

    if status in DIRTY_GATED_STATUSES and _tree_is_dirty(root):
        rc, detail = _run_gates(root, record)
        if rc == 0:
            return 0
        return _block(
            f"Quality Loop stop gate failed at status '{status}' with a dirty working tree. "
            "Three legitimate ways forward:\n"
            "  1. Keep working — resolve the findings below.\n"
            "  2. Advance to package/done and pass the gates.\n"
            "  3. Set status \"escalated\" with a non-empty escalation_reason for an auditable pause.\n"
            + detail
        )

    # intake/explore/plan/implement/iterating (or verify/review with a clean tree):
    # allow the stop so the agent can pause mid-work to consult the user.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
