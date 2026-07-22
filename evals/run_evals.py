#!/usr/bin/env python3
"""Record-gate eval harness for the Coding Quality Loop.

These cases exercise the *runtime* record gates in `scripts/quality_loop.py`
(`verify-gates`, `check-record`, `diff-audit`) against constructed agent
records. They complement the record-based cases in `evals/cases/` (run with
`quality_loop.py eval-cases`), which feed a raw goal + record through the same
production gates (`detect_risk_floor` + `verify-gates`) — there is no separate
static classifier to drift from the shipping gate.

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

# Canonical count of offline CORE gate cases — COMPUTED, never hand-set. The
# old hand-bumped literal drifted from the real suites twice (116->121, then
# again in v6 review); canonical_gate_cases() now derives the total at runtime
# from the suites themselves: len(CASES) of each core suite module (behavioral
# = this file, memory, reality, routing, hook) + the count of static
# evals/cases/*.json files. The count-consistency lint
# (case_doc_counts_match_canonical) asserts every public doc agrees with the
# computed total. It EXCLUDES the opt-in control-plane add-on suite, derived
# the same way by control_addon_cases() and phrased "<n> add-on cases" in
# docs. Suite modules are imported lazily (inside the lint), so plain eval
# runs never pay for importing the sibling suites.
_CORE_SUITE_MODULES = (
    "run_memory_evals",
    "run_reality_evals",
    "run_routing_evals",
    "run_hook_evals",
)


def _suite_case_count(module_name: str) -> int:
    """len(CASES) of a sibling suite module, imported lazily from evals/."""
    import importlib

    evals_dir = str(ROOT / "evals")
    if evals_dir not in sys.path:
        sys.path.insert(0, evals_dir)
    return len(importlib.import_module(module_name).CASES)


def canonical_gate_cases() -> int:
    """The derived core gate-case total: static cases/*.json + every core
    suite's len(CASES). The single source of truth the doc lint checks."""
    static = len(list((ROOT / "evals" / "cases").glob("*.json")))
    return static + len(CASES) + sum(_suite_case_count(m) for m in _CORE_SUITE_MODULES)


def control_addon_cases() -> int:
    """The derived opt-in control-plane add-on case count."""
    return _suite_case_count("run_control_evals")

sys.path.insert(0, str(ROOT / "scripts"))
import quality_loop  # noqa: E402  (SECRET_PATTERNS reused by the untracked-secret case)

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
        # Medium+ requires provable criteria: an object AC whose proving_command
        # matches the base pass command (string ACs block at medium+ risk).
        acceptance_criteria=[{"criterion": "does the thing", "proving_command": "pytest"}],
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


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _git_repo_with_base(tmp: Path, name: str = "repo") -> Path:
    """A git repo with one 'base' commit of main.py — the shared starting
    point the diff-grounded cases previously each rebuilt verbatim."""
    repo = tmp / name
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "eval@example.com")
    _git(repo, "config", "user.name", "eval")
    (repo / "main.py").write_text("print('hi')\n")
    _git(repo, "add", "main.py")
    _git(repo, "commit", "-m", "base")
    return repo


def case_right_size_gate_dependency(tmp: Path) -> tuple[bool, str]:
    # Severity tiers (P1.4): dependency and migration edits are ADVISORY, not
    # blocking. They must surface in the audit's `advisory` list but exit 0, so a
    # benign lockfile bump or a legitimate migration does not fail the loop (and
    # does not block the git pre-commit hook). Only real correctness/safety
    # problems (leaked secret, weakened test) are blocking / exit 1.
    def advisory_of(out: str) -> list[str]:
        try:
            return json.loads(out).get("advisory", [])
        except json.JSONDecodeError:
            return []

    dep_repo = _git_repo_with_base(tmp, "dep")
    (dep_repo / "requirements.txt").write_text("leftpad==1.0.0\n")
    _git(dep_repo, "add", "requirements.txt")
    dep_code, dep_out, _ = run_cli("diff-audit", "--base", "HEAD", cwd=str(dep_repo))
    dep_ok = dep_code == 0 and any("dependency files changed" in a for a in advisory_of(dep_out))

    changelog_repo = _git_repo_with_base(tmp, "changelog")
    (changelog_repo / "CHANGELOG.md").write_text("## Changed\n\n- Document migration guidance.\n")
    _git(changelog_repo, "add", "CHANGELOG.md")
    changelog_code, changelog_out, _ = run_cli("diff-audit", "--base", "HEAD", cwd=str(changelog_repo))
    changelog_ok = changelog_code == 0 and "migration/schema-related" not in changelog_out

    migration_repo = _git_repo_with_base(tmp, "migration")
    migration_file = migration_repo / "db" / "migrate" / "001_add_users.sql"
    migration_file.parent.mkdir(parents=True)
    migration_file.write_text("alter table users add column nickname text;\n")
    _git(migration_repo, "add", str(migration_file.relative_to(migration_repo)))
    migration_code, migration_out, _ = run_cli("diff-audit", "--base", "HEAD", cwd=str(migration_repo))
    migration_ok = migration_code == 0 and any(
        "migration/schema-related files changed" in a for a in advisory_of(migration_out)
    )

    ok = dep_ok and changelog_ok and migration_ok
    return ok, (
        f"dependency(exit={dep_code},advisory={dep_ok}); "
        f"changelog(exit={changelog_code},clean={changelog_ok}); "
        f"migration(exit={migration_code},advisory={migration_ok})"
    )


def case_diff_audit_untracked_hygiene(tmp: Path) -> tuple[bool, str]:
    """P1.5/P1.6/P3.17 in one repo: loop scaffolding and caches are excluded from
    the untracked sweep, an unreadable untracked file is surfaced (not silently
    skipped), and an intentional `cql:` shortcut marker is counted — all advisory,
    exit 0."""
    import json as _json
    import os as _os
    import stat as _stat

    repo = _git_repo_with_base(tmp, "repo")

    # P1.5: scaffolding + caches are untracked but must be dropped from the sweep.
    (repo / ".quality-loop").mkdir()
    (repo / ".quality-loop" / "progress.md").write_text("notes\n")
    (repo / "__pycache__").mkdir()
    (repo / "__pycache__" / "x.pyc").write_text("bytecode\n")
    (repo / "agent-record.json").write_text('{"goal": "x"}\n')
    # A real new module stays in the audit (untracked but not scaffolding).
    (repo / "newmodule.py").write_text("x = 1\n")
    # P3.17: a tracked change carrying a `cql:` shortcut marker is counted.
    (repo / "main.py").write_text("print('hi')  # cql: linear scan; upgrade to index if slow\n")
    # P1.6: an unreadable untracked file must be surfaced, not silently skipped.
    unreadable = repo / "locked.py"
    unreadable.write_text("secret = 'x'\n")
    _os.chmod(unreadable, 0)

    code, out, _ = run_cli("diff-audit", "--base", "HEAD", cwd=str(repo))
    _os.chmod(unreadable, _stat.S_IRUSR | _stat.S_IWUSR)  # restore for cleanup
    try:
        advisory = _json.loads(out).get("advisory", [])
    except _json.JSONDecodeError:
        return False, f"non-json output (exit={code}): {out[:120]!r}"

    joined = " ".join(advisory)
    scaffolding_excluded = (
        ".quality-loop" not in joined
        and "__pycache__" not in joined
        and "agent-record.json" not in joined
    )
    module_included = "newmodule.py" in joined
    unreadable_surfaced = any("could not scan untracked file" in a and "locked.py" in a for a in advisory)
    marker_counted = any("shortcut marker" in a and "cql:" in a for a in advisory)

    ok = (
        code == 0
        and scaffolding_excluded
        and module_included
        and unreadable_surfaced
        and marker_counted
    )
    return ok, (
        f"exit={code}; scaffolding_excluded={scaffolding_excluded}; "
        f"module_included={module_included}; unreadable_surfaced={unreadable_surfaced}; "
        f"marker_counted={marker_counted}"
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
        ROOT / "references" / "philosophy.md",
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

    # One truth per thing (1.4d): acceptance criteria live ONLY in the record's
    # top-level list. A validation_contract with goal + evidence and NO
    # acceptance-criteria copy passes — the gate reads no copy inside the
    # artifact, so it must not demand one.
    no_dup = passing_medium(
        validation_contract={
            "goal": "Move invoice rounding to the summed total",
            "evidence": ["pytest billing/tests -> pass"],
        },
    )
    code_n, out_n = verify_gates(tmp, no_dup)
    ok = code == 0 and code_n == 0
    return ok, f"with_dup(exit={code}); no_dup_copy(exit={code_n}: {out_n.strip()!r})"


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
    repo = _git_repo_with_base(tmp, "repo")

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
    # A small, low-risk task ships on handoff evidence (a passing targeted check),
    # not a formal completion record. The runtime gate is the single source of
    # truth now that the parallel static classifier is gone.
    record = base_record(
        goal="rename a local helper for clarity",
        risk_tier="low",
        task_class="small",
        commands_run=[{"cmd": "pytest test_helper.py", "class": "unit", "result": "pass", "evidence": "3 passed"}],
        status="done",
    )
    code, output = verify_gates(tmp, record)
    ok = code == 0 and "completion_record" not in output
    return ok, f"runtime(exit={code}); output={output.strip()!r}"


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
    repo = _git_repo_with_base(tmp, name)
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


# Matches the headline phrasings only: "<n> cases", "<n> gate cases",
# "<n> eval cases", "<n> offline cases", "<n> offline gate/eval cases".
# Also catches "<n> core cases" — including URL-encoded ("<n>%20core%20cases")
# so a shields.io badge cannot drift invisibly — and "| **<n>** |" /
# "| <n> |" table cells, the two phrasings the v6 final review found the
# plain word-boundary regex could not see.
_COUNT_PATTERN = re.compile(
    r"(\d+)(?:\s+|%20)(?:offline(?:\s+|%20))?(?:gate(?:\s+|%20)|eval(?:\s+|%20)|core(?:\s+|%20))?cases\b",
    re.IGNORECASE,
)
_TABLE_CELL_PATTERN = re.compile(r"\|\s*\*{0,2}(\d+)\*{0,2}\s*\|")
# The add-on suite's own phrasing ("<n> add-on cases"), invisible to the
# core pattern above and vice versa.
_ADDON_PATTERN = re.compile(r"(\d+)(?:-case)?\s+add-on\s+(?:gate\s+|eval\s+)?cases?\b", re.IGNORECASE)
_HISTORICAL_LINE = re.compile(r"\bas of v\d", re.IGNORECASE)
# Only lint table cells inside the canonical "Total core gate cases" row —
# per-suite rows carry their own (varying) counts that are not the total.
_TOTAL_ROW = re.compile(r"total\s+core\s+gate\s+cases", re.IGNORECASE)
# The add-on suite's own table row ("| Control plane add-on … | 37 | …") — the
# v6.5.0 review found the phrase-only add-on lint let a stale table cell
# through; any table row naming the control-plane add-on must carry the
# derived add-on count in its numeric cell.
_ADDON_ROW = re.compile(r"control[- ]plane\s+add-on", re.IGNORECASE)
# Per-suite breakdown addends, e.g. "20 static", "54/54 hook". A right TOTAL
# with a wrong per-suite addend (a 53 that should be 54) slipped past the
# total-only lint twice; this catches the arithmetic itself (v6.2 review).
_BREAKDOWN_ADDEND = re.compile(
    r"(\d+)(?:/\d+)?\s+(static|behavioral|memory|reality|routing|hook)\b", re.IGNORECASE)


def _doc_count_mismatches(
    text: str, rel: str, allow_trigger: bool, canonical: int, addon: int,
    suite_counts: dict[str, int] | None = None,
) -> list[str]:
    """Count-lint one doc's text against the derived canonical/add-on totals.

    Module-level (not a closure) so the derived-count eval case can feed it a
    synthetic doc and prove a wrong number is still caught. When ``suite_counts``
    is supplied, per-suite breakdown addends ("... 30 routing + 54 hook") are
    also checked against the real per-suite counts and their arithmetic — a
    right TOTAL with a wrong addend slipped past the total-only lint twice.
    """
    mismatches: list[str] = []
    # Plain counts are scanned on a whitespace-flattened view so a number and
    # its "gate cases" phrase split across a hard-wrapped line are still one
    # mention (the v6.5.0 round-5 review found a wrapped '249\noffline gate
    # cases' the per-line scan missed). The "as of vX.Y" historical exemption
    # is scoped to the match's own sentence CLAUSE — a fixed window let a
    # historical clause mask a stale current count right next to it (round 6).
    def _clause(flat_text: str, start: int, end: int) -> str:
        cs = flat_text.rfind(". ", 0, start)
        cs = 0 if cs == -1 else cs + 2
        ce = flat_text.find(". ", end)
        ce = len(flat_text) if ce == -1 else ce + 1
        return flat_text[cs:ce]

    flat = _ADDON_PATTERN.sub("", " ".join(text.split()))
    for m in _COUNT_PATTERN.finditer(flat):
        if _HISTORICAL_LINE.search(_clause(flat, m.start(), m.end())):
            continue
        n = int(m.group(1))
        if allow_trigger and n == 10:
            continue
        if n != canonical:
            mismatches.append(f"{rel}: {m.group(0)!r} != {canonical}")
    flat_addon = " ".join(text.split())
    for m in _ADDON_PATTERN.finditer(flat_addon):
        if _HISTORICAL_LINE.search(_clause(flat_addon, m.start(), m.end())):
            continue
        if int(m.group(1)) != addon:
            mismatches.append(f"{rel}: {m.group(0)!r} != {addon} (add-on)")
    for line in text.splitlines():
        if _HISTORICAL_LINE.search(line):
            continue  # "as of vX.Y" marks a historical count; exempt
        if _TOTAL_ROW.search(line):
            for m in _TABLE_CELL_PATTERN.finditer(line):
                if int(m.group(1)) != canonical:
                    mismatches.append(f"{rel}: total-row cell {m.group(0)!r} != {canonical}")
        elif _ADDON_ROW.search(line) or "run_control_evals.py" in line:
            for m in _TABLE_CELL_PATTERN.finditer(line):
                if int(m.group(1)) != addon:
                    mismatches.append(f"{rel}: add-on row cell {m.group(0)!r} != {addon}")
        elif suite_counts and line.lstrip().startswith("|"):
            # A table row naming a suite's own runner must carry that suite's
            # derived count in its numeric cell (round 6: the Behavioral row's
            # parenthetical dodged a rename-style fix and the lint was blind
            # to per-suite rows).
            runner_map = {
                "run_evals.py": "behavioral", "run_memory_evals.py": "memory",
                "run_reality_evals.py": "reality", "run_routing_evals.py": "routing",
                "run_hook_evals.py": "hook", "eval-cases evals/cases": "static",
            }
            for needle, suite in runner_map.items():
                if needle in line and not any(
                        other in line for other in runner_map if
                        other != needle and needle in other):
                    real = suite_counts.get(suite)
                    for m in _TABLE_CELL_PATTERN.finditer(line):
                        if real is not None and int(m.group(1)) != real:
                            mismatches.append(
                                f"{rel}: {suite} suite row cell {m.group(0)!r} != {real}")
                    break  # one runner per row; first unambiguous match wins
        if suite_counts:
            addends = _BREAKDOWN_ADDEND.findall(line)
            # Every addend is checked against its real suite count wherever it
            # appears. The SUM is only checked when all six suite names are on
            # one line (a complete breakdown) — a breakdown that wraps across
            # lines would otherwise sum a partial line to a false total.
            names_on_line = {name.lower() for _, name in addends}
            for num, name in addends:
                real = suite_counts.get(name.lower())
                if real is not None and int(num) != real:
                    mismatches.append(f"{rel}: breakdown addend '{num} {name}' != {real}")
            if names_on_line >= set(suite_counts):
                total = sum(int(num) for num, _ in addends)
                if total != canonical:
                    mismatches.append(f"{rel}: breakdown sums to {total}, not {canonical}")
    return mismatches


def case_release_version_parity(tmp: Path) -> tuple[bool, str]:
    """Release surfaces share ONE version: npm package.json, SKILL.md
    frontmatter, the README version badge, and the shipped GitHub example's
    action ref. Version drift is a repeated field mistake (the schema-version
    pin drifted before v6.1.0; the README badge and GitHub example shipped
    stale into the v6.5.0 review) — so parity is a gate, not a checklist."""
    pkg = json.loads((ROOT / "packages" / "npm" / "package.json").read_text(encoding="utf-8"))["version"]
    skill_m = re.search(r'^\s*version:\s*"([^"]+)"',
                        (ROOT / "SKILL.md").read_text(encoding="utf-8"), re.MULTILINE)
    badge_m = re.search(r"badge/version-([0-9.]+)-",
                        (ROOT / "README.md").read_text(encoding="utf-8"))
    gh_m = re.search(r"coding-quality-loop@v([0-9.]+)",
                     (ROOT / "hosts" / "github" / "quality-loop-example.yml").read_text(encoding="utf-8"))
    vals = {"npm": pkg, "skill": skill_m.group(1) if skill_m else None,
            "readme_badge": badge_m.group(1) if badge_m else None,
            "gh_example": gh_m.group(1) if gh_m else None}
    ok = all(v == pkg for v in vals.values())
    return ok, f"versions={vals}"


def case_doc_counts_match_canonical(tmp: Path) -> tuple[bool, str]:
    # Numbers-consistency lint (critical review R2 + improvement plan 2.5): every
    # public doc that states an offline gate-case count must state the DERIVED
    # canonical_gate_cases() total (core suites), and every "<n> add-on cases"
    # mention must state control_addon_cases() (the opt-in control-plane suite).
    # Guards against the 116->121 drift the review flagged. Two deliberate
    # exemptions: the CHANGELOG top entry may reference the historical 10-case
    # trigger fixture (deleted in v6.1.0), and any LINE annotated "as of vX.Y"
    # is historical by declaration — the lint must never rewrite history again
    # (it once overwrote ROADMAP's v3.0-era count with the then-current one).
    docs = [
        ROOT / "README.md",
        ROOT / "ROADMAP.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "docs" / "README.md",
        ROOT / "docs" / "comparison.md",
        ROOT / "docs" / "launch-kit.md",
        ROOT / "docs" / "control-plane.md",
        ROOT / "docs" / "images" / "src" / "README.md",
        ROOT / "evals" / "README.md",
    ]
    # CHANGELOG holds historical counts by design; only its TOP entry must be
    # current. Dated snapshot docs (docs/critical-review-*, docs/spec-*,
    # docs/improvement-plan-*) are deliberately excluded: they describe the
    # tree they audited.
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    top_entry = re.split(r"\n## ", changelog)[1] if "\n## " in changelog else changelog
    canonical = canonical_gate_cases()
    addon = control_addon_cases()
    suite_counts = {
        "static": len(list((ROOT / "evals" / "cases").glob("*.json"))),
        "behavioral": len(CASES),
        "memory": _suite_case_count("run_memory_evals"),
        "reality": _suite_case_count("run_reality_evals"),
        "routing": _suite_case_count("run_routing_evals"),
        "hook": _suite_case_count("run_hook_evals"),
    }
    mismatches: list[str] = []

    for doc in docs:
        rel = str(doc.relative_to(ROOT))
        if not doc.exists():
            mismatches.append(f"{rel}: MISSING")
            continue
        mismatches.extend(
            _doc_count_mismatches(
                doc.read_text(encoding="utf-8"), rel, False, canonical, addon, suite_counts
            )
        )
    mismatches.extend(
        _doc_count_mismatches(
            top_entry, "CHANGELOG.md (top entry)", True, canonical, addon, suite_counts)
    )
    # Historical entries are never rewritten to current counts — but their
    # arithmetic must stay internally consistent: when an old entry states a
    # complete six-suite breakdown with its own total, the addends must sum
    # to THAT total. (The v6.5.0 round-3 review caught a global sed silently
    # corrupting v6.4.0's historical breakdown; wrapped lines are joined so
    # multi-line "Suites:" breakdowns are checked too.)
    for i, entry in enumerate(re.split(r"\n## ", changelog)[2:], start=2):
        flat = " ".join(entry.split())
        for span in re.finditer(
                r"\b\d+\s+static\b[^=]{0,200}?=\s*\*\*(\d+)(?:\s+core)?\s+gate\s+cases\*\*",
                flat):
            addends = _BREAKDOWN_ADDEND.findall(span.group(0))
            if {n.lower() for _, n in addends} >= set(suite_counts):
                total = sum(int(num) for num, _ in addends)
                if total != int(span.group(1)):
                    mismatches.append(
                        f"CHANGELOG.md (historical entry #{i}): breakdown sums to "
                        f"{total}, not its own stated {span.group(1)}")

    ok = not mismatches
    detail = f"canonical={canonical}; addon={addon}"
    return ok, (f"all docs match {detail}" if ok else f"{detail}; mismatches={mismatches}")


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
    live_fails = bad_code == 1 and "MISSING-COST" in bad_out and "MISSING-PROVENANCE" in bad_out

    # v6 validator hardening (codex review): an empty-runs document fails
    # instead of passing as "0 runs"; a live document whose rows self-label
    # mode=fixture to dodge cost enforcement fails on mode consistency; a
    # fully instrumented live row passes; the COMMITTED fixture smoke passes.
    empty = tmp / "empty-runs.json"
    empty.write_text(json.dumps({"mode": "live", "runs": []}), encoding="utf-8")
    empty_code, empty_out = run("--validate", str(empty))
    empty_fails = empty_code == 1 and "empty 'runs'" in empty_out

    dodge = tmp / "live-fixture-dodge.json"
    dodge.write_text(
        json.dumps({"mode": "live", "runs": [
            {"task_id": "webapp", "arm": "full", "seed": 0, "mode": "fixture",
             "host": "claude-code 3.1.0", "model": "m", "skill_version": "6.0.0",
             "prompt_file": "SPEC.md",
             "tokens_in": 0, "tokens_out": 0, "duration_sec": 0.0}]}),
        encoding="utf-8",
    )
    dodge_code, dodge_out = run("--validate", str(dodge))
    dodge_fails = dodge_code == 1 and "MODE-MISMATCH" in dodge_out

    good_live = tmp / "live-good.json"
    good_live.write_text(
        json.dumps({"mode": "live", "runs": [
            {"task_id": "webapp", "arm": "full", "seed": 0, "mode": "live",
             "host": "claude-code 3.1.0", "model": "m", "skill_version": "6.0.0",
             "prompt_file": "SPEC.md",
             "tokens_in": 1200, "tokens_out": 400, "duration_sec": 33.5}]}),
        encoding="utf-8",
    )
    good_code, good_out = run("--validate", str(good_live))
    good_live_ok = good_code == 0 and "OK:" in good_out

    committed = ROOT / "bench" / "results" / "fixture-smoke-2026-07-20.json"
    com_code, com_out = run("--validate", str(committed))
    committed_ok = com_code == 0 and "OK:" in com_out

    ok = fixture_ok and live_fails and empty_fails and dodge_fails and good_live_ok and committed_ok
    return ok, (f"fixture_validates={fixture_ok}; live_missing_cost_fails={live_fails}; "
                f"empty_runs_fails={empty_fails}; fixture_dodge_fails={dodge_fails}; "
                f"instrumented_live_passes={good_live_ok}; committed_fixture_passes={committed_ok}")


def case_models_used_shape(tmp: Path) -> tuple[bool, str]:
    """Optional models_used (v4.2 routing evidence) validates when present."""
    good = base_record(models_used=[
        {"role": "implementer", "host": "droid", "model": "glm-5.2-fast",
         "thinking": "high", "attempts": 2, "cost_usd": 0.42},
        {"role": "fresh_reviewer", "host": "codex", "model": "gpt-5.6-sol"},
    ])
    code_good, out_good = check_record(tmp, good)

    bad = base_record(models_used=[
        {"host": "droid"},                                # missing role + model
        {"role": "implementer", "model": "x", "attempts": 0},   # attempts < 1
        {"role": "implementer", "model": "x", "cost_usd": -1},  # negative cost
    ])
    code_bad, out_bad = check_record(tmp, bad)
    flagged = (
        code_bad == 1
        and "models_used[0].role" in out_bad
        and "models_used[1].attempts" in out_bad
        and "models_used[2].cost_usd" in out_bad
    )
    ok = code_good == 0 and flagged
    return ok, f"good(exit={code_good}); bad(exit={code_bad},flagged={flagged})"


def case_escalations_shape(tmp: Path) -> tuple[bool, str]:
    """Optional escalations entries validate: trigger is the enum-of-one
    'verified_failure', failing_commands is non-empty, from != to."""
    good = base_record(escalations=[
        {"step": "IMPLEMENT_SLICE", "from_model": "glm-5.2-fast", "to_model": "claude-opus-4-8",
         "trigger": "verified_failure", "failing_commands": ["pytest -x"], "attempts": 2},
    ])
    code_good, out_good = check_record(tmp, good)

    bad = base_record(escalations=[
        {"step": "IMPLEMENT_SLICE", "from_model": "a", "to_model": "b",
         "trigger": "looked_stuck", "failing_commands": ["x"]},
        {"step": "IMPLEMENT_SLICE", "from_model": "a", "to_model": "a",
         "trigger": "verified_failure", "failing_commands": ["x"]},
        {"step": "IMPLEMENT_SLICE", "from_model": "a", "to_model": "b",
         "trigger": "verified_failure", "failing_commands": []},
    ])
    code_bad, out_bad = check_record(tmp, bad)
    flagged = (
        code_bad == 1
        and "escalations[0].trigger" in out_bad
        and "from_model and to_model must differ" in out_bad
        and "escalations[2].failing_commands" in out_bad
    )
    ok = code_good == 0 and flagged
    return ok, f"good(exit={code_good}); bad(exit={code_bad},flagged={flagged})"


def case_escalation_requires_failing_evidence(tmp: Path) -> tuple[bool, str]:
    """verify-gates: an escalation must cite a commands_run entry with
    result=fail; citing a passing or absent command is self-report, not
    evidence."""
    esc = {
        "step": "IMPLEMENT_SLICE", "from_model": "glm-5.2-fast",
        "to_model": "claude-opus-4-8", "trigger": "verified_failure",
        "failing_commands": ["pytest -x tests/test_auth.py"], "attempts": 2,
    }
    cmds_with_red_green = [
        {"cmd": "pytest -x tests/test_auth.py", "class": "unit", "result": "fail",
         "evidence": "2 failed"},
        {"cmd": "pytest -x tests/test_auth.py", "class": "unit", "result": "pass",
         "evidence": "12 passed"},
    ]
    legit = base_record(escalations=[dict(esc)], commands_run=list(cmds_with_red_green))
    code1, out1 = verify_gates(tmp, legit)
    legit_clean = "self-report escalation" not in out1

    unmatched = base_record(
        escalations=[dict(esc)],
        commands_run=[{"cmd": "pytest other", "class": "unit", "result": "pass", "evidence": "ok"}],
    )
    code2, out2 = verify_gates(tmp, unmatched)
    unmatched_flagged = "self-report escalation is not evidence" in out2 and "claude-opus-4-8" in out2

    cited_but_passing = base_record(
        escalations=[dict(esc)],
        commands_run=[{"cmd": "pytest -x tests/test_auth.py", "class": "unit", "result": "pass", "evidence": "ok"}],
    )
    code3, out3 = verify_gates(tmp, cited_but_passing)
    passing_flagged = "self-report escalation is not evidence" in out3

    # A bare {"result": "fail"} row with no evidence handle is free to
    # fabricate; it cannot back an escalation.
    unevidenced_fail = base_record(
        escalations=[dict(esc)],
        commands_run=[
            {"cmd": "pytest -x tests/test_auth.py", "class": "unit", "result": "fail"},
            {"cmd": "pytest -x tests/test_auth.py", "class": "unit", "result": "pass", "evidence": "12 passed"},
        ],
    )
    code4, out4 = verify_gates(tmp, unevidenced_fail)
    unevidenced_flagged = "self-report escalation is not evidence" in out4

    ok = legit_clean and unmatched_flagged and passing_flagged and unevidenced_flagged
    return ok, (
        f"legit_clean={legit_clean}; unmatched_flagged={unmatched_flagged}; "
        f"passing_cite_flagged={passing_flagged}; unevidenced_fail_flagged={unevidenced_flagged}"
    )


def case_resolved_failures_dont_block(tmp: Path) -> tuple[bool, str]:
    """A fail entry superseded by a later pass of the same command (the honest
    RED->GREEN shape an escalation leaves behind) is resolved, not outstanding;
    an unsuperseded fail still blocks."""
    resolved = base_record(commands_run=[
        {"cmd": "pytest -x", "class": "unit", "result": "fail", "evidence": "1 failed"},
        {"cmd": "pytest -x", "class": "unit", "result": "pass", "evidence": "12 passed"},
    ])
    code1, out1 = verify_gates(tmp, resolved)
    resolved_clean = "command(s) failed" not in out1

    outstanding = base_record(commands_run=[
        {"cmd": "pytest -x", "class": "unit", "result": "fail", "evidence": "1 failed"},
        {"cmd": "mypy .", "class": "types", "result": "pass", "evidence": "clean"},
    ])
    code2, out2 = verify_gates(tmp, outstanding)
    outstanding_flagged = "1 verification command(s) failed" in out2

    # Two entries that both omit `cmd` are not "the same command": None == None
    # must never excuse a failure.
    cmdless = base_record(commands_run=[
        {"class": "unit", "result": "fail", "evidence": "1 failed"},
        {"class": "unit", "result": "pass", "evidence": "ok"},
    ])
    code3, out3 = verify_gates(tmp, cmdless)
    cmdless_flagged = "verification command(s) failed" in out3

    ok = resolved_clean and outstanding_flagged and cmdless_flagged
    return ok, (
        f"resolved_clean={resolved_clean}; outstanding_flagged={outstanding_flagged}; "
        f"cmdless_not_excused={cmdless_flagged}"
    )


def case_string_acs_blocked_at_medium_not_low(tmp: Path) -> tuple[bool, str]:
    """String ACs are unprovable at medium+ (blocking, with the object shape
    named in the fix); the same string ACs stay valid at low risk."""
    medium = passing_medium(acceptance_criteria=["does the thing"])
    code_m, out_m = verify_gates(tmp, medium)
    medium_flagged = (
        code_m == 1
        and "has no proving_command" in out_m
        and "proving_command" in out_m
        and "error:" in out_m
    )

    low = base_record(
        risk_tier="low",
        task_class="tiny",
        acceptance_criteria=["does the thing"],
        commands_run=[{"cmd": "pytest", "class": "unit", "result": "pass", "evidence": "ok"}],
        status="done",
    )
    code_l, out_l = verify_gates(tmp, low)
    low_clean = code_l == 0 and "proving_command" not in out_l

    ok = medium_flagged and low_clean
    return ok, f"medium(exit={code_m},flagged={medium_flagged}); low(exit={code_l},clean={low_clean})"


def case_shared_proving_command_warns(tmp: Path) -> tuple[bool, str]:
    """>=3 ACs sharing one identical proving_command draws an advisory note
    (never blocking); distinct per-criterion commands stay silent."""
    shared = passing_medium(
        acceptance_criteria=[
            {"criterion": f"criterion {i}", "proving_command": "pytest"} for i in range(4)
        ],
    )
    code_s, out_s = verify_gates(tmp, shared)
    warned = code_s == 0 and "share one proving_command" in out_s and "note:" in out_s

    distinct = passing_medium(
        acceptance_criteria=[
            {"criterion": "a", "proving_command": "pytest"},
            {"criterion": "b", "proving_command": "mypy ."},
        ],
        commands_run=[
            {"cmd": "pytest", "class": "unit", "result": "pass", "evidence": "12 passed"},
            {"cmd": "mypy .", "class": "typecheck", "result": "pass", "evidence": "clean"},
        ],
    )
    code_d, out_d = verify_gates(tmp, distinct)
    silent = code_d == 0 and "share one proving_command" not in out_d

    ok = warned and silent
    return ok, f"shared(exit={code_s},warned={warned}); distinct(exit={code_d},silent={silent})"


def case_new_exec_classes_count(tmp: Path) -> tuple[bool, str]:
    """e2e/security/format/migration_dry_run passes count as executable
    evidence for the medium 'relevant executable check' rule."""
    results = []
    for cls in ("e2e", "security", "format", "migration_dry_run"):
        record = passing_medium(
            acceptance_criteria=[{"criterion": "does the thing", "proving_command": f"run-{cls}"}],
            commands_run=[{"cmd": f"run-{cls}", "class": cls, "result": "pass", "evidence": "ok"}],
        )
        code, output = verify_gates(tmp, record)
        results.append(code == 0 and "executable check" not in output)
    ok = all(results)
    return ok, f"clean={results} for e2e/security/format/migration_dry_run"


def case_blocking_findings_print_as_error(tmp: Path) -> tuple[bool, str]:
    """Blocking verify-gates findings print with the error: prefix, not
    warning: (agents read warning-labeled blockers as ignorable)."""
    record = passing_medium(implementer=None)
    code, output = verify_gates(tmp, record)
    ok = code == 1 and "error: " in output and "warning: " not in output
    return ok, f"exit={code}; error_prefix={'error: ' in output}; warning_prefix={'warning: ' in output}"


def case_v41_record_fixture_passes(tmp: Path) -> tuple[bool, str]:
    """The archived v4.1.0 dogfood record (predates models_used/escalations)
    still passes check-record: the v4.2 fields are strictly additive."""
    fixture = ROOT / "docs" / "records" / "v4.1.0-agent-record.json"
    if not fixture.is_file():
        return False, f"fixture missing: {fixture}"
    code, out, err = run_cli("check-record", str(fixture))
    ok = code == 0
    return ok, f"exit={code}; {(out + err).strip()!r}"


def case_all_archived_records_pass_check(tmp: Path) -> tuple[bool, str]:
    """Every archived completion record under docs/records/ must pass
    check-record. An invalid archived record (an unrecognized command class, a
    non-array models_used, a missing minimality reason) fails CI from here on,
    so the release history cannot silently rot. Generalizes the v4.1.0 fixture
    pin to the whole archive directory."""
    records_dir = ROOT / "docs" / "records"
    files = sorted(records_dir.glob("*.json")) if records_dir.is_dir() else []
    if not files:
        return False, f"no archived records found under {records_dir}"
    problems = []
    for path in files:
        code, out, err = run_cli("check-record", str(path))
        if code != 0:
            problems.append(f"{path.name}: exit={code} {(out + err).strip()!r}")
    ok = not problems
    return ok, (f"{len(files)} archived record(s) checked; "
                + ("all pass" if ok else "; ".join(problems)))


def case_reviewer_contract_surfaces_agree(tmp: Path) -> tuple[bool, str]:
    """Drift lint: the reviewer contract (verdict enum + ran_checks) must appear
    consistently in the canonical prompt card, the security prompt card, the two
    .claude agents, the two droid copies, and the record schema — so the
    surfaces cannot silently diverge again."""
    verdicts = ("approve", "request_changes", "needs_discussion", "reject")
    md_surfaces = [
        ROOT / "assets" / "prompts" / "reviewer.md",
        ROOT / "assets" / "prompts" / "security-reviewer.md",
        ROOT / ".claude" / "agents" / "quality-loop-reviewer.md",
        ROOT / ".claude" / "agents" / "quality-loop-security-reviewer.md",
        ROOT / "examples" / "droid" / ".factory" / "droids" / "quality-loop-reviewer.md",
        ROOT / "examples" / "droid" / ".factory" / "droids" / "quality-loop-security-reviewer.md",
        # The surface that actually drifted in v6.0.x (shipped a stale 3-value
        # spaced enum no gate accepts) — pinned so it cannot recur silently.
        ROOT / "references" / "reviewer-checklists.md",
    ]
    problems = []
    for path in md_surfaces:
        rel = path.relative_to(ROOT)
        if not path.is_file():
            problems.append(f"{rel}: MISSING")
            continue
        text = path.read_text(encoding="utf-8")
        for verdict in verdicts:
            if verdict not in text:
                problems.append(f"{rel}: verdict {verdict!r} absent")
        if "ran_checks" not in text:
            problems.append(f"{rel}: ran_checks absent")
        # Negative check with teeth: presence alone let the stale spaced
        # 3-value enum (`approve | request changes | needs discussion`) ship
        # alongside the correct one. Reject the known-bad spaced forms so a
        # surface cannot carry a contradictory enum the machine rejects.
        for stale in ("request changes", "needs discussion"):
            if re.search(r"\b" + stale.replace(" ", r"\s+") + r"\b", text):
                problems.append(f"{rel}: stale spaced verdict {stale!r} present (use underscored enum)")

    schema = json.loads((ROOT / "assets" / "agent-record.schema.json").read_text(encoding="utf-8"))
    for key in ("independent_review", "security_review"):
        props = schema["properties"][key]["properties"]
        enum = props.get("verdict", {}).get("enum")
        if enum != list(verdicts):
            problems.append(f"schema.{key}.verdict enum is {enum!r}, want {list(verdicts)!r}")
        if props.get("ran_checks", {}).get("type") != "boolean":
            problems.append(f"schema.{key}.ran_checks missing or not boolean")
    reason = schema["properties"]["commands_run"]["items"]["properties"]
    if "reason" not in reason or "rationale" not in reason:
        problems.append("schema.commands_run items missing reason/rationale (blocked-row escape hatch)")

    ok = not problems
    return ok, ("all surfaces agree" if ok else f"drift={problems}")


def case_paper_trail_is_four_artifacts(tmp: Path) -> tuple[bool, str]:
    """The medium paper trail is exactly contract / plan / completion record /
    progress (plus the context map): the merged contract exists, the folded
    standalone templates stay deleted, and the completion-record template is a
    blank current-lifecycle template, not the stale filled v2.4.0 record."""
    assets = ROOT / "assets"
    must_exist = ["contract.md", "plan.md", "completion-record.md", "progress.md", "context-map.md"]
    must_not_exist = [
        "task-contract-template.md",
        "validation-contract.md",
        "pr-summary-template.md",
        "decision-log.md",
        "execution-log.md",
    ]
    problems = []
    for name in must_exist:
        if not (assets / name).is_file():
            problems.append(f"assets/{name}: MISSING")
    for name in must_not_exist:
        if (assets / name).exists():
            problems.append(f"assets/{name}: should be deleted (folded into the 4-artifact trail)")

    contract = (assets / "contract.md").read_text(encoding="utf-8") if (assets / "contract.md").is_file() else ""
    if "proving" not in contract.lower():
        problems.append("assets/contract.md: no per-criterion proving-command pairing")

    record = (assets / "completion-record.md").read_text(encoding="utf-8") if (assets / "completion-record.md").is_file() else ""
    for stale in ("context-check", "verify-phases", "trace-audit", "archive/v240"):
        if stale in record:
            problems.append(f"assets/completion-record.md: stale reference {stale!r}")
    for section in ("Goal", "Files Changed", "Evidence", "Rollback", "Follow-ups"):
        if section not in record:
            problems.append(f"assets/completion-record.md: missing section {section!r}")

    ok = not problems
    return ok, ("4-artifact trail intact" if ok else f"problems={problems}")


def case_ran_checks_warns_not_fails(tmp: Path) -> tuple[bool, str]:
    """make-ran-checks-real: at medium+ an APPROVING independent_review without
    ran_checks: true draws an advisory note (never blocking); the same review
    with ran_checks: true stays silent."""
    without = passing_medium()  # its independent_review omits ran_checks
    code_w, out_w = verify_gates(tmp, without)
    warned = code_w == 0 and "ran_checks" in out_w and "note:" in out_w and "error:" not in out_w

    with_flag = passing_medium(
        independent_review={
            "reviewer": "agent-b",
            "verdict": "approve",
            "fresh_context": True,
            "patched": False,
            "findings": [],
            "ran_checks": True,
        },
    )
    code_f, out_f = verify_gates(tmp, with_flag)
    silent = code_f == 0 and "ran_checks" not in out_f

    ok = warned and silent
    return ok, f"without(exit={code_w},warned={warned}); with(exit={code_f},silent={silent})"


def case_brief_caps_over_budget_lesson(tmp: Path) -> tuple[bool, str]:
    """recall_pool always admits the first (highest-scoring) lesson even when
    it alone exceeds the recall budget; brief must cap the rendered digest in
    both text and --json output instead of emitting the full lesson body."""
    qdir = tmp / ".quality-loop"
    (qdir / "memory").mkdir(parents=True)
    (qdir / "agent-record.json").write_text(json.dumps({
        "task_id": "t-b", "goal": "billing rounding overflow cleanup", "status": "review",
        "risk_tier": "medium", "open_risks": [], "review_findings": [], "task_class": "medium",
    }), encoding="utf-8")
    lesson = {
        "id": "l1", "created": "2026-01-01", "source_task_id": "t0", "kind": "gotcha",
        "risk_tier": "medium", "scope_globs": [], "keywords": ["billing", "rounding", "overflow"],
        "lesson": "billing rounding overflow " + ("padword " * 400) + "ZZZENDMARKER",
        "hits": 0,
    }
    (qdir / "memory" / "lessons.jsonl").write_text(json.dumps(lesson) + "\n", encoding="utf-8")

    code_t, out_t, _ = run_cli("brief", "--cwd", str(tmp), "--budget", "200")
    text_capped = code_t == 0 and "ZZZENDMARKER" not in out_t and "recalled)" in out_t

    code_j, out_j, _ = run_cli("brief", "--cwd", str(tmp), "--budget", "200", "--json")
    try:
        data = json.loads(out_j)
        json_capped = (
            code_j == 0
            and data.get("lessons_recalled", 0) >= 1
            and "ZZZENDMARKER" not in data.get("lessons_digest", "")
            and len(data.get("lessons_digest", "")) <= 200
        )
    except json.JSONDecodeError:
        json_capped = False

    ok = text_capped and json_capped
    return ok, f"text(exit={code_t},capped={text_capped}); json(exit={code_j},capped={json_capped})"


EXAMPLE_CONFIG = ROOT / "assets" / "quality-loop.config.example.json"


def case_check_config_core_control_plane_shape(tmp: Path) -> tuple[bool, str]:
    """Config validation must not depend on the opt-in control-plane add-on:
    with quality_loop_control.py absent, a malformed control_plane block (even
    a disabled one) still fails the core shape check, and a valid disabled
    block still passes."""
    partial = tmp / "partial"
    partial.mkdir()
    src = ROOT / "scripts"
    for name in (
        "quality_loop.py", "quality_loop_core.py", "quality_loop_memory.py",
        "quality_loop_reality.py", "quality_loop_routing.py",
    ):
        (partial / name).write_text((src / name).read_text(encoding="utf-8"), encoding="utf-8")
    base = json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))

    def check(control) -> tuple[int, str]:
        cfg = dict(base)
        if control is not None:
            cfg["control_plane"] = control
        cfg_path = tmp / "config.json"
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(partial / "quality_loop.py"), "check-config", str(cfg_path)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(tmp), check=False,
        )
        return proc.returncode, proc.stdout + proc.stderr

    code_p, out_p = check({"enabled": False, "port": "8080"})
    bad_port_fails = code_p == 1 and "control_plane.port must be an integer" in out_p

    # A disabled block with an out-of-range port / negative retention / non-bool
    # autostart must still fail in core, not slip through because the add-on's
    # full validator is absent.
    code_r, out_r = check({"enabled": False, "port": 99999, "retention_days": -1, "autostart": "yes"})
    range_fails = code_r == 1 and all(s in out_r for s in (
        "control_plane.port must be between 1 and 65535",
        "control_plane.retention_days must be >= 0",
        "control_plane.autostart must be a boolean",
    ))

    code_n, out_n = check("on")
    non_dict_fails = code_n == 1 and "control_plane must be an object" in out_n

    code_v, out_v = check(None)  # the example's own valid disabled block
    valid_passes = code_v == 0 and "config ok" in out_v

    ok = bad_port_fails and range_fails and non_dict_fails and valid_passes
    return ok, (
        f"bad_port(exit={code_p},flagged={bad_port_fails}); "
        f"range(exit={code_r},flagged={range_fails}); "
        f"non_dict(exit={code_n},flagged={non_dict_fails}); valid(exit={code_v})"
    )


def case_config_schema_version_pinned(tmp: Path) -> tuple[bool, str]:
    """1.3: CONFIG_SCHEMA_VERSION is the config SCHEMA lineage version (the
    shape last changed in release 5.1.0), not the package release version.
    Three-way pin — engine constant == schema const == example config version —
    so the silent drift that hid behind the old EXPECTED_CONFIG_VERSION name
    (nothing read it; the rejection text claimed a version unification that was
    false) cannot recur. Also pins the rejection text's honesty."""
    example = json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    schema = json.loads(
        (ROOT / "assets" / "quality-loop.config.schema.json").read_text(encoding="utf-8")
    )
    engine = quality_loop.CONFIG_SCHEMA_VERSION
    schema_const = schema["properties"]["version"].get("const")
    pinned = (
        isinstance(engine, str) and engine
        and example.get("version") == engine == schema_const
    )

    bad = dict(example)
    bad["version"] = "9.9.9"
    bad_path = tmp / "bad-version.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    code, out, err = run_cli("check-config", str(bad_path))
    rejected_honestly = (
        code == 1
        and "does not track the package release version" in err
        and "share one version" not in (out + err)
    )
    ok = bool(pinned) and rejected_honestly
    return ok, (
        f"engine={engine!r}; schema_const={schema_const!r}; example={example.get('version')!r}; "
        f"pinned={bool(pinned)}; rejected_honestly={rejected_honestly}(exit={code})"
    )


def case_check_config_always_prints_heterogeneity(tmp: Path) -> tuple[bool, str]:
    """check-config always emits a heterogeneity_status line — including the
    no-model_routing SKIPPED case — so a passing config without routing is
    visibly unverified rather than silently status-free."""
    cfg = json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    cfg.pop("model_routing", None)
    cfg_path = tmp / "config.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    code, out, err = run_cli("check-config", str(cfg_path))
    skipped_line = "reviewer heterogeneity: SKIPPED" in out and "model_routing not configured" in out
    ok = code == 0 and skipped_line and "config ok" in out
    return ok, f"exit={code}; skipped_line={skipped_line}; out={out.strip()[:160]!r}"


def case_check_config_gate_config_only(tmp: Path) -> tuple[bool, str]:
    """v6.3: a quality-loop.config.json with NO orchestration sections
    (profiles/steps) but the gate-config surface (base / tests / high_risk_paths
    / protect_harness) validates the gate keys and exits 0. Malformed gate keys
    still fail; a full config keeps the full validation path (heterogeneity
    line, not the gate-config note). Since v6.5.0 this repo's own config is the
    FULL orchestration shape with activated model_routing — it must take the
    full path and report cross-family review as verified."""
    # (a) A gate-config-only fixture passes and takes the gate-config path;
    #     this repo's own config (full shape since v6.5.0) takes the full path
    #     with heterogeneity verified.
    gate_only = {"version": quality_loop.CONFIG_SCHEMA_VERSION,
                 "tests": {"path_markers": ["evals/cases/"]},
                 "high_risk_paths": [], "protect_harness": False}
    gate_path = tmp / "gate-only.json"
    gate_path.write_text(json.dumps(gate_only), encoding="utf-8")
    code_g, out_g, _ = run_cli("check-config", str(gate_path))
    repo_cfg = ROOT / "quality-loop.config.json"
    code_r, out_r, _ = run_cli("check-config", str(repo_cfg))
    repo_ok = (
        code_g == 0
        and "gate-config (no orchestration sections)" in out_g
        and "config ok" in out_g
        and "reviewer heterogeneity" not in out_g  # orchestration checks skipped
        and code_r == 0
        and "config ok" in out_r
        and "reviewer heterogeneity: verified" in out_r  # dogfood routing active
    )
    # (b) A gate-config with a bad type fails loudly (not silently accepted).
    bad = {"version": quality_loop.CONFIG_SCHEMA_VERSION,
           "tests": {"path_markers": ["evals/", 7]},  # non-string marker
           "protect_harness": "yes"}                   # non-bool
    bad_path = tmp / "bad-gate-config.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    code_b, _, err_b = run_cli("check-config", str(bad_path))
    bad_ok = (
        code_b == 1
        and "tests.path_markers must be an array of non-empty strings" in err_b
        and "protect_harness must be a boolean" in err_b
    )
    # (c) Full config (profiles/steps present) is unchanged: still the full path.
    full = json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    full_path = tmp / "full-config.json"
    full_path.write_text(json.dumps(full), encoding="utf-8")
    code_f, out_f, _ = run_cli("check-config", str(full_path))
    full_ok = (
        code_f == 0
        and "config ok" in out_f
        and "gate-config (no orchestration sections)" not in out_f
        and "reviewer heterogeneity" in out_f  # full path prints the het line
    )
    # (d) A HYBRID config — gate keys plus an orchestration-facing section
    # (model_routing) but no profiles/steps — must NOT slip through the
    # gate-config shortcut with routing/heterogeneity validation skipped: it
    # takes the full path and fails loudly on the missing orchestration core.
    hybrid = {"version": quality_loop.CONFIG_SCHEMA_VERSION,
              "base": "origin/main",
              "model_routing": {"host": "github"}}
    hybrid_path = tmp / "hybrid-config.json"
    hybrid_path.write_text(json.dumps(hybrid), encoding="utf-8")
    code_h, out_h, err_h = run_cli("check-config", str(hybrid_path))
    hybrid_ok = (
        code_h == 1
        and "gate-config (no orchestration sections)" not in out_h
        and "missing required field: profiles" in err_h
    )
    ok = repo_ok and bad_ok and full_ok and hybrid_ok
    return ok, (f"repo_ok={repo_ok}(exit={code_r}); bad_ok={bad_ok}(exit={code_b}); "
                f"full_ok={full_ok}(exit={code_f}); hybrid_ok={hybrid_ok}(exit={code_h})")


def case_record_mutation_roundtrip(tmp: Path) -> tuple[bool, str]:
    """record set-status/add-evidence/add-ac mutate the record atomically,
    preserve unknown fields, and the mutated record still passes check-record."""
    record = base_record(status="implement")
    record["custom_extra"] = {"keep": "me"}  # unknown field must survive mutation
    path = tmp / "record.json"
    path.write_text(json.dumps(record))

    c1, _, e1 = run_cli("record", "set-status", str(path), "verify")
    c2, _, e2 = run_cli(
        "record", "add-evidence", str(path),
        "--cmd", "pytest -q", "--result", "pass", "--class", "unit",
        "--evidence", "13 passed",
    )
    c3, _, e3 = run_cli(
        "record", "add-ac", str(path),
        "--criterion", "totals round once", "--proving-command", "pytest -q",
    )
    mutated = json.loads(path.read_text())
    status_set = mutated.get("status") == "verify"
    row = (mutated.get("commands_run") or [])[-1]
    row_ok = row == {"cmd": "pytest -q", "class": "unit", "result": "pass", "evidence": "13 passed"}
    ac = (mutated.get("acceptance_criteria") or [])[-1]
    ac_ok = ac == {"criterion": "totals round once", "proving_command": "pytest -q"}
    preserved = mutated.get("custom_extra") == {"keep": "me"}
    check_code, _, check_err = run_cli("check-record", str(path))
    ok = (
        c1 == c2 == c3 == 0 and status_set and row_ok and ac_ok
        and preserved and check_code == 0
    )
    return ok, (
        f"exits=({c1},{c2},{c3}); status_set={status_set}; row_ok={row_ok}; "
        f"ac_ok={ac_ok}; preserved={preserved}; check_record={check_code} "
        f"err={(e1 + e2 + e3 + check_err).strip()[:120]!r}"
    )


def case_record_mutation_malformed_errors(tmp: Path) -> tuple[bool, str]:
    """Malformed record-mutation input (missing file, bad status, bad result
    enum, non-object record, blank criterion) exits non-zero with a clear
    stderr message — never a traceback."""
    path = tmp / "record.json"
    path.write_text(json.dumps(base_record()))
    list_path = tmp / "list.json"
    list_path.write_text("[1, 2]")

    runs = [
        run_cli("record", "set-status", str(tmp / "missing.json"), "plan"),
        run_cli("record", "set-status", str(path), "shipped"),
        run_cli(
            "record", "add-evidence", str(path),
            "--cmd", "x", "--result", "maybe", "--class", "unit", "--evidence", "e",
        ),
        run_cli("record", "set-status", str(list_path), "plan"),
        run_cli("record", "add-ac", str(path), "--criterion", "   ", "--proving-command", "x"),
    ]
    all_nonzero = all(code != 0 for code, _, _ in runs)
    no_traceback = all("Traceback" not in (out + err) for _, out, err in runs)
    messages = [
        ("not found", runs[0][2]),
        ("invalid choice", runs[1][2]),
        ("invalid choice", runs[2][2]),
        ("must be a JSON object", runs[3][2]),
        ("non-empty string", runs[4][2]),
    ]
    clear = all(needle in err for needle, err in messages)
    untouched = json.loads(path.read_text())["status"] == "intake"  # failed runs never wrote
    ok = all_nonzero and no_traceback and clear and untouched
    return ok, (
        f"exits={[c for c, _, _ in runs]}; no_traceback={no_traceback}; "
        f"clear={clear}; untouched={untouched}"
    )


def case_record_mutation_refuses_invalid_result(tmp: Path) -> tuple[bool, str]:
    """A mutation that would INTRODUCE a validation error is refused and leaves
    the file untouched (v6.2 cross-family review): the CLI must never persist a
    record it just made invalid. Concretely, `set-status done` on a record with
    no minimality_decision introduces the 'required at minimality_gate or later'
    error, so it must exit non-zero, print that error, and NOT write."""
    path = tmp / "record.json"
    rec = base_record()
    rec["status"] = "intake"
    rec.pop("minimality_decision", None)
    path.write_text(json.dumps(rec))
    code, out, err = run_cli("record", "set-status", str(path), "done")
    refused = code != 0 and "minimality_decision is required" in err and "invalid" in err.lower()
    untouched = json.loads(path.read_text())["status"] == "intake"
    # And a mutation that keeps the record valid still succeeds.
    code_ok, _, _ = run_cli("record", "set-status", str(path), "explore")
    advanced = code_ok == 0 and json.loads(path.read_text())["status"] == "explore"
    ok = refused and untouched and advanced
    return ok, f"refused={refused}; untouched={untouched}; valid_move_ok={advanced}"


def case_record_outcome_writes_field_and_ledger(tmp: Path) -> tuple[bool, str]:
    """record outcome sets record['outcome'] (verdict/note/recorded_at), appends
    a {task_id, verdict, note, recorded_at} line to .quality-loop/outcomes.jsonl,
    the record still passes check-record, and a malformed outcome fails it."""
    path = tmp / "record.json"
    path.write_text(json.dumps(base_record()))
    c1, out1, err1 = run_cli("record", "outcome", str(path), "clean", "--note", "shipped fine")
    c2, _, _ = run_cli("record", "outcome", str(path), "regressed", "--note", "hotfixed later")

    record = json.loads(path.read_text())
    field = record.get("outcome") or {}
    field_ok = bool(
        field.get("verdict") == "regressed"
        and field.get("note") == "hotfixed later"
        and isinstance(field.get("recorded_at"), str) and field["recorded_at"]
    )
    ledger = tmp / ".quality-loop" / "outcomes.jsonl"
    rows = [json.loads(l) for l in ledger.read_text().splitlines()] if ledger.is_file() else []
    ledger_ok = (
        len(rows) == 2
        and rows[0] == {"task_id": "t-eval", "verdict": "clean", "note": "shipped fine",
                        "recorded_at": rows[0].get("recorded_at")}
        and rows[1].get("verdict") == "regressed"
    )
    check_code, _, _ = run_cli("check-record", str(path))

    bad = base_record()
    bad["outcome"] = {"verdict": "meh"}
    bad_path = tmp / "bad.json"
    bad_path.write_text(json.dumps(bad))
    bad_code, _, bad_err = run_cli("check-record", str(bad_path))
    bad_rejected = bad_code == 1 and "outcome.verdict" in bad_err

    # v6.3.0 regression: inside a git repo, an outcome recorded on an ARCHIVED
    # record (docs/records/*.json) must append to the repo root's
    # .quality-loop/outcomes.jsonl — where brief reads the tally — not nest a
    # stray docs/records/.quality-loop/ next to the archive.
    repo = tmp / "arch-repo"
    (repo / "docs" / "records").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    arch = repo / "docs" / "records" / "vX-record.json"
    arch.write_text(json.dumps(base_record()))
    c3, _, _ = run_cli("record", "outcome", str(arch), "clean", "--note", "post-ship")
    root_ledger = repo / ".quality-loop" / "outcomes.jsonl"
    stray = repo / "docs" / "records" / ".quality-loop"
    archived_ok = c3 == 0 and root_ledger.is_file() and not stray.exists()

    ok = (c1 == c2 == 0 and field_ok and ledger_ok and check_code == 0
          and bad_rejected and archived_ok)
    return ok, (
        f"exits=({c1},{c2}); field_ok={field_ok}; ledger_rows={len(rows)}; "
        f"ledger_ok={ledger_ok}; check_record={check_code}; bad_rejected={bad_rejected}; "
        f"archived_ok={archived_ok}"
    )


def case_brief_prints_outcome_tally(tmp: Path) -> tuple[bool, str]:
    """brief prints the one-line outcomes tally when .quality-loop/outcomes.jsonl
    exists (skipping malformed lines) and stays silent when it is absent."""
    silent_dir = tmp / "no-ledger"
    silent_dir.mkdir()
    code_s, out_s, _ = run_cli("brief", "--cwd", str(silent_dir), cwd=str(silent_dir))
    silent = code_s == 0 and "outcomes (this repo)" not in out_s

    ql_dir = tmp / ".quality-loop"
    ql_dir.mkdir()
    rows = [
        {"task_id": "a", "verdict": "clean", "note": "", "recorded_at": "2026-07-21T00:00:00+00:00"},
        {"task_id": "b", "verdict": "clean", "note": "", "recorded_at": "2026-07-21T00:00:01+00:00"},
        {"task_id": "c", "verdict": "regressed", "note": "x", "recorded_at": "2026-07-21T00:00:02+00:00"},
    ]
    (ql_dir / "outcomes.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\nnot json\n"
    )
    code_t, out_t, _ = run_cli("brief", "--cwd", str(tmp), cwd=str(tmp))
    expected = "outcomes (this repo): 3 recorded — 2 clean, 1 regressed, 0 reverted"
    tally = code_t == 0 and expected in out_t
    code_j, out_j, _ = run_cli("brief", "--cwd", str(tmp), "--json", cwd=str(tmp))
    try:
        json_tally = json.loads(out_j).get("outcomes_tally") == expected
    except json.JSONDecodeError:
        json_tally = False
    ok = silent and tally and code_j == 0 and json_tally
    return ok, f"silent={silent}; tally={tally}; json_tally={json_tally}; exits=({code_s},{code_t},{code_j})"


def case_derived_count_lint_catches_wrong_number(tmp: Path) -> tuple[bool, str]:
    """canonical_gate_cases()/control_addon_cases() are DERIVED from the real
    suites (static cases/*.json + each suite's len(CASES)), and the lint still
    fails a doc stating a wrong number against the derived totals."""
    import importlib

    evals_dir = str(ROOT / "evals")
    if evals_dir not in sys.path:
        sys.path.insert(0, evals_dir)
    static = len(list((ROOT / "evals" / "cases").glob("*.json")))
    suites = {
        m: len(importlib.import_module(m).CASES)
        for m in ("run_memory_evals", "run_reality_evals", "run_routing_evals", "run_hook_evals")
    }
    expected = static + len(CASES) + sum(suites.values())
    canonical = canonical_gate_cases()
    addon = control_addon_cases()
    derived_ok = (
        canonical == expected
        and addon == len(importlib.import_module("run_control_evals").CASES)
        and canonical > 0 and addon > 0
    )

    wrong = _doc_count_mismatches(
        f"the suite ships {canonical + 1} gate cases plus {addon + 1} add-on cases",
        "synthetic.md", False, canonical, addon,
    )
    right = _doc_count_mismatches(
        f"the suite ships {canonical} gate cases plus {addon} add-on cases",
        "synthetic.md", False, canonical, addon,
    )
    catches = len(wrong) == 2 and right == []

    # Per-suite breakdown arithmetic (v6.2 review): a right TOTAL with ONE wrong
    # addend (hook off by one) must be caught when suite_counts is supplied.
    sc = {"static": static, "behavioral": len(CASES), "memory": suites["run_memory_evals"],
          "reality": suites["run_reality_evals"], "routing": suites["run_routing_evals"],
          "hook": suites["run_hook_evals"]}
    good_bd = (f"{sc['static']} static + {sc['behavioral']} behavioral + {sc['memory']} memory + "
               f"{sc['reality']} reality + {sc['routing']} routing + {sc['hook']} hook = {canonical} cases")
    bad_bd = good_bd.replace(f"{sc['hook']} hook", f"{sc['hook'] - 1} hook")  # addend wrong, total right-looking
    bd_clean = _doc_count_mismatches(good_bd, "synthetic.md", False, canonical, addon, sc) == []
    bd_caught = len(_doc_count_mismatches(bad_bd, "synthetic.md", False, canonical, addon, sc)) >= 1

    # v6.5.0 round-5/6 regressions: (a) a count split from its phrase by a
    # hard wrap is still one mention; (b) a historical clause must not mask a
    # stale CURRENT count in the next clause (and the historical one stays
    # exempt: exactly one mismatch); (c) a suite's own table row must carry
    # its derived count.
    wrapped = _doc_count_mismatches(
        f"reject drift. {canonical - 2}\noffline gate cases keep it honest.",
        "synthetic.md", False, canonical, addon)
    masked = _doc_count_mismatches(
        f"as of v6.4 it shipped {canonical - 2} gate cases. "
        f"Current release: {canonical - 1} gate cases.",
        "synthetic.md", False, canonical, addon)
    row_bad = _doc_count_mismatches(
        f"| Hook (host shims) | {sc['hook'] + 1} | `evals/run_hook_evals.py` |",
        "synthetic.md", False, canonical, addon, sc)
    row_good = _doc_count_mismatches(
        f"| Hook (host shims) | {sc['hook']} | `evals/run_hook_evals.py` |",
        "synthetic.md", False, canonical, addon, sc)
    hardened = (len(wrapped) == 1 and len(masked) == 1
                and len(row_bad) == 1 and row_good == [])

    ok = derived_ok and catches and bd_clean and bd_caught and hardened
    return ok, (
        f"canonical={canonical} (static={static} + behavioral={len(CASES)} + {suites}); "
        f"addon={addon}; derived_ok={derived_ok}; wrong_flagged={len(wrong)}; "
        f"bd_clean={bd_clean}; bd_caught={bd_caught}; "
        f"wrapped={len(wrapped)}; masked={len(masked)}; row_bad={len(row_bad)}; row_good={len(row_good)}"
    )


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
    ("diff-audit untracked hygiene: scaffolding excluded, unreadable surfaced, cql: marker counted", case_diff_audit_untracked_hygiene),
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
    ("schema accepts object acceptance criteria with proving_command (and strings)", case_schema_accepts_object_acceptance_criteria),
    ("optional run_metrics with non-negative numbers passes check-record", case_run_metrics_valid_passes),
    ("run_metrics with a string cost_usd fails check-record", case_run_metrics_string_cost_fails),
    ("verify --require-terminal blocks an unclosed loop (implement + dirty diff)", case_require_terminal_blocks_unclosed_loop),
    ("verify --require-terminal is a no-op at done status", case_require_terminal_noop_when_done),
    ("public docs state the canonical gate-case count (numbers-consistency lint)", case_doc_counts_match_canonical),
    ("bench --validate enforces doc mode + runs + live cost/provenance (fixture docs exempt)", case_bench_validate_requires_cost_fields),
    ("optional models_used entries validate shape, attempts, and costs", case_models_used_shape),
    ("escalations entries require verified_failure trigger and differing models", case_escalations_shape),
    ("escalation must cite a recorded failing command (self-report is not evidence)", case_escalation_requires_failing_evidence),
    ("resolved RED->GREEN failures don't block; outstanding failures do", case_resolved_failures_dont_block),
    ("archived v4.1.0 record passes untouched (v4.2 fields are additive)", case_v41_record_fixture_passes),
    ("every docs/records/*.json passes check-record (archive cannot rot)", case_all_archived_records_pass_check),
    ("string ACs block at medium+ but stay valid at low risk", case_string_acs_blocked_at_medium_not_low),
    (">=3 ACs sharing one proving_command draws an advisory note only", case_shared_proving_command_warns),
    ("e2e/security/format/migration_dry_run count as executable evidence", case_new_exec_classes_count),
    ("blocking verify-gates findings print as error:, not warning:", case_blocking_findings_print_as_error),
    ("reviewer contract (verdict enum + ran_checks) agrees across prompt/agents/schema", case_reviewer_contract_surfaces_agree),
    ("paper trail is four artifacts (contract/plan/record/progress)", case_paper_trail_is_four_artifacts),
    ("approving review without ran_checks draws a note at medium+ (never blocking)", case_ran_checks_warns_not_fails),
    ("brief caps an over-budget recalled lesson in text and --json output", case_brief_caps_over_budget_lesson),
    ("control_plane shape is validated in core even without the add-on installed", case_check_config_core_control_plane_shape),
    ("check-config prints heterogeneity_status even without model_routing (SKIPPED)", case_check_config_always_prints_heterogeneity),
    ("check-config accepts a gate-config-only shape (no profiles/steps); bad types still fail", case_check_config_gate_config_only),
    ("config schema version is pinned three ways (engine == schema const == example)", case_config_schema_version_pinned),
    ("release surfaces share one version (npm == SKILL == README badge == gh example)", case_release_version_parity),
    ("record set-status/add-evidence/add-ac round-trip; mutated record passes check-record", case_record_mutation_roundtrip),
    ("malformed record-mutation input errors cleanly (no traceback, no write)", case_record_mutation_malformed_errors),
    ("record mutation refuses to write a newly-invalid record", case_record_mutation_refuses_invalid_result),
    ("record outcome writes the field and the outcomes.jsonl ledger", case_record_outcome_writes_field_and_ledger),
    ("brief prints the outcomes tally and stays silent without a ledger", case_brief_prints_outcome_tally),
    ("derived count lint computes the real total and still catches a wrong doc number", case_derived_count_lint_catches_wrong_number),
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
