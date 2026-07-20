#!/usr/bin/env python3
"""Offline fixture tests for host hook shims and installer wiring."""

from __future__ import annotations

import json
import os
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


def run_script(path: Path, payload: dict, cwd: Path, env: dict | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(path)],
        input=json.dumps(payload),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd),
        env=env,
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


def _bash(repo: Path, command: str, env: dict | None = None) -> tuple[int, str, str]:
    return run_script(PRE, {"cwd": str(repo), "tool_name": "Bash", "tool_input": {"command": command}}, repo, env=env)


def case_pretool_blocks_flag_order_variants(tmp: Path) -> tuple[bool, str]:
    # rm matching must be order-insensitive: combined, reversed, and long-form
    # flags all count as recursive+force.
    repo = make_repo(tmp)
    details = []
    ok = True
    for cmd in ("rm -fr /x", "rm --recursive --force x"):
        code, out, _ = _bash(repo, cmd)
        good = code == 0 and deny_json(out)
        ok = ok and good
        details.append(f"{cmd!r}: exit={code} denied={deny_json(out)}")
    return ok, "; ".join(details)


def case_pretool_allows_quoted_or_other_command(tmp: Path) -> tuple[bool, str]:
    # Anchoring to a command position: quoted/read-only mentions must not match,
    # and a force flag on a DIFFERENT command (cp -f) must not complete rm -r.
    repo = make_repo(tmp)
    details = []
    ok = True
    for cmd in ('grep -rn "git reset --hard" docs/', 'echo "never rm -rf"', "rm -r build && cp -f a b"):
        code, out, err = _bash(repo, cmd)
        good = code == 0 and out.strip() == ""
        ok = ok and good
        details.append(f"{cmd!r}: exit={code} out={out.strip()!r}")
    return ok, "; ".join(details)


def case_pretool_blocks_wrapper_forms(tmp: Path) -> tuple[bool, str]:
    # Wrapper tokens must not launder a destructive command: shells (-c bodies),
    # path/backslash prefixes, and env/command/nice/xargs pass-throughs are all
    # still the same rm/git running — while quoted read-only mentions stay allowed.
    repo = make_repo(tmp)
    details = []
    ok = True
    denied_cmds = [
        'bash -c "rm -rf /x"',
        "sh -c 'rm -rf x'",
        "/bin/rm -fr x",
        "env rm -rf x",
        "\\rm -rf x",
        "find . -name '*.pyc' | xargs rm -rf",
        "command rm -rf x",
        "nice rm -rf x",
    ]
    for cmd in denied_cmds:
        code, out, _ = _bash(repo, cmd)
        good = code == 0 and deny_json(out)
        ok = ok and good
        details.append(f"{cmd!r}: denied={deny_json(out)}")
    for cmd in ('grep -rn "git reset --hard" docs/', 'echo "never rm -rf"'):
        code, out, _ = _bash(repo, cmd)
        good = code == 0 and out.strip() == ""
        ok = ok and good
        details.append(f"{cmd!r}: allowed={out.strip() == ''}")
    return ok, "; ".join(details)


def case_pretool_allows_force_with_lease(tmp: Path) -> tuple[bool, str]:
    # --force-with-lease is the SAFE force form and must not be denied by the
    # --force pattern; plain --force and -f stay denied.
    repo = make_repo(tmp)
    details = []
    code_a, out_a, _ = _bash(repo, "git push --force-with-lease origin main")
    allowed = code_a == 0 and out_a.strip() == ""
    details.append(f"--force-with-lease allowed={allowed}")
    ok = allowed
    for cmd in ("git push --force origin main", "git push -f origin main"):
        code, out, _ = _bash(repo, cmd)
        good = code == 0 and deny_json(out)
        ok = ok and good
        details.append(f"{cmd!r}: denied={deny_json(out)}")
    return ok, "; ".join(details)


