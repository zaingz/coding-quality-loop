#!/usr/bin/env python3
"""Offline fixture tests for host hook shims and installer wiring."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRE = ROOT / "hosts" / "claude-code" / "pretooluse_guard.py"
STOP = ROOT / "hosts" / "claude-code" / "stop_gate.py"
START = ROOT / "hosts" / "claude-code" / "sessionstart_context.py"
INSTALL = ROOT / "scripts" / "install.py"

from _harness import main_loop  # noqa: E402

# run_script / run_cli stay local: they invoke arbitrary host shims (not the
# quality_loop.py CLI) with a required cwd, so they do not share the harness's
# run_cli contract.


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


def _dirty_review_repo(tmp: Path, status: str, extra: dict | None = None) -> Path:
    """A scripts-bearing repo with a non-empty working tree (an unmapped new
    file) and a record at `status`. The unmapped file guarantees the diff-
    grounded gates fail at medium+ risk (scope integrity)."""
    repo = make_repo(tmp, with_scripts=True)
    (repo / "surprise.py").write_text("x = 1\n")  # unmapped -> scope-integrity finding
    record = done_record()
    record["status"] = status
    record.update(extra or {})
    (repo / "agent-record.json").write_text(json.dumps(record))
    return repo


def case_stop_gate_blocks_review_dirty_failing(tmp: Path) -> tuple[bool, str]:
    repo = _dirty_review_repo(tmp, "review")
    code, out, err = run_script(STOP, {"cwd": str(repo), "hook_event_name": "Stop", "stop_hook_active": False}, repo)
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        data = {}
    ok = code == 0 and data.get("decision") == "block" and "escalate" in out.lower()
    return ok, f"exit={code}; decision={data.get('decision')}; out={out.strip()[:220]!r}; err={err.strip()[:120]!r}"


def case_stop_gate_blocks_retrospect_dirty(tmp: Path) -> tuple[bool, str]:
    # 4.0.0 added the retrospect status AFTER package; without dirty-gating it
    # would be a post-completion parking spot where further changes stop
    # ungated locally (merge-seam finding, probe-proven).
    repo = _dirty_review_repo(tmp, "retrospect")
    code, out, err = run_script(STOP, {"cwd": str(repo), "hook_event_name": "Stop", "stop_hook_active": False}, repo)
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        data = {}
    ok = code == 0 and data.get("decision") == "block"
    return ok, f"exit={code}; decision={data.get('decision')}; out={out.strip()[:160]!r}"


def case_stop_gate_allows_escalate_dirty(tmp: Path) -> tuple[bool, str]:
    # The valve requires a non-empty escalation_reason: that is what makes the
    # pause auditable rather than a free status string.
    repo = _dirty_review_repo(tmp, "escalated", {"escalation_reason": "waiting on schema owner sign-off"})
    code, out, err = run_script(STOP, {"cwd": str(repo), "hook_event_name": "Stop", "stop_hook_active": False}, repo)
    return code == 0 and out.strip() == "", f"exit={code}; out={out.strip()!r}; err={err.strip()!r}"


def case_stop_gate_blocks_escalated_without_reason(tmp: Path) -> tuple[bool, str]:
    # escalated with NO recorded reason gets no free pass: with a dirty tree it
    # is gated like verify/review, so the reasonless valve cannot be an evasion.
    repo = _dirty_review_repo(tmp, "escalated")
    code, out, err = run_script(STOP, {"cwd": str(repo), "hook_event_name": "Stop", "stop_hook_active": False}, repo)
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        data = {}
    ok = code == 0 and data.get("decision") == "block"
    return ok, f"exit={code}; decision={data.get('decision')}; out={out.strip()[:160]!r}"


def case_stop_gate_blocks_unreadable_record(tmp: Path) -> tuple[bool, str]:
    # A present-but-corrupt record must fail CLOSED: a traceback would exit
    # non-2 and Claude Code would allow the stop, so one corrupted byte of the
    # agent's own record would otherwise reopen the silent-evasion vector.
    repo = make_repo(tmp, with_scripts=True)
    (repo / "agent-record.json").write_bytes(b'{"status": "done"\xff\xfe')
    code, out, err = run_script(STOP, {"cwd": str(repo), "hook_event_name": "Stop", "stop_hook_active": False}, repo)
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        data = {}
    ok = code == 0 and data.get("decision") == "block" and "unreadable" in out.lower()
    return ok, f"exit={code}; decision={data.get('decision')}; out={out.strip()[:160]!r}; err={err.strip()[:100]!r}"


def case_stop_gate_allows_implement_dirty(tmp: Path) -> tuple[bool, str]:
    repo = _dirty_review_repo(tmp, "implement")
    code, out, err = run_script(STOP, {"cwd": str(repo), "hook_event_name": "Stop", "stop_hook_active": False}, repo)
    return code == 0 and out.strip() == "", f"exit={code}; out={out.strip()!r}; err={err.strip()!r}"


def case_stop_gate_allows_active_loop_review(tmp: Path) -> tuple[bool, str]:
    repo = _dirty_review_repo(tmp, "review")
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
    ("Stop gate blocks review status with dirty tree and failing gates", case_stop_gate_blocks_review_dirty_failing),
    ("Stop gate blocks retrospect status with dirty tree", case_stop_gate_blocks_retrospect_dirty),
    ("Stop gate allows escalated status with a recorded reason", case_stop_gate_allows_escalate_dirty),
    ("Stop gate blocks reasonless escalated status with dirty tree", case_stop_gate_blocks_escalated_without_reason),
    ("Stop gate blocks (not crashes) on an unreadable record", case_stop_gate_blocks_unreadable_record),
    ("Stop gate allows implement status with dirty tree", case_stop_gate_allows_implement_dirty),
    ("Stop gate allows active stop loop even at review with failing gates", case_stop_gate_allows_active_loop_review),
    ("SessionStart emits memory and record context", case_sessionstart_context),
    ("SessionStart includes brief output when scripts present", case_sessionstart_brief),
    ("installer is idempotent for Claude/Codex wiring", case_installer_idempotent_claude_codex),
]


if __name__ == "__main__":
    raise SystemExit(main_loop(CASES, "hook eval cases passed"))
