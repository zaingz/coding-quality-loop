#!/usr/bin/env python3
"""Claude Code/Codex PreToolUse guard for dangerous commands, harness tampering, and secret writes."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from hooklib import deny_pretool, json_input, load_json, project_root

# Every pattern is anchored to a command position (start of string/line or right
# after ; & | $( or a backtick) so quoted or read-only mentions — e.g.
# grep -rn "git reset --hard" docs/ or echo "never rm -rf" — do not match.
# Wrapper tokens are transparent: the destructive command still runs, so
# `env rm -rf`, `xargs rm -rf`, `command rm -rf`, `nice rm -rf`, VAR=1
# prefixes, and a path/backslash prefix on the binary (`/bin/rm`, `\rm`) all
# stay anchored to the command position.
# A wrapper keyword may carry its own option/value tokens before the real
# command: `sudo -n rm`, `env -i rm`, `xargs -0 rm`, `nice -n 5 rm`, `command
# -- rm`. Consume leading `-flag` and bare-number tokens after each keyword so
# an option-bearing wrapper cannot slip a destructive command past the guard.
_WRAPPER = (
    r"(?:(?:\S*/)?(?:sudo|env|command|nice|nohup|time|xargs)\s+(?:-\S+\s+|\d+\s+)*"
    r"|[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
)
_CMD = r"(?:^|[;&|\n]|\$\(|`)\s*" + _WRAPPER + r"(?:\\|\S*/)?"
# Rest of the same command segment: never crosses into the next command.
_SEG = r"[^;&|\n]*"
# Flag tokens (short flags combined or separate, plus long forms), matched
# order-insensitively via segment-scoped lookaheads. Long options are excluded
# from the short-flag branch because their second dash is not a letter.
# --force must not match the SAFE --force-with-lease prefix, hence (?!-).
_RECURSIVE_FLAG = r"[ \t]-(?:[a-zA-Z]*r|-recursive\b)"
_FORCE_FLAG = r"[ \t]-(?:[a-zA-Z]*f|-force\b(?!-))"
# `sh -c "..."` / `bash -lc '...'` payloads run as commands: the quoted body is
# scanned too, so a shell wrapper string cannot smuggle a destructive command.
_SHELL_C = re.compile(r"\b(?:ba|da|z)?sh\s+(?:-\S+\s+)*-\w*c\s+(?:\"([^\"]*)\"|'([^']*)')")

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
# The agent record is deliberately NOT here: the lifecycle requires continuous
# record mutation and no CLI subcommand writes it, so denying record edits only
# funnels honest agents into Bash heredocs. Record integrity comes from the
# layer that actually holds it — the freshness hash, verify's re-execution, and
# the CI anchor — not from a PreToolUse path deny. What stays denied is the set
# an agent never legitimately edits: config, hook wiring, and the install
# inventory (unwiring the hooks or rewriting the uninstall manifest defeats the
# gates without touching the scripts).
HARNESS_RECORD_FILES = {
    "quality-loop.config.json",
    ".quality-loop/config.json",
    ".claude/settings.json",
    ".codex/hooks.json",
    ".quality-loop/install-manifest.json",
}


def _command_texts(command: str) -> list[str]:
    """The command plus the payload of any sh|bash -c quoted string, so a
    wrapper cannot smuggle a destructive command inside a -c argument."""
    texts = [command]
    for m in _SHELL_C.finditer(command):
        texts.append(m.group(1) or m.group(2) or "")
    return texts


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


def _patch_protected_target(tool_input: dict) -> str | None:
    """Best-effort apply_patch coverage: raw patch bodies carry their file
    targets in the patch text (e.g. `*** Update File: <path>`), not in a single
    path key, so a protected path referenced anywhere in the body is denied."""
    text = "\n".join(v for v in tool_input.values() if isinstance(v, str))
    if not text:
        return None
    for name in sorted(HARNESS_RECORD_FILES):
        if name in text:
            return name
    match = re.search(r"\b(?:scripts/quality_loop[\w.-]*\.py|hosts/claude-code/[\w.-]+\.py)", text)
    return match.group(0) if match else None


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
        # Exit 1 alone is not proof of findings: a crashed runtime (e.g. a
        # syntax error in quality_loop.py) also exits 1. Deny only when the
        # structured scan-text result on stdout carries non-empty findings;
        # a crash without that marker allows with a truthful warning.
        try:
            result = json.loads(proc.stdout or "")
        except json.JSONDecodeError:
            result = None
        findings = result.get("findings") if isinstance(result, dict) else None
        if not (isinstance(findings, list) and findings):
            print(
                "quality-loop: secret scan skipped — scan-text exited 1 without a structured "
                f"findings result (broken runtime?): {(proc.stderr or proc.stdout).strip()[:300]}",
                file=sys.stderr,
            )
            return None
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
        texts = _command_texts(str(tool_input.get("command", "")))
        if any(p.search(t) for p in DESTRUCTIVE for t in texts):
            return deny_pretool("destructive Bash command blocked by Quality Loop pretooluse_guard")
        if protect and any(p.search(t) for p in RECORD_DESTRUCTIVE for t in texts):
            return deny_pretool(
                "destructive Bash command blocked: it would delete the Quality Loop record or "
                ".quality-loop state, erasing the loop's tamper-evident audit trail. If the loop "
                "should leave this repo, ask the user to remove it deliberately."
            )
    if tool in EDIT_TOOLS:
        target = _protected_target(root, tool_input) if protect else None
        if protect and target is None and tool == "apply_patch":
            target = _patch_protected_target(tool_input)
        if target:
            return deny_pretool(
                f"edit blocked: {target} is Quality Loop harness — tamper-evidence depends on the "
                "agent under review not rewriting its own gate scripts, hook wiring, config, or "
                "install manifest. (The agent record is deliberately NOT protected here: its "
                "integrity comes from the freshness hash, verify's re-execution, and the CI anchor "
                "— edit it directly with Write/Edit as the lifecycle requires.) If this harness "
                "file genuinely needs to change, ask the user to make or approve the change."
            )
        if finding := _scan_text(root, tool_input):
            return deny_pretool(finding)
        if cfg.get("enforcement") == "required" and (finding := _edit_before_plan_block(root)):
            return deny_pretool(finding)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