def case_pretool_scan_crash_allows_with_warning(tmp: Path) -> tuple[bool, str]:
    # A crashed scanner (e.g. a syntax error in quality_loop.py) exits 1 just
    # like a real findings run. Without the structured findings JSON on stdout
    # the guard must allow with a truthful warning, never fabricate a secret block.
    repo = make_repo(tmp, with_scripts=True)
    (repo / "scripts" / "quality_loop.py").write_text("def broken(:\n    pass\n")
    payload = {"cwd": str(repo), "tool_name": "Write", "tool_input": {"content": 'api_key = "ghp_' + "A" * 36 + '"'}}
    code, out, err = run_script(PRE, payload, repo)
    ok = code == 0 and out.strip() == "" and "without a structured" in err
    return ok, f"exit={code}; out={out.strip()!r}; err={err.strip()[:200]!r}"


def case_pretool_protects_hook_wiring_and_manifest(tmp: Path) -> tuple[bool, str]:
    # Hook wiring files and the install manifest are the same protection class
    # as the gate scripts: unwiring hooks or rewriting the uninstall inventory
    # defeats the gates without touching them.
    repo = make_repo(tmp)
    details = []
    ok = True
    for target in (".claude/settings.json", ".codex/hooks.json", ".quality-loop/install-manifest.json"):
        code, out, _ = run_script(PRE, {"cwd": str(repo), "tool_name": "Edit", "tool_input": {"file_path": target, "new_string": "{}"}}, repo)
        good = code == 0 and deny_json(out) and "tamper-evidence" in out
        ok = ok and good
        details.append(f"{target}: denied={deny_json(out)}")
    return ok, "; ".join(details)


def case_pretool_apply_patch_body_targets_protected(tmp: Path) -> tuple[bool, str]:
    # apply_patch payloads carry targets in the patch text, not a single path
    # key: a protected path in the body is denied; a normal target is allowed.
    repo = make_repo(tmp)
    bad = "*** Begin Patch\n*** Update File: hosts/claude-code/stop_gate.py\n+x = 1\n*** End Patch\n"
    code_b, out_b, _ = run_script(PRE, {"cwd": str(repo), "tool_name": "apply_patch", "tool_input": {"input": bad}}, repo)
    denied = code_b == 0 and deny_json(out_b)
    good = "*** Begin Patch\n*** Update File: src/app.py\n+x = 1\n*** End Patch\n"
    code_g, out_g, _ = run_script(PRE, {"cwd": str(repo), "tool_name": "apply_patch", "tool_input": {"input": good}}, repo)
    allowed = code_g == 0 and out_g.strip() == ""
    return denied and allowed, f"protected_denied={denied}; normal_allowed={allowed}"


def case_pretool_blocks_record_deletion(tmp: Path) -> tuple[bool, str]:
    # protect_harness (default ON): deleting the record or .quality-loop erases
    # the audit trail, so rm against either is denied even without -rf.
    repo = make_repo(tmp)
    details = []
    ok = True
    for cmd in ("rm agent-record.json", "rm -r .quality-loop"):
        code, out, _ = _bash(repo, cmd)
        good = code == 0 and deny_json(out) and "audit trail" in out
        ok = ok and good
        details.append(f"{cmd!r}: exit={code} denied={deny_json(out)}")
    return ok, "; ".join(details)


def case_pretool_protect_harness_blocks_gate_edit(tmp: Path) -> tuple[bool, str]:
    # Default-on tamper-evidence: editing the gate scripts, hook shims, or the
    # active record is denied without any config present.
    repo = make_repo(tmp)
    details = []
    ok = True
    for target in ("scripts/quality_loop.py", "hosts/claude-code/stop_gate.py", "agent-record.json"):
        code, out, _ = run_script(PRE, {"cwd": str(repo), "tool_name": "Edit", "tool_input": {"file_path": target, "new_string": "x = 1"}}, repo)
        good = code == 0 and deny_json(out) and "tamper-evidence" in out
        ok = ok and good
        details.append(f"{target}: exit={code} denied={deny_json(out)}")
    return ok, "; ".join(details)


