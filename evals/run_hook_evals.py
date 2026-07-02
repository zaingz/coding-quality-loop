#!/usr/bin/env python3
"""Offline fixture tests for host hook shims and installer wiring."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRE = ROOT / "hosts" / "claude-code" / "pretooluse_guard.py"
STOP = ROOT / "hosts" / "claude-code" / "stop_gate.py"
START = ROOT / "hosts" / "claude-code" / "sessionstart_context.py"
INSTALL = ROOT / "scripts" / "install.py"

PASS = "PASS"
FAIL = "FAIL"


def run_script(path: Path, payload: dict, cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(path)],
        input=json.dumps(payload),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd),
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_cli(*args: str, cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd),
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def make_repo(tmp: Path, with_scripts: bool = False) -> Path:
    repo = tmp / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "eval@example.com")
    git(repo, "config", "user.name", "eval")
    (repo / "README.md").write_text("# eval\n")
    if with_scripts:
        shutil.copytree(ROOT / "scripts", repo / "scripts")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "base")
    return repo


def deny_json(out: str) -> bool:
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return False
    hso = data.get("hookSpecificOutput") or {}
    return hso.get("permissionDecision") == "deny"


def done_record() -> dict:
    return {
        "task_id": "hook-eval",
        "goal": "Add rounding to the total calculation",
        "task_class": "medium",
        "risk_tier": "medium",
        "acceptance_criteria": ["round once"],
        "constraints": [],
        "non_goals": [],
        "assumptions": [],
        "verification_plan": ["unit"],
        "minimality_decision": {"rung": "reuse", "reason": "existing helper"},
        "plan": ["edit src/round.py"],
        "commands_run": [{"cmd": "pytest", "class": "unit", "result": "pass", "evidence": "1 passed"}],
        "open_risks": [],
        "review_findings": ["approved"],
        "repo_map": {"entry_points": ["src/round.py"], "likely_files": ["src/round.py"], "callers_checked": ["src/app.py"], "tests": ["tests/test_round.py"]},
        "implementer": "agent-a",
        "validation_contract": {"goal": "round", "acceptance_criteria": ["round once"], "evidence": ["pytest"]},
        "independent_review": {"reviewer": "agent-b", "verdict": "approve", "fresh_context": True, "patched": False, "diff_sha256": "0" * 64},
        "completion_record": {"goal": "round", "acceptance_criteria": ["round once"], "evidence": ["pytest"], "files_changed": ["src/round.py"]},
        "security_sensitive": False,
        "status": "done",
    }


def case_pretool_blocks_destructive(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    code, out, err = run_script(PRE, {"cwd": str(repo), "tool_name": "Bash", "tool_input": {"command": "rm -rf build"}}, repo)
    return code == 0 and deny_json(out), f"exit={code}; out={out.strip()!r}; err={err.strip()!r}"


def case_pretool_blocks_secret_write(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp, with_scripts=True)
    payload = {"cwd": str(repo), "tool_name": "Write", "tool_input": {"content": 'api_key = "ghp_' + "A" * 36 + '"'}}
    code, out, err = run_script(PRE, payload, repo)
    return code == 0 and deny_json(out), f"exit={code}; out={out.strip()!r}; err={err.strip()!r}"


def case_pretool_required_blocks_edit_before_plan(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp, with_scripts=True)
    (repo / ".quality-loop").mkdir()
    (repo / ".quality-loop" / "config.json").write_text(json.dumps({"enforcement": "required"}))
    record = done_record()
    record["status"] = "plan"
    record["minimality_decision"] = None
    (repo / "agent-record.json").write_text(json.dumps(record))
    code, out, err = run_script(PRE, {"cwd": str(repo), "tool_name": "Write", "tool_input": {"content": "safe text"}}, repo)
    return code == 0 and deny_json(out) and "PLAN" in out, f"exit={code}; out={out.strip()!r}; err={err.strip()!r}"


def case_pretool_allows_safe_write(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp, with_scripts=True)
    code, out, err = run_script(PRE, {"cwd": str(repo), "tool_name": "Write", "tool_input": {"content": "safe text"}}, repo)
    return code == 0 and out.strip() == "", f"exit={code}; out={out.strip()!r}; err={err.strip()!r}"


def case_stop_gate_blocks_phantom_done(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp, with_scripts=True)
    (repo / "agent-record.json").write_text(json.dumps(done_record()))
    code, out, err = run_script(STOP, {"cwd": str(repo), "hook_event_name": "Stop", "stop_hook_active": False}, repo)
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        data = {}
    return code == 0 and data.get("decision") == "block" and "phantom" in out.lower(), f"exit={code}; out={out.strip()[:220]!r}; err={err.strip()[:120]!r}"


def case_stop_gate_skips_active_loop(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp, with_scripts=True)
    (repo / "agent-record.json").write_text(json.dumps(done_record()))
    code, out, err = run_script(STOP, {"cwd": str(repo), "hook_event_name": "Stop", "stop_hook_active": True}, repo)
    return code == 0 and out.strip() == "", f"exit={code}; out={out.strip()!r}; err={err.strip()!r}"


def case_sessionstart_context(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    mem = repo / ".quality-loop" / "memory"
    mem.mkdir(parents=True)
    (mem / "MEMORY.md").write_text("# Project Memory\n- keep diffs small\n")
    (repo / "agent-record.json").write_text(json.dumps(done_record()))
    code, out, err = run_script(START, {"cwd": str(repo), "hook_event_name": "SessionStart", "source": "startup"}, repo)
    data = json.loads(out)
    ctx = data.get("hookSpecificOutput", {}).get("additionalContext", "")
    return code == 0 and "keep diffs small" in ctx and "status=done" in ctx, f"exit={code}; ctx={ctx[:120]!r}; err={err.strip()!r}"


def case_sessionstart_brief(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp, with_scripts=True)
    qdir = repo / ".quality-loop"
    qdir.mkdir(parents=True, exist_ok=True)
    (qdir / "agent-record.json").write_text(json.dumps(done_record()))
    (qdir / "progress.md").write_text("# Progress\n\n## Next step\nAdd more tests\n")
    code, out, err = run_script(START, {"cwd": str(repo), "hook_event_name": "SessionStart", "source": "startup"}, repo)
    data = json.loads(out)
    ctx = data.get("hookSpecificOutput", {}).get("additionalContext", "")
    return code == 0 and "briefing" in ctx and "Add more tests" in ctx, f"exit={code}; ctx={ctx[:200]!r}; err={err.strip()!r}"


def case_installer_idempotent_claude_codex(tmp: Path) -> tuple[bool, str]:
    target = tmp / "target"
    target.mkdir()
    code1, out1, err1 = run_cli(str(INSTALL), "--target", str(target), "--host", "claude-code", cwd=ROOT)
    code2, out2, err2 = run_cli(str(INSTALL), "--target", str(target), "--host", "claude-code", cwd=ROOT)
    code3, out3, err3 = run_cli(str(INSTALL), "--target", str(target), "--host", "codex", cwd=ROOT)
    ok = (
        code1 == code2 == code3 == 0
        and (target / ".claude" / "settings.json").is_file()
        and (target / ".claude" / "agents" / "quality-loop-reviewer.md").is_file()
        and (target / ".codex" / "hooks.json").is_file()
        and (target / "hosts" / "claude-code" / "pretooluse_guard.py").is_file()
        and (target / "hosts" / "claude-code" / "hooklib.py").is_file()
        and (target / "scripts" / "quality_loop.py").is_file()
    )
    return ok, f"codes={[code1, code2, code3]}; out={(out1 + out2 + out3).strip()[:220]!r}; err={(err1 + err2 + err3).strip()!r}"


CASES = [
    ("PreToolUse blocks destructive Bash", case_pretool_blocks_destructive),
    ("PreToolUse blocks secret Write content", case_pretool_blocks_secret_write),
    ("PreToolUse required mode blocks medium edit before plan", case_pretool_required_blocks_edit_before_plan),
    ("PreToolUse allows safe Write", case_pretool_allows_safe_write),
    ("Stop gate blocks phantom done", case_stop_gate_blocks_phantom_done),
    ("Stop gate skips active stop loop", case_stop_gate_skips_active_loop),
    ("SessionStart emits memory and record context", case_sessionstart_context),
    ("SessionStart includes brief output when scripts present", case_sessionstart_brief),
    ("installer is idempotent for Claude/Codex wiring", case_installer_idempotent_claude_codex),
]


def main() -> int:
    failures = 0
    for name, fn in CASES:
        with tempfile.TemporaryDirectory() as td:
            try:
                ok, detail = fn(Path(td))
            except Exception as exc:  # noqa: BLE001
                ok, detail = False, f"exception: {exc!r}"
        print(f"[{PASS if ok else FAIL}] {name}\n        {detail}")
        failures += 0 if ok else 1
    print(f"\n{len(CASES) - failures}/{len(CASES)} hook eval cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
