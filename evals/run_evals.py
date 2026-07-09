#!/usr/bin/env python3
"""Record-gate eval harness for the Coding Quality Loop.

These cases exercise the *runtime* record gates in `scripts/quality_loop.py`
(`verify-gates`, `check-record`, `diff-audit`) against constructed agent
records. They complement the static intake-derivation cases in `evals/cases/`
(run with `quality_loop.py eval-cases`), which assert `evaluate_input`.

Run: python evals/run_evals.py   (exits non-zero if any case fails)

Cases (safety-hardening behaviors enforced on actual records):
  1. tiny work does NOT require mission artifacts
  2. medium work requires a validation contract and independent review
  3. security/high work requires a DISTINCT security review (a passing
     class=security command is not sufficient); an approving review satisfies it
  4. right-size gate catches an unnecessary dependency
  5. the implementer cannot be the final validator
  6. a repeated mistake triggers a durable retrospective harness update (docs)
  7. package status without a completion record fails (shipping gate)
  8. a rejected independent review fails
  9. missing implementer fails
 10. boolean validation/completion placeholders fail
 11. malformed commands_run fails cleanly without crashing
 12. shallow/nonexistent artifact placeholders fail (object missing required
     content, or a string path that does not resolve to a real file)
 13. complete inline artifact objects pass without files on disk
 14. a string artifact that points at an existing file passes
 15. repeated verification failure requires a durable harness_update
     (retrospective evidence), not a repeated chat correction
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "quality_loop.py"

# Canonical count of offline GATE cases. This is the single source of truth the
# count-consistency lint (case_doc_counts_match_canonical) asserts every public
# doc agrees with. It EXCLUDES the trigger smoke fixture, whose default grader is
# reverse-engineered from its own prompts and cannot fail (see
# evals/run_trigger_evals.py, evals/README.md).
#
# BUMP THIS whenever a gate suite's case count changes. Current breakdown:
#   11 static + 38 behavioral + 26 memory + 22 reality + 13 routing + 15 hook = 125
# (behavioral is this file: len(CASES); run it to confirm the number.)
CANONICAL_GATE_CASES = 125

sys.path.insert(0, str(ROOT / "scripts"))
import quality_loop  # noqa: E402  (used for the static evaluate_input consistency check)

PASS = "PASS"
FAIL = "FAIL"


def run_cli(*args: str, cwd: str | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def base_record(**overrides) -> dict:
    record = {
        "task_id": "t-eval",
        "goal": "eval goal",
        "task_class": None,
        "risk_tier": "medium",
        "acceptance_criteria": ["does the thing"],
        "constraints": [],
        "non_goals": [],
        "assumptions": [],
        "verification_plan": ["unit tests"],
        "minimality_decision": {"rung": "reuse", "reason": "existing helper covers it"},
        "plan": ["one slice"],
        "commands_run": [{"cmd": "pytest", "class": "unit", "result": "pass", "evidence": "12 passed"}],
        "open_risks": [],
        "review_findings": ["fresh-context review: approved"],
        "repo_map": {
            "entry_points": ["mod/x.py:fn"],
            "likely_files": ["mod/x.py"],
            "callers_checked": ["mod/y.py:caller"],
            "tests": ["tests/test_x.py"],
            "patterns_to_follow": [],
        },
        "implementer": None,
        "validation_contract": None,
        "independent_review": None,
        "security_review": None,
        "completion_record": None,
        "security_sensitive": False,
        "status": "intake",
    }
    record.update(overrides)
    return record


COMPLETE_CONTRACT = {
    "goal": "Move invoice rounding to the summed total",
    "acceptance_criteria": ["Total rounds once; single-line invoices unchanged"],
    "evidence": ["pytest billing/tests -> pass", "mypy billing -> clean"],
}
COMPLETE_COMPLETION = {
    "goal": "Move invoice rounding to the summed total",
    "acceptance_criteria": ["Total rounds once; single-line invoices unchanged"],
    "evidence": ["pytest billing/tests -> 14 passed", "fresh-context review: approve"],
}


def passing_medium(**overrides) -> dict:
    """A fully compliant medium record that should pass all gates.

    Artifacts are complete inline objects (real content, not placeholder paths)
    so they satisfy the deep artifact validation in `verify-gates`.
    """
    record = base_record(
        risk_tier="medium",
        task_class="medium",
        status="done",
        implementer="agent-a",
        validation_contract=dict(COMPLETE_CONTRACT),
        completion_record=dict(COMPLETE_COMPLETION),
        independent_review={
            "reviewer": "agent-b",
            "verdict": "approve",
            "fresh_context": True,
            "patched": False,
            "findings": [],
        },
    )
    record.update(overrides)
    return record


def verify_gates(tmp: Path, record: dict) -> tuple[int, str]:
    path = tmp / "record.json"
    path.write_text(json.dumps(record))
    code, out, err = run_cli("verify-gates", str(path))
    return code, out + err


def check_record(tmp: Path, record: dict) -> tuple[int, str]:
    path = tmp / "record.json"
    path.write_text(json.dumps(record))
    code, out, err = run_cli("check-record", str(path))
    return code, out + err


# --- Cases -----------------------------------------------------------------


def case_tiny_no_artifacts(tmp: Path) -> tuple[bool, str]:
    record = base_record(
        risk_tier="low",
        task_class="tiny",
        commands_run=[{"cmd": "pytest test_x.py", "class": "unit", "result": "pass"}],
        status="done",
    )
    code, output = verify_gates(tmp, record)
    ok = code == 0 and "validation_contract" not in output and "completion_record" not in output
    return ok, f"exit={code}; output={output.strip()!r}"


def case_medium_requires_contract_and_review(tmp: Path) -> tuple[bool, str]:
    incomplete = base_record(
        risk_tier="medium",
        task_class="medium",
        status="review",
    )
    code_i, out_i = verify_gates(tmp, incomplete)
    needs_contract = "validation_contract" in out_i
    needs_review = "independent_review" in out_i
    incomplete_fails = code_i == 1 and needs_contract and needs_review

    code_c, out_c = verify_gates(tmp, passing_medium())
    complete_passes = code_c == 0

    ok = incomplete_fails and complete_passes
    return ok, f"incomplete(exit={code_i},contract={needs_contract},review={needs_review}); complete(exit={code_c}: {out_c.strip()!r})"


def case_security_requires_distinct_review(tmp: Path) -> tuple[bool, str]:
    # A passing class=security command is NOT sufficient on its own.
    self_attested = passing_medium(
        risk_tier="high",
        task_class="mission",
        security_sensitive=True,
        open_risks=["auth path"],
        commands_run=[
            {"cmd": "pytest", "class": "unit", "result": "pass"},
            {"cmd": "self security scan", "class": "security", "result": "pass"},
        ],
        security_review=None,
    )
    code_s, out_s = verify_gates(tmp, self_attested)
    self_fails = code_s == 1 and "security_review" in out_s

    # A distinct, approving security review satisfies the hard gate.
    reviewed = passing_medium(
        risk_tier="high",
        task_class="mission",
        security_sensitive=True,
        open_risks=["auth path"],
        commands_run=[
            {"cmd": "pytest", "class": "unit", "result": "pass", "evidence": "20 passed"},
            {"cmd": "semgrep", "class": "security", "result": "pass", "evidence": "no findings"},
        ],
        security_review={
            "reviewer": "sec-c",
            "verdict": "approve",
            "fresh_context": True,
            "patched": False,
        },
    )
    code_r, out_r = verify_gates(tmp, reviewed)
    reviewed_passes = code_r == 0

    ok = self_fails and reviewed_passes
    return ok, f"self-attested(exit={code_s},flagged={('security_review' in out_s)}); reviewed(exit={code_r}: {out_r.strip()!r})"


def case_right_size_gate_dependency(tmp: Path) -> tuple[bool, str]:
    def git(repo: Path, *args: str) -> None:
        subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def init_repo(name: str) -> Path:
        repo = tmp / name
        repo.mkdir()
        git(repo, "init")
        git(repo, "config", "user.email", "eval@example.com")
        git(repo, "config", "user.name", "eval")
        (repo / "main.py").write_text("print('hi')\n")
        git(repo, "add", "main.py")
        git(repo, "commit", "-m", "base")
        return repo

    dep_repo = init_repo("dep")
    (dep_repo / "requirements.txt").write_text("leftpad==1.0.0\n")
    git(dep_repo, "add", "requirements.txt")
    dep_code, dep_out, _ = run_cli("diff-audit", "--base", "HEAD", cwd=str(dep_repo))
    dep_ok = dep_code == 1 and "dependency files changed" in dep_out

    changelog_repo = init_repo("changelog")
    (changelog_repo / "CHANGELOG.md").write_text("## Changed\n\n- Document migration guidance.\n")
    git(changelog_repo, "add", "CHANGELOG.md")
    changelog_code, changelog_out, _ = run_cli("diff-audit", "--base", "HEAD", cwd=str(changelog_repo))
    changelog_ok = changelog_code == 0 and "migration/schema-related" not in changelog_out

    migration_repo = init_repo("migration")
    migration_file = migration_repo / "db" / "migrate" / "001_add_users.sql"
    migration_file.parent.mkdir(parents=True)
    migration_file.write_text("alter table users add column nickname text;\n")
    git(migration_repo, "add", str(migration_file.relative_to(migration_repo)))
    migration_code, migration_out, _ = run_cli("diff-audit", "--base", "HEAD", cwd=str(migration_repo))
    migration_ok = migration_code == 1 and "migration/schema-related files changed" in migration_out

    ok = dep_ok and changelog_ok and migration_ok
    return ok, (
        f"dependency(exit={dep_code},flagged={dep_ok}); "
        f"changelog(exit={changelog_code},clean={changelog_ok}); "
        f"migration(exit={migration_code},flagged={migration_ok})"
    )


def case_implementer_cannot_validate(tmp: Path) -> tuple[bool, str]:
    record = passing_medium(
        independent_review={
            "reviewer": "agent-a",  # same as implementer
            "verdict": "approve",
            "fresh_context": True,
            "patched": False,
        },
    )
    code, output = verify_gates(tmp, record)
    ok = code == 1 and "cannot be the implementer" in output
    return ok, f"exit={code}; output={output.strip()!r}"


def case_repeated_mistake_retrospective(tmp: Path) -> tuple[bool, str]:
    docs = [
        ROOT / "SKILL.md",
        ROOT / "references" / "engineering-operating-system.md",
        ROOT / "references" / "lifecycle.md",
        ROOT / "references" / "agentic-orchestration.md",
        ROOT / "assets" / "AGENTS.template.md",
    ]
    text = "\n".join(d.read_text().lower() for d in docs if d.exists())
    must_have = ["retrospective", "repeated mistake", "durable harness", "agents.md", "hooks"]
    missing = [m for m in must_have if m not in text]
    return (not missing), (f"missing={missing}" if missing else "all retrospective signals present")


def case_package_requires_completion_record(tmp: Path) -> tuple[bool, str]:
    record = passing_medium(status="package", completion_record=None)
    code, output = verify_gates(tmp, record)
    ok = code == 1 and "completion_record" in output and "package" in output
    return ok, f"exit={code}; output={output.strip()!r}"


def case_rejected_review_fails(tmp: Path) -> tuple[bool, str]:
    record = passing_medium(
        independent_review={
            "reviewer": "agent-b",
            "verdict": "request_changes",
            "fresh_context": True,
            "patched": False,
        },
    )
    code, output = verify_gates(tmp, record)
    ok = code == 1 and "not approving" in output
    return ok, f"exit={code}; output={output.strip()!r}"


def case_missing_implementer_fails(tmp: Path) -> tuple[bool, str]:
    record = passing_medium(implementer=None)
    code, output = verify_gates(tmp, record)
    ok = code == 1 and "named implementer" in output
    return ok, f"exit={code}; output={output.strip()!r}"


def case_boolean_placeholders_fail(tmp: Path) -> tuple[bool, str]:
    # check-record rejects bare booleans explicitly; verify-gates treats them as no evidence.
    record = passing_medium(validation_contract=True, completion_record=True)
    code_c, out_c = check_record(tmp, record)
    check_flags = code_c == 1 and "validation_contract" in out_c and "completion_record" in out_c

    code_g, out_g = verify_gates(tmp, record)
    gate_flags = code_g == 1 and "validation_contract" in out_g and "completion_record" in out_g

    ok = check_flags and gate_flags
    return ok, f"check(exit={code_c},flags={check_flags}); gate(exit={code_g},flags={gate_flags})"


def case_malformed_commands_no_crash(tmp: Path) -> tuple[bool, str]:
    record = passing_medium(commands_run=["not-a-dict", 123, {"cmd": "x", "result": "bogus"}])
    code, output = verify_gates(tmp, record)
    crashed = "Traceback" in output
    ok = code == 1 and not crashed and "malformed" in output
    return ok, f"exit={code}; crashed={crashed}; output={output.strip()!r}"


def case_shallow_artifacts_fail(tmp: Path) -> tuple[bool, str]:
    # An object with only a placeholder key and a nonexistent string path are
    # both shape-valid but not real artifacts; the shipping gate must reject them.
    record = passing_medium(
        validation_contract={"placeholder": "yes"},
        completion_record="nonexistent-completion-record.md",
    )
    code, output = verify_gates(tmp, record)
    flagged = "validation_contract" in output and "completion_record" in output
    ok = code == 1 and flagged
    return ok, f"exit={code}; flagged={flagged}; output={output.strip()!r}"


def case_valid_inline_artifacts_pass(tmp: Path) -> tuple[bool, str]:
    # Complete inline artifact objects (goal + acceptance criteria + evidence)
    # are real evidence and must pass even without files on disk.
    record = passing_medium()
    code, output = verify_gates(tmp, record)
    ok = code == 0
    return ok, f"exit={code}; output={output.strip()!r}"


def case_existing_artifact_path_passes(tmp: Path) -> tuple[bool, str]:
    # A string artifact resolves to a real file relative to the record, and the
    # file must carry the required content (not just exist).
    (tmp / "validation-contract.md").write_text(
        "# contract\ngoal: round once\nacceptance criteria: total rounds once\nevidence: pytest -> pass\n"
    )
    (tmp / "completion-record.md").write_text(
        "# completion\ngoal: round once\nacceptance criteria: total rounds once\nevidence: pytest -> 14 passed\n"
    )
    record = passing_medium(
        validation_contract="validation-contract.md",
        completion_record="completion-record.md",
    )
    code, output = verify_gates(tmp, record)
    ok = code == 0
    return ok, f"exit={code}; output={output.strip()!r}"


def case_repeated_failure_requires_harness_update(tmp: Path) -> tuple[bool, str]:
    # Repeated verification failure with no durable harness change must fail;
    # the same record with a harness_update passes.
    no_update = passing_medium(repeated_failure=True, harness_update=None)
    code_n, out_n = verify_gates(tmp, no_update)
    no_update_fails = code_n == 1 and "harness_update" in out_n

    with_update = passing_medium(
        repeated_failure=True,
        harness_update={"type": "test", "change": "added regression test for the skipped null check"},
    )
    code_w, out_w = verify_gates(tmp, with_update)
    with_update_passes = code_w == 0

    # repair_attempts >= 2 is also treated as a repeated failure.
    by_attempts = passing_medium(repair_attempts=2, harness_update=None)
    code_a, _ = verify_gates(tmp, by_attempts)
    attempts_fail = code_a == 1

    ok = no_update_fails and with_update_passes and attempts_fail
    return ok, (
        f"no_update(exit={code_n},flagged={('harness_update' in out_n)}); "
        f"with_update(exit={code_w}: {out_w.strip()!r}); by_attempts(exit={code_a})"
    )


def case_untracked_secret_flagged(tmp: Path) -> tuple[bool, str]:
    # `git diff <base>` excludes untracked files; a brand-new module with a
    # secret must still be caught by diff-audit.
    repo = tmp / "repo"
    repo.mkdir()

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    git("init")
    git("config", "user.email", "eval@example.com")
    git("config", "user.name", "eval")
    (repo / "main.py").write_text("print('hi')\n")
    git("add", "main.py")
    git("commit", "-m", "base")

    # leak.py is NEVER `git add`-ed - it stays untracked.
    (repo / "leak.py").write_text('AKIA' + 'A' * 16 + '\napi_key = abcd1234abcd1234\n')

    code, out, _ = run_cli("diff-audit", "--base", "HEAD", cwd=str(repo))
    ok = code == 1 and "secret" in out and "untracked" in out
    return ok, f"exit={code}; output={out.strip()!r}"


def case_self_downgrade_auth_fails(tmp: Path) -> tuple[bool, str]:
    # A boundary task (disable auth) declared low/tiny with empty evidence must
    # NOT pass - the detected-risk floor overrides the self-declared tier.
    record = base_record(
        goal="Disable auth check on admin endpoint",
        risk_tier="low",
        task_class="tiny",
        security_sensitive=False,
        commands_run=[],
        minimality_decision={"rung": "one_liner", "reason": "remove the check"},
        validation_contract=None,
        independent_review=None,
        completion_record=None,
        status="done",
    )
    code, output = verify_gates(tmp, record)
    ok = code == 1 and ("boundary" in output or "downgrade" in output)
    return ok, f"exit={code}; output={output.strip()!r}"


def case_floor_catches_more_boundary_phrasings(tmp: Path) -> tuple[bool, str]:
    # The floor vocabulary must cover how engineers actually phrase boundary work,
    # not just the canonical word. Each self-downgraded phrasing must fail.
    phrasings = [
        "Fix the authz middleware ordering",
        "Add an MFA bypass for service accounts",
        "Disable TLS certificate verification in the client",
        "Process a payout to the vendor account",
        "Add an RBAC permission for the billing service",
    ]
    results = []
    for goal in phrasings:
        record = base_record(
            goal=goal,
            risk_tier="low",
            task_class="tiny",
            security_sensitive=False,
            commands_run=[],
            validation_contract=None,
            independent_review=None,
            completion_record=None,
            status="done",
        )
        code, output = verify_gates(tmp, record)
        results.append(code == 1 and "boundary" in output)
    ok = all(results)
    return ok, f"caught={results} for {phrasings}"


def case_floor_catches_new_boundaries(tmp: Path) -> tuple[bool, str]:
    # v1.5 added concurrency/race/data-loss/PII to the runtime boundary keywords.
    # Each self-downgraded phrasing must fail the floor.
    phrasings = [
        "Fix the race condition in the checkout handler",
        "Prevent data loss on partial writes",
        "Add a concurrency guard to the queue worker",
        "Mask PII in the audit log",
        "Add GDPR data retention controls",
    ]
    results = []
    for goal in phrasings:
        record = base_record(
            goal=goal,
            risk_tier="low",
            task_class="tiny",
            security_sensitive=False,
            commands_run=[],
            validation_contract=None,
            independent_review=None,
            completion_record=None,
            status="done",
        )
        code, output = verify_gates(tmp, record)
        results.append(code == 1 and "boundary" in output)
    ok = all(results)
    return ok, f"caught={results} for {phrasings}"


def case_secret_guard_flags_real_keys(tmp: Path) -> tuple[bool, str]:
    # The placeholder guard must skip only obvious stubs, never suppress a real
    # value that merely starts with 'your_'; and quoted secrets must match too.
    def flag(s: str) -> bool:
        return any(p.search(s) for p in quality_loop.SECRET_PATTERNS)

    must_flag = [
        "api_key = your_realProductionKey99AAA",
        'passwd = "hunter2hunter2hunter2"',
        "credential = abcd1234abcd1234",
    ]
    must_skip = [
        "api_key = REPLACE_ME",
        "token = ${TOKEN}",
        "api_key = <your-key-here>",
        "api_key = os.environ.get('HONCHO_API_KEY', '')",
    ]
    flagged = all(flag(s) for s in must_flag)
    skipped = all(not flag(s) for s in must_skip)
    return (flagged and skipped), f"flagged_real={flagged} skipped_stubs={skipped}"


def case_floor_ignores_benign_common_words(tmp: Path) -> tuple[bool, str]:
    # The floor must NOT force ceremony onto benign copy/docs that merely contain
    # a common word (admin / token / session) - that is the process theater the
    # skill disclaims. Each tiny/low record should pass without a boundary warning.
    benign = [
        "Improve the admin dashboard welcome copy",
        "Rename the Token component in the design system",
        "Tidy the user session summary wording",
    ]
    results = []
    for goal in benign:
        record = base_record(
            goal=goal,
            risk_tier="low",
            task_class="tiny",
            commands_run=[{"cmd": "read", "class": "lint", "result": "pass", "evidence": "looks good"}],
            status="done",
        )
        code, output = verify_gates(tmp, record)
        results.append(code == 0 and "boundary" not in output)
    ok = all(results)
    return ok, f"clean={results} for {benign}"


def case_small_low_ships_without_completion_record(tmp: Path) -> tuple[bool, str]:
    # Consistency: the runtime gate and evaluate_input must agree that a small,
    # low-risk task ships with handoff evidence, not a formal completion record.
    record = base_record(
        goal="rename a local helper for clarity",
        risk_tier="low",
        task_class="small",
        commands_run=[{"cmd": "pytest test_helper.py", "class": "unit", "result": "pass", "evidence": "3 passed"}],
        status="done",
    )
    code, output = verify_gates(tmp, record)
    runtime_ok = code == 0 and "completion_record" not in output
    static = quality_loop.evaluate_input({"signals": []})  # empty signals -> small/low
    static_ok = static["task_class"] == "small" and static["requires_completion_record"] is False
    ok = runtime_ok and static_ok
    return ok, f"runtime(exit={code}) static(class={static['task_class']},req_cr={static['requires_completion_record']})"


def case_declared_high_auth_passes(tmp: Path) -> tuple[bool, str]:
    # The floor must not false-block a properly-declared, fully-reviewed boundary
    # task: a compliant high-risk auth record with a distinct security review passes.
    record = passing_medium(
        goal="Add an authorization scope check to the admin endpoint",
        risk_tier="high",
        task_class="medium",
        security_sensitive=True,
        open_risks=["auth path"],
        commands_run=[
            {"cmd": "pytest", "class": "unit", "result": "pass", "evidence": "12 passed"},
            {"cmd": "semgrep", "class": "security", "result": "pass", "evidence": "no findings"},
        ],
        security_review={
            "reviewer": "sec-c",
            "verdict": "approve",
            "fresh_context": True,
            "patched": False,
        },
    )
    code, output = verify_gates(tmp, record)
    return code == 0, f"exit={code}; output={output.strip()!r}"


def case_wrong_content_artifact_fails(tmp: Path) -> tuple[bool, str]:
    # An existing file with no contract content must NOT satisfy the gate
    # (cwd-independent: resolved relative to the record in tmp).
    (tmp / "wrong.md").write_text("just prose, no contract fields here")
    record = passing_medium(validation_contract="wrong.md")
    code, output = verify_gates(tmp, record)
    ok = code == 1 and "missing required content" in output
    return ok, f"exit={code}; output={output.strip()!r}"


def case_unknown_command_class_fails(tmp: Path) -> tuple[bool, str]:
    record = passing_medium(
        commands_run=[{"cmd": "echo ok", "class": "bogus", "result": "pass", "evidence": "x"}]
    )
    code, output = check_record(tmp, record)
    ok = code == 1 and "class" in output
    return ok, f"exit={code}; output={output.strip()!r}"


def case_pass_command_needs_evidence(tmp: Path) -> tuple[bool, str]:
    record = passing_medium(
        commands_run=[{"cmd": "pytest", "class": "unit", "result": "pass"}]
    )
    code, output = verify_gates(tmp, record)
    ok = code == 1 and "evidence" in output
    return ok, f"exit={code}; output={output.strip()!r}"


def case_empty_repo_map_fails(tmp: Path) -> tuple[bool, str]:
    # The UNDERSTAND verb must be gated: non-trivial work with no context map fails.
    record = passing_medium(
        repo_map={"entry_points": [], "likely_files": [], "callers_checked": [], "tests": []}
    )
    code, output = verify_gates(tmp, record)
    ok = code == 1 and "context map" in output
    return ok, f"exit={code}; output={output.strip()!r}"


def case_brief_empty_repo(tmp: Path) -> tuple[bool, str]:
    code, out, err = run_cli("brief", "--cwd", str(tmp))
    ok = code == 0 and "none found" in out and "Suggested next step" in out
    return ok, f"exit={code}; out={out.strip()!r}"


def case_brief_with_record_and_progress(tmp: Path) -> tuple[bool, str]:
    qdir = tmp / ".quality-loop"
    qdir.mkdir(parents=True, exist_ok=True)
    record = {
        "task_id": "test-1", "goal": "Fix the billing bug", "status": "review",
        "risk_tier": "medium", "open_risks": ["race condition in charge()"],
        "review_findings": [], "task_class": "medium",
    }
    (qdir / "agent-record.json").write_text(json.dumps(record), encoding="utf-8")
    (qdir / "progress.md").write_text(
        "# Progress\n\n## Current goal\nFix the billing bug\n\n## Next step\nAdd regression test\n",
        encoding="utf-8",
    )
    code, out, err = run_cli("brief", "--cwd", str(tmp))
    ok = (
        code == 0
        and "Fix the billing bug" in out
        and "race condition" in out
        and "Add regression test" in out
        and "Resume incomplete task" in out
    )
    return ok, f"exit={code}; out={out.strip()!r}"


def case_brief_json_valid(tmp: Path) -> tuple[bool, str]:
    code, out, err = run_cli("brief", "--cwd", str(tmp), "--json")
    ok = False
    try:
        data = json.loads(out)
        ok = code == 0 and "next_step" in data and "lessons_recalled" in data
    except json.JSONDecodeError:
        ok = False
    return ok, f"exit={code}; json_valid={ok}"


def case_brief_with_run_journal(tmp: Path) -> tuple[bool, str]:
    runs_dir = tmp / ".quality-loop" / "runs" / "2026-07-01-001"
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "journal.jsonl").write_text(
        "\n".join(json.dumps(e) for e in [
            {"step": "INTAKE", "ts": "2026-07-01T10:00:00"},
            {"step": "IMPLEMENT_SLICE", "ts": "2026-07-01T10:05:00"},
            {"step": "PACKAGE", "ts": "2026-07-01T10:15:00"},
        ]),
        encoding="utf-8",
    )
    code, out, err = run_cli("brief", "--cwd", str(tmp))
    ok = (
        code == 0
        and "INTAKE" in out
        and "PACKAGE" in out
        and "Last run shipped" in out
    )
    return ok, f"exit={code}; out={out.strip()!r}"


def case_schema_accepts_object_acceptance_criteria(tmp: Path) -> tuple[bool, str]:
    """The agent-record schema must allow acceptance_criteria entries that are
    objects carrying a proving_command (for the AC-to-command coverage gate),
    while still accepting plain string criteria.
    """
    schema_path = ROOT / "assets" / "agent-record.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    items = schema["properties"]["acceptance_criteria"]["items"]
    one_of = items.get("oneOf", [])
    has_string = any(s.get("type") == "string" for s in one_of)
    obj_def = next((s for s in one_of if isinstance(s, dict) and s.get("type") == "object"), None)
    has_object = obj_def is not None
    has_proving_command = bool(obj_def and "proving_command" in obj_def.get("properties", {}))
    required = obj_def.get("required", []) if obj_def else []
    criterion_required = "criterion" in required
    proving_required = "proving_command" in required
    ok = has_string and has_object and has_proving_command and criterion_required and proving_required
    return ok, (
        f"string={has_string}; object={has_object}; "
        f"proving_command={has_proving_command}; criterion_required={criterion_required}; "
        f"proving_required={proving_required}"
    )


def case_run_metrics_valid_passes(tmp: Path) -> tuple[bool, str]:
    # Optional run_metrics with non-negative numbers must be accepted by check-record.
    record = base_record(
        run_metrics={"tokens_in": 1200, "tokens_out": 800, "cost_usd": 0.42, "duration_sec": 30.5}
    )
    code, output = check_record(tmp, record)
    ok = code == 0 and "run_metrics" not in output
    return ok, f"exit={code}; output={output.strip()!r}"


def case_run_metrics_string_cost_fails(tmp: Path) -> tuple[bool, str]:
    # A non-numeric metric value must be rejected by check-record.
    record = base_record(run_metrics={"cost_usd": "0.42"})
    code, output = check_record(tmp, record)
    ok = code == 1 and "run_metrics.cost_usd" in output and "number" in output
    return ok, f"exit={code}; output={output.strip()!r}"


def _repo_with_uncommitted_change(tmp: Path, name: str) -> Path:
    """A git repo with a base commit plus a new untracked file, so the diff vs
    HEAD is non-empty (the shipped-work case --require-terminal guards)."""
    repo = tmp / name
    repo.mkdir()

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    git("init")
    git("config", "user.email", "eval@example.com")
    git("config", "user.name", "eval")
    (repo / "main.py").write_text("print('hi')\n")
    git("add", "main.py")
    git("commit", "-m", "base")
    (repo / "feature.py").write_text("def feature():\n    return 1\n")  # untracked -> dirty diff
    return repo


def case_require_terminal_blocks_unclosed_loop(tmp: Path) -> tuple[bool, str]:
    # implement status + non-empty diff + --require-terminal -> verify fails with
    # the shipped-unclosed finding; the same run WITHOUT the flag must not raise it.
    repo = _repo_with_uncommitted_change(tmp, "rt-block")
    (repo / "record.json").write_text(json.dumps(passing_medium(status="implement")))
    code_flag, out_flag, err_flag = run_cli(
        "verify", "record.json", "--base", "HEAD", "--require-terminal", cwd=str(repo)
    )
    combined_flag = out_flag + err_flag
    blocked = code_flag != 0 and "work shipped without closing the loop" in combined_flag

    code_no, out_no, err_no = run_cli("verify", "record.json", "--base", "HEAD", cwd=str(repo))
    finding_absent_without_flag = "work shipped without closing the loop" not in (out_no + err_no)

    ok = blocked and finding_absent_without_flag
    return ok, f"flag(exit={code_flag},blocked={blocked}); no_flag(finding_absent={finding_absent_without_flag})"


def case_require_terminal_noop_when_done(tmp: Path) -> tuple[bool, str]:
    # done status: --require-terminal is a no-op — no shipped-unclosed finding and
    # the exit code is unchanged vs running verify without the flag.
    repo = _repo_with_uncommitted_change(tmp, "rt-done")
    (repo / "record.json").write_text(json.dumps(passing_medium(status="done")))
    code_flag, out_flag, err_flag = run_cli(
        "verify", "record.json", "--base", "HEAD", "--require-terminal", cwd=str(repo)
    )
    code_no, out_no, err_no = run_cli("verify", "record.json", "--base", "HEAD", cwd=str(repo))
    no_finding = "work shipped without closing the loop" not in (out_flag + err_flag)
    unaffected = code_flag == code_no
    ok = no_finding and unaffected
    return ok, f"flag(exit={code_flag},no_finding={no_finding}); no_flag(exit={code_no}); unaffected={unaffected}"


def case_doc_counts_match_canonical(tmp: Path) -> tuple[bool, str]:
    # Numbers-consistency lint (critical review R2): every public doc that states an
    # offline gate-case count must state CANONICAL_GATE_CASES. Guards against the
    # 116->121 drift the review flagged. The trigger smoke fixture is counted
    # separately and always as "10-case ..." (hyphen + singular), which this pattern
    # deliberately does not match.
    docs = [
        ROOT / "README.md",
        ROOT / "ROADMAP.md",
        ROOT / "docs" / "README.md",
        ROOT / "docs" / "comparison.md",
        ROOT / "docs" / "launch-kit.md",
        ROOT / "evals" / "README.md",
    ]
    # Matches the headline phrasings only: "<n> cases", "<n> gate cases",
    # "<n> eval cases", "<n> offline cases", "<n> offline gate/eval cases".
    pattern = re.compile(r"(\d+)\s+(?:offline\s+)?(?:gate\s+|eval\s+)?cases\b", re.IGNORECASE)
    mismatches = []
    for doc in docs:
        rel = doc.relative_to(ROOT)
        if not doc.exists():
            mismatches.append(f"{rel}: MISSING")
            continue
        for m in pattern.finditer(doc.read_text(encoding="utf-8")):
            n = int(m.group(1))
            if n != CANONICAL_GATE_CASES:
                mismatches.append(f"{rel}: {m.group(0)!r} != {CANONICAL_GATE_CASES}")
    ok = not mismatches
    return ok, ("all docs match canonical" if ok else f"mismatches={mismatches}")


def case_bench_validate_requires_cost_fields(tmp: Path) -> tuple[bool, str]:
    # Cost-instrumentation gate (critical review R3): the live-sweep validator must
    # PASS a fixture run (zero placeholders are exempt) and FAIL a synthetic live
    # result that omits the cost fields. Hermetic: both files live under tmp; the
    # committed examples/*/results.json are intentionally not touched.
    bench_runner = ROOT / "bench" / "runner.py"
    if not bench_runner.exists():
        return False, "bench/runner.py missing"

    def run(*args: str) -> tuple[int, str]:
        proc = subprocess.run(
            [sys.executable, str(bench_runner), *args],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        return proc.returncode, proc.stdout + proc.stderr

    fixture_out = tmp / "fixture.json"
    gen_code, _ = run("--mode", "fixture", "--seeds", "1", "--out", str(fixture_out))
    val_code, val_out = run("--validate", str(fixture_out))
    fixture_ok = gen_code == 0 and val_code == 0 and "OK:" in val_out

    bad_live = tmp / "live-missing-cost.json"
    bad_live.write_text(
        json.dumps(
            {
                "mode": "live",
                "runs": [
                    {"task_id": "webapp", "arm": "skill", "seed": 0, "mode": "live",
                     "hidden_tests_passed": True}
                ],
            }
        ),
        encoding="utf-8",
    )
    bad_code, bad_out = run("--validate", str(bad_live))
    live_fails = bad_code == 1 and "MISSING-COST" in bad_out

    ok = fixture_ok and live_fails
    return ok, f"fixture_validates={fixture_ok}; live_missing_cost_fails={live_fails}"


CASES = [
    ("tiny work does not require mission artifacts", case_tiny_no_artifacts),
    ("diff-audit flags secrets in untracked files", case_untracked_secret_flagged),
    ("self-downgrade of a boundary task fails the floor", case_self_downgrade_auth_fails),
    ("floor covers common boundary phrasings (authz/mfa/tls/payout/rbac)", case_floor_catches_more_boundary_phrasings),
    ("floor catches new boundaries (concurrency/race/data-loss/pii)", case_floor_catches_new_boundaries),
    ("floor ignores benign common words (admin/token/session copy)", case_floor_ignores_benign_common_words),
    ("small low-risk task ships without a completion record (runtime==static)", case_small_low_ships_without_completion_record),
    ("secret guard flags real keys and skips only stubs", case_secret_guard_flags_real_keys),
    ("compliant declared-high boundary task passes the floor", case_declared_high_auth_passes),
    ("non-trivial work with an empty context map fails", case_empty_repo_map_fails),
    ("existing file with wrong content fails the artifact gate", case_wrong_content_artifact_fails),
    ("unknown command class is rejected", case_unknown_command_class_fails),
    ("pass-labeled command without evidence fails", case_pass_command_needs_evidence),
    ("medium work requires validation contract and independent review", case_medium_requires_contract_and_review),
    ("security/high work requires a distinct security review", case_security_requires_distinct_review),
    ("right-size gate catches unnecessary dependency", case_right_size_gate_dependency),
    ("implementer cannot be the final validator", case_implementer_cannot_validate),
    ("repeated mistake triggers retrospective harness update", case_repeated_mistake_retrospective),
    ("package status without completion record fails", case_package_requires_completion_record),
    ("rejected independent review fails", case_rejected_review_fails),
    ("missing implementer fails", case_missing_implementer_fails),
    ("boolean validation/completion placeholders fail", case_boolean_placeholders_fail),
    ("malformed commands_run fails cleanly without crashing", case_malformed_commands_no_crash),
    ("shallow/nonexistent artifact placeholders fail", case_shallow_artifacts_fail),
    ("valid inline artifact objects pass", case_valid_inline_artifacts_pass),
    ("string artifact pointing at an existing file passes", case_existing_artifact_path_passes),
    ("repeated failure requires a durable harness update", case_repeated_failure_requires_harness_update),
    ("brief does not crash on an empty repo", case_brief_empty_repo),
    ("brief renders record, risks, and progress tail", case_brief_with_record_and_progress),
    ("brief --json returns valid structured output", case_brief_json_valid),
    ("brief surfaces run journal steps and suggests next step", case_brief_with_run_journal),
    ("schema accepts object acceptance criteria with proving_command (and strings)", case_schema_accepts_object_acceptance_criteria),
    ("optional run_metrics with non-negative numbers passes check-record", case_run_metrics_valid_passes),
    ("run_metrics with a string cost_usd fails check-record", case_run_metrics_string_cost_fails),
    ("verify --require-terminal blocks an unclosed loop (implement + dirty diff)", case_require_terminal_blocks_unclosed_loop),
    ("verify --require-terminal is a no-op at done status", case_require_terminal_noop_when_done),
    ("public docs state the canonical gate-case count (numbers-consistency lint)", case_doc_counts_match_canonical),
    ("bench --validate requires cost fields on live runs (exempts fixtures)", case_bench_validate_requires_cost_fields),
]


def main() -> int:
    failures = 0
    for name, fn in CASES:
        with tempfile.TemporaryDirectory() as td:
            try:
                ok, detail = fn(Path(td))
            except Exception as exc:  # noqa: BLE001 - eval harness surfaces any error
                ok, detail = False, f"exception: {exc!r}"
        status = PASS if ok else FAIL
        if not ok:
            failures += 1
        print(f"[{status}] {name}\n        {detail}")
    total = len(CASES)
    print(f"\n{total - failures}/{total} eval cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
