#!/usr/bin/env python3
"""SessionStart/SessionEnd hook: feed the control plane and autostart its server.

Observability shim, not a gate: it records the session event via
``control-ingest`` and, on SessionStart, starts the local dashboard server when
``control_plane.enabled`` (and ``autostart``) are set in the repo config.

Contract: this hook NEVER blocks or breaks a session. Every failure path exits
0 silently — a broken observability plane must degrade to "no data", never to
a session that cannot start. The Quality Loop gates live in stop_gate.py and
stay loud; this file is deliberately quiet.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _root(data: dict) -> Path:
    cwd = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd())
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return cwd
    return Path(proc.stdout.strip()) if proc.returncode == 0 and proc.stdout.strip() else cwd


def _server_running(root: Path) -> bool:
    """True only if a server behind the recorded port answers /healthz for
    THIS root. A live-looking pid is not proof (pids get recycled, and probing
    a pid with os.kill(pid, 0) would terminate it on Windows); a dead or
    foreign server must not suppress autostart. If two SessionStarts race past
    this check, the port bind inside control-serve settles it."""
    state_path = root / ".quality-loop" / "control" / "server.json"
    if not state_path.is_file():
        return False
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        port = int(state.get("port") or -1)
    except (ValueError, OSError):
        return False
    if port <= 0:
        return False
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=2) as res:
            health = json.loads(res.read().decode("utf-8"))
        # Resolve both sides: the server may hold a symlinked spelling of the
        # same directory (macOS /var vs /private/var).
        return (isinstance(health, dict) and isinstance(health.get("root"), str)
                and Path(health["root"]).resolve() == root.resolve())
    except (OSError, ValueError):
        return False


def main() -> int:
    event = sys.argv[1] if len(sys.argv) > 1 else "SessionStart"
    host = sys.argv[2] if len(sys.argv) > 2 else "claude-code"
    try:
        raw = sys.stdin.read() or "{}"
    except (OSError, ValueError):  # ValueError covers undecodable stdin bytes
        raw = "{}"
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            data = {}
    except ValueError:
        data = {}
    try:
        root = _root(data)
        script = root / "scripts" / "quality_loop.py"
        if not script.is_file():
            return 0
        try:
            cfg = json.loads((root / "quality-loop.config.json").read_text(encoding="utf-8"))
        except (ValueError, OSError):
            cfg = {}
        block = cfg.get("control_plane") if isinstance(cfg, dict) else None
        block = block if isinstance(block, dict) else {}
        if block.get("enabled") is not True:
            return 0
        subprocess.run(
            [sys.executable, str(script), "control-ingest", "--event", event,
             "--host", host, "--cwd", str(root)],
            input=raw,
            text=True,
            timeout=6,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if event == "SessionStart" and block.get("autostart", True) is True and not _server_running(root):
            control = root / ".quality-loop" / "control"
            control.mkdir(parents=True, exist_ok=True)
            # Self-gitignore BEFORE the first file lands: if the ingest
            # subprocess above died early, server.log must not be the one
            # window where control data is visible to `git add -A`.
            gitignore = control / ".gitignore"
            if not gitignore.is_file():
                gitignore.write_text("*\n", encoding="utf-8")
            detach: dict = (
                {"start_new_session": True} if os.name != "nt"
                # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP: start_new_session
                # is silently ignored on Windows, which would tie the server to
                # the hook's console lifetime.
                else {"creationflags": 0x00000008 | 0x00000200}
            )
            with (control / "server.log").open("ab") as log:
                subprocess.Popen(  # noqa: S603 - detached local server, our own script
                    [sys.executable, str(script), "control-serve", "--cwd", str(root)],
                    stdout=log,
                    stderr=log,
                    stdin=subprocess.DEVNULL,
                    **detach,
                )
    except Exception:  # noqa: BLE001 - see module docstring: never break a session
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