def case_pretool_protect_harness_off_allows_gate_edit(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp, with_scripts=True)
    (repo / "quality-loop.config.json").write_text(json.dumps({"protect_harness": False}))
    code, out, err = run_script(PRE, {"cwd": str(repo), "tool_name": "Edit", "tool_input": {"file_path": "scripts/quality_loop.py", "new_string": "# comment"}}, repo)
    return code == 0 and out.strip() == "", f"exit={code}; out={out.strip()!r}; err={err.strip()!r}"


def case_pretool_missing_runtime_allows_with_warning(tmp: Path) -> tuple[bool, str]:
    # A missing CQL runtime is NOT a secret finding: allow, and name the actual
    # problem on stderr instead of fabricating "secret-like text blocked".
    repo = make_repo(tmp)  # no scripts/
    payload = {"cwd": str(repo), "tool_name": "Write", "tool_input": {"file_path": "notes.txt", "content": 'api_key = "ghp_' + "A" * 36 + '"'}}
    code, out, err = run_script(PRE, payload, repo)
    ok = code == 0 and out.strip() == "" and "CQL runtime missing" in err
    return ok, f"exit={code}; out={out.strip()!r}; err={err.strip()[:160]!r}"


def case_pretool_scans_without_python3_on_path(tmp: Path) -> tuple[bool, str]:
    # The scan child is spawned via sys.executable, so a PATH without python3
    # (git only) must still produce a REAL scan result, not a spawn crash.
    git_path = shutil.which("git")
    if not git_path:
        return False, "git not found on PATH"
    bindir = tmp / "bin"
    bindir.mkdir()
    (bindir / "git").symlink_to(git_path)
    repo = make_repo(tmp, with_scripts=True)
    env = {**os.environ, "PATH": str(bindir)}
    payload = {"cwd": str(repo), "tool_name": "Write", "tool_input": {"content": 'api_key = "ghp_' + "A" * 36 + '"'}}
    code, out, err = run_script(PRE, payload, repo, env=env)
    return code == 0 and deny_json(out), f"exit={code}; out={out.strip()[:160]!r}; err={err.strip()[:160]!r}"


def case_pretool_legacy_config_warns(tmp: Path) -> tuple[bool, str]:
    # Old .quality-loop/config.json still works as a fallback, with a one-line
    # deprecation warning naming the move to root quality-loop.config.json.
    repo = make_repo(tmp, with_scripts=True)
    (repo / ".quality-loop").mkdir()
    (repo / ".quality-loop" / "config.json").write_text(json.dumps({"enforcement": "advisory"}))
    code, out, err = run_script(PRE, {"cwd": str(repo), "tool_name": "Write", "tool_input": {"content": "safe text"}}, repo)
    ok = code == 0 and out.strip() == "" and "deprecated" in err and "quality-loop.config.json" in err
    return ok, f"exit={code}; out={out.strip()!r}; err={err.strip()[:160]!r}"


def case_pretool_canonical_config_required(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp, with_scripts=True)
    (repo / "quality-loop.config.json").write_text(json.dumps({"enforcement": "required"}))
    record = done_record()
    record["status"] = "plan"
    record["minimality_decision"] = None
    (repo / "agent-record.json").write_text(json.dumps(record))
    code, out, err = run_script(PRE, {"cwd": str(repo), "tool_name": "Write", "tool_input": {"content": "safe text"}}, repo)
    ok = code == 0 and deny_json(out) and "PLAN" in out and "deprecated" not in err
    return ok, f"exit={code}; out={out.strip()[:160]!r}; err={err.strip()[:120]!r}"


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


def _stop(repo: Path, env: dict | None = None) -> tuple[int, str, str]:
    return run_script(STOP, {"cwd": str(repo), "hook_event_name": "Stop", "stop_hook_active": False}, repo, env=env)


def _decision(out: str) -> str | None:
    try:
        return json.loads(out).get("decision")
    except json.JSONDecodeError:
        return None


def _stub_gate_repo(tmp: Path, stub_body: str, status: str = "done") -> Path:
    """A repo whose scripts/quality_loop.py is a stub, so the stop gate's child
    invocation is observable without depending on the real gate engine."""
    repo = make_repo(tmp)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "quality_loop.py").write_text(stub_body)
    record = done_record()
    record["status"] = status
    (repo / "agent-record.json").write_text(json.dumps(record))
    return repo


def case_stop_gate_allows_no_record_no_loop(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    code, out, err = _stop(repo)
    return code == 0 and out.strip() == "", f"exit={code}; out={out.strip()!r}; err={err.strip()!r}"


def case_stop_gate_blocks_deleted_record_with_config(tmp: Path) -> tuple[bool, str]:
    # Loop artifacts without a record mean the record was deleted mid-loop —
    # deletion must not lift the gate, and the message must say how to restore.
    repo = make_repo(tmp)
    (repo / "quality-loop.config.json").write_text(json.dumps({"enforcement": "advisory"}))
    code, out, err = _stop(repo)
    ok = code == 0 and _decision(out) == "block" and "init-record" in out
    return ok, f"exit={code}; decision={_decision(out)}; out={out.strip()[:200]!r}"


def case_stop_gate_allows_manifest_only_install(tmp: Path) -> tuple[bool, str]:
    # Every fresh v6 install writes .quality-loop/install-manifest.json. That
    # alone is NOT loop state: a record-less stop right after install must be
    # allowed, or the gate bricks every freshly installed repo.
    repo = make_repo(tmp)
    (repo / ".quality-loop").mkdir()
    (repo / ".quality-loop" / "install-manifest.json").write_text(json.dumps({
        "version": 1, "host": "claude-code", "files": [], "hook_groups": [],
    }))
    code, out, err = _stop(repo)
    return code == 0 and out.strip() == "", f"exit={code}; out={out.strip()[:200]!r}; err={err.strip()!r}"


def case_stop_gate_blocks_tombstoned_record_deletion(tmp: Path) -> tuple[bool, str]:
    # A git-tracked record deleted from the tree leaves a tombstone: even with
    # no config file, the deletion must not lift the gate.
    repo = make_repo(tmp)
    qdir = repo / ".quality-loop"
    qdir.mkdir()
    (qdir / "agent-record.json").write_text(json.dumps(done_record()))
    git(repo, "add", ".quality-loop/agent-record.json")
    git(repo, "commit", "-m", "record")
    (qdir / "agent-record.json").unlink()
    code, out, err = _stop(repo)
    ok = code == 0 and _decision(out) == "block" and "init-record" in out
    return ok, f"exit={code}; decision={_decision(out)}; out={out.strip()[:200]!r}"


def case_settings_stop_timeout_covers_verify(tmp: Path) -> tuple[bool, str]:
    # Terminal Stop runs the full verify umbrella, which re-executes recorded
    # evidence at up to 120s per command (QUALITY_LOOP_TIMEOUT-overridable). A
    # 30s outer hook timeout killed honest slow suites mid-verify, so the Stop
    # hook must carry a generous terminal-status budget (>= 600s). Tradeoff: a
    # genuinely hung suite can hold the stop for that long — acceptable, since
    # the alternative silently kills truthful evidence re-execution.
    settings = json.loads((ROOT / "hosts" / "claude-code" / "settings.json").read_text(encoding="utf-8"))
    stop_hooks = [h for entry in settings["hooks"]["Stop"] for h in entry["hooks"]]
    timeouts = [h.get("timeout") for h in stop_hooks]
    ok = bool(timeouts) and all(isinstance(t, int) and t >= 600 for t in timeouts)
    return ok, f"stop_timeouts={timeouts} (need >= 600 to cover 120s/command evidence re-execution)"


def case_stop_gate_terminal_runs_verify_umbrella(tmp: Path) -> tuple[bool, str]:
    # At package/done the child must be the `verify` umbrella, with --base only
    # when QUALITY_LOOP_BASE is set (otherwise the script auto-resolves it).
    stub = "import sys\nprint('ARGS: ' + ' '.join(sys.argv[1:]))\nsys.exit(1)\n"
    repo = _stub_gate_repo(tmp, stub)
    env = {k: v for k, v in os.environ.items() if k != "QUALITY_LOOP_BASE"}
    code, out, _ = _stop(repo, env=env)
    ok_default = code == 0 and _decision(out) == "block" and "ARGS: verify " in out and "--base" not in out
    code2, out2, _ = _stop(repo, env={**env, "QUALITY_LOOP_BASE": "main"})
    ok_env = code2 == 0 and "--base main" in out2
    return ok_default and ok_env, f"default_ok={ok_default} env_ok={ok_env}; out={out.strip()[:200]!r}"


def case_stop_gate_timeout_failure_names_override(tmp: Path) -> tuple[bool, str]:
    # A timeout-looking gate failure must tell the agent that slow suites can
    # raise the limit via QUALITY_LOOP_TIMEOUT.
    stub = "import sys\nprint('evidence: pytest timed out after 30s')\nsys.exit(1)\n"
    repo = _stub_gate_repo(tmp, stub)
    code, out, _ = _stop(repo)
    ok = code == 0 and _decision(out) == "block" and "QUALITY_LOOP_TIMEOUT" in out
    return ok, f"exit={code}; decision={_decision(out)}; out={out.strip()[:200]!r}"


def case_stop_gate_terminal_exit2_names_cause(tmp: Path) -> tuple[bool, str]:
    # Child exit 2 (missing/crashed runner) is an environment problem, not gate
    # findings: the block must say so and still offer the three ways forward.
    repo = make_repo(tmp)  # no scripts/ -> python exits 2 (can't open file)
    (repo / "agent-record.json").write_text(json.dumps(done_record()))
    code, out, err = _stop(repo)
    ok = (
        code == 0
        and _decision(out) == "block"
        and "environment problem" in out
        and "Three legitimate ways forward" in out
    )
    return ok, f"exit={code}; decision={_decision(out)}; out={out.strip()[:220]!r}"


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


def case_uninstall_skips_symlink_traversal(tmp: Path) -> tuple[bool, str]:
    # Security fix: a manifest entry whose directory component is a committed
    # symlink pointing outside the target must be SKIPPED, never unlinked.
    target = tmp / "target"
    victim = tmp / "victim"
    victim.mkdir(parents=True)
    outside = victim / "p2.txt"
    outside.write_text("precious\n")
    (target / ".quality-loop").mkdir(parents=True)
    (target / "linkdir").symlink_to(Path("..") / "victim")
    (target / ".quality-loop" / "install-manifest.json").write_text(json.dumps({
        "version": 1, "host": "claude-code", "files": ["linkdir/p2.txt"], "hook_groups": [],
    }))
    code, out, err = run_cli(str(INSTALL), "--target", str(target), "--uninstall", cwd=ROOT)
    ok = (
        code == 0
        and outside.is_file()
        and "skipped linkdir/p2.txt" in out
        and "removed linkdir/p2.txt" not in out
    )
    return ok, f"exit={code}; victim_survives={outside.is_file()}; out={out.strip()[:220]!r}; err={err.strip()!r}"


def case_installer_ships_prompts_and_routing_default(tmp: Path) -> tuple[bool, str]:
    # render-prompt reads assets/prompts/<role>.md next to scripts/, and
    # SKILL.md references assets/routing/ — both must land on a DEFAULT install
    # (no --with-control-plane). --host all must not install demoted cursor/pi.
    repo = make_repo(tmp)
    code1, out1, err1 = run_cli(str(INSTALL), "--target", str(repo), "--host", "all", cwd=ROOT)
    record = repo / "rec.json"
    record.write_text(json.dumps(done_record()))
    code2, out2, err2 = run_cli(
        str(repo / "scripts" / "quality_loop.py"),
        "render-prompt", "--role", "reviewer", "--record", str(record),
        cwd=repo,
    )
    ok = (
        code1 == 0
        and (repo / "assets" / "prompts" / "reviewer.md").is_file()
        and (repo / "assets" / "routing" / "README.md").is_file()
        and not (repo / "assets" / "control-plane").exists()
        and not (repo / ".cursor").exists()
        and not (repo / ".pi").exists()
        and code2 == 0
        and "Quality Loop Reviewer" in out2
    )
    return ok, f"codes={[code1, code2]}; err={(err1 + err2).strip()[:220]!r}"


CASES = [
    ("PreToolUse blocks destructive Bash", case_pretool_blocks_destructive),
    ("PreToolUse blocks secret Write content", case_pretool_blocks_secret_write),
    ("PreToolUse required mode blocks medium edit before plan", case_pretool_required_blocks_edit_before_plan),
    ("PreToolUse allows safe Write", case_pretool_allows_safe_write),
    ("PreToolUse blocks rm with reordered/long recursive+force flags", case_pretool_blocks_flag_order_variants),
    ("PreToolUse allows quoted mentions and cross-command force flags", case_pretool_allows_quoted_or_other_command),
    ("PreToolUse blocks wrapper-invoked destructive forms (bash -c, /bin/rm, env, xargs)", case_pretool_blocks_wrapper_forms),
    ("PreToolUse allows git push --force-with-lease but denies --force/-f", case_pretool_allows_force_with_lease),
    ("PreToolUse scanner crash (exit 1, no findings JSON) allows with warning", case_pretool_scan_crash_allows_with_warning),
    ("PreToolUse protects hook wiring files and the install manifest", case_pretool_protects_hook_wiring_and_manifest),
    ("PreToolUse apply_patch body targeting a protected path is denied", case_pretool_apply_patch_body_targets_protected),
    ("PreToolUse blocks deletion of the record and .quality-loop", case_pretool_blocks_record_deletion),
    ("PreToolUse protect_harness blocks gate/hook/record edits by default", case_pretool_protect_harness_blocks_gate_edit),
    ("PreToolUse protect_harness=false allows gate-script edit", case_pretool_protect_harness_off_allows_gate_edit),
    ("PreToolUse missing runtime allows with a truthful warning", case_pretool_missing_runtime_allows_with_warning),
    ("PreToolUse scans via sys.executable without python3 on PATH", case_pretool_scans_without_python3_on_path),
    ("PreToolUse legacy .quality-loop/config.json warns but still works", case_pretool_legacy_config_warns),
    ("PreToolUse canonical quality-loop.config.json drives required mode", case_pretool_canonical_config_required),
    ("Stop gate blocks phantom done", case_stop_gate_blocks_phantom_done),
    ("Stop gate allows a repo with no record and no loop artifacts", case_stop_gate_allows_no_record_no_loop),
    ("Stop gate blocks a deleted record while loop config exists", case_stop_gate_blocks_deleted_record_with_config),
    ("Stop gate allows a fresh install with only the install manifest", case_stop_gate_allows_manifest_only_install),
    ("Stop gate blocks a git-tombstoned record deletion without config", case_stop_gate_blocks_tombstoned_record_deletion),
    ("Stop hook timeout covers the terminal verify umbrella budget", case_settings_stop_timeout_covers_verify),
    ("Stop gate runs the verify umbrella at terminal statuses", case_stop_gate_terminal_runs_verify_umbrella),
    ("Stop gate names QUALITY_LOOP_TIMEOUT on timeout-looking failures", case_stop_gate_timeout_failure_names_override),
    ("Stop gate names the cause and remedies on runner exit 2", case_stop_gate_terminal_exit2_names_cause),
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
    ("uninstall skips manifest paths that traverse a symlink outside the target", case_uninstall_skips_symlink_traversal),
    ("default install ships prompts+routing; render-prompt works; all skips cursor/pi", case_installer_ships_prompts_and_routing_default),
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
