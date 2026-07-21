#!/usr/bin/env python3
"""Reality-layer eval harness for the Coding Quality Loop.

Builds temp git repos where the record and the diff disagree, then asserts the
diff-grounded gates catch the lie. Mirrors evals/run_evals.py: drives the real
CLI via subprocess in a tempdir. Dependency-free; CI-friendly.

Run: python evals/run_reality_evals.py   (exits non-zero if any case fails)

Cases (record↔reality verification):
  1.  phantom completion (package/done with an empty diff) is caught
  2.  an unmapped changed file is caught (scope integrity)
  3.  an auth path under a low tier is caught (diff-derived risk floor)
  4.  a missing bugfix test is caught (bugfix-test co-presence)
  5.  a stale review hash is caught (review freshness)
  6.  lying evidence (recorded pass that fails on rerun) is caught
  7.  a faked RED→GREEN (command passes at base) is caught
  8.  a staged secret is caught by diff-audit --staged
  9.  attest-review embeds a recomputed diff sha256
 10.  scan-text --stdin catches a secret
 11.  a clean, well-mapped record passes --against-diff
 12.  run-evidence refuses a command not on the allowlist
 13.  a softened local gate script passes locally but the pinned CI copy still
      blocks the same phantom-completion record (F1 CI trust anchor)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "quality_loop.py"

sys.path.insert(0, str(ROOT / "scripts"))
import quality_loop_core as qlcore  # noqa: E402
import quality_loop_reality as qlreal  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"


def run_cli(
    *args: str,
    cwd: str | None = None,
    stdin: str | None = None,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    # QUALITY_LOOP_BASE is scrubbed by default so a developer's ambient env
    # cannot change what these cases pin; pass env explicitly to test it.
    run_env = {k: v for k, v in os.environ.items() if k != "QUALITY_LOOP_BASE"}
    if env:
        run_env.update(env)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        input=stdin,
        env=run_env,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def make_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "eval@example.com")
    _git(repo, "config", "user.name", "eval")
    (repo / "README.md").write_text("# test\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "base")
    return repo


def write_record(repo: Path, record: dict) -> Path:
    path = repo / "agent-record.json"
    path.write_text(json.dumps(record))
    return path


def write_allowlist(repo: Path, patterns: list[str]) -> None:
    al = repo / ".quality-loop" / "allowed-commands"
    al.parent.mkdir(parents=True, exist_ok=True)
    al.write_text("\n".join(patterns) + "\n")


def _contract() -> dict:
    return {
        "goal": "Add rounding to the total calculation",
        "acceptance_criteria": ["total rounds once"],
        "evidence": ["pytest -> pass", "mypy -> clean"],
    }


def _completion(files: list[str] | None = None) -> dict:
    cr = {
        "goal": "Add rounding to the total calculation",
        "acceptance_criteria": ["total rounds once"],
        "evidence": ["pytest -> 14 passed", "fresh-context review: approve"],
    }
    if files is not None:
        cr["files_changed"] = files
    return cr


def passing_record(repo: Path, **overrides) -> dict:
    """A medium record that passes the record-only gates. diff_sha256 is set
    to the current diff hash so review freshness is clean unless overridden.

    The goal/plan/acceptance_criteria deliberately avoid boundary keywords
    (billing, charge, auth, ...) so the TEXT risk floor does not fire and the
    only findings come from the diff-grounded reality checks.
    """
    try:
        hash_val = qlreal.diff_sha256("HEAD", cwd=repo)
    except SystemExit:
        hash_val = ""
    record = {
        "task_id": "t-reality",
        "goal": "Add rounding to the total calculation",
        "task_class": "medium",
        "risk_tier": "medium",
        # Medium+ requires provable criteria: object AC whose proving_command
        # matches the pass command below (string ACs block at medium+ risk).
        "acceptance_criteria": [{"criterion": "total rounds once", "proving_command": "pytest"}],
        "constraints": [],
        "non_goals": [],
        "assumptions": [],
        "verification_plan": ["unit tests"],
        "minimality_decision": {"rung": "reuse", "reason": "existing helper covers it"},
        "plan": ["edit src/invoice/round.py to round the summed total"],
        "commands_run": [{"cmd": "pytest", "class": "unit", "result": "pass", "evidence": "12 passed"}],
        "open_risks": [],
        "review_findings": ["fresh-context review: approved"],
        "repo_map": {
            "entry_points": ["src/invoice/round.py:round_total"],
            "likely_files": ["src/invoice/round.py"],
            "callers_checked": ["src/invoice/api.py:submit"],
            "tests": ["tests/test_invoice.py"],
            "patterns_to_follow": [],
        },
        "implementer": "agent-a",
        "validation_contract": _contract(),
        "independent_review": {
            "reviewer": "agent-b",
            "verdict": "approve",
            "fresh_context": True,
            "patched": False,
            "findings": [],
            "diff_sha256": hash_val,
        },
        "security_review": None,
        "completion_record": _completion(),
        "security_sensitive": False,
        "status": "done",
    }
    record.update(overrides)
    return record


# --- Cases -----------------------------------------------------------------


def case_phantom_completion(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    # No working-tree changes -> empty diff at HEAD.
    record = passing_record(repo)
    path = write_record(repo, record)
    code, out, err = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
    ok = code == 1 and "phantom completion" in (out + err).lower()
    return ok, f"exit={code}; output={ (out + err).strip()[:200]!r}"


def case_unmapped_file(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    invoice = repo / "src" / "invoice"
    invoice.mkdir(parents=True)
    (invoice / "round.py").write_text("def round_total(): pass\n")
    # An unmapped file not in repo_map/plan/completion.
    other = repo / "src" / "other"
    other.mkdir(parents=True)
    (other / "surprise.py").write_text("x = 1\n")
    record = passing_record(repo)
    path = write_record(repo, record)
    code, out, err = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
    ok = code == 1 and "scope integrity" in (out + err).lower()
    return ok, f"exit={code}; output={ (out + err).strip()[:200]!r}"


def case_auth_path_low_tier(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    auth = repo / "src" / "auth"
    auth.mkdir(parents=True)
    (auth / "login.py").write_text("def login(): pass\n")
    # Goal deliberately avoids boundary keywords so the TEXT floor does not fire;
    # only the DIFF-derived floor should catch the auth/ path.
    record = passing_record(
        repo,
        goal="rename a local helper for clarity",
        risk_tier="low",
        task_class="small",
        status="done",
        commands_run=[{"cmd": "read", "class": "lint", "result": "pass", "evidence": "looks good"}],
        validation_contract=None,
        independent_review=None,
        completion_record=None,
        repo_map={"entry_points": [], "likely_files": [], "callers_checked": [], "tests": []},
        plan=[],
        review_findings=[],
    )
    path = write_record(repo, record)
    code, out, err = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
    ok = code == 1 and "diff-derived risk floor" in (out + err).lower()
    return ok, f"exit={code}; output={ (out + err).strip()[:200]!r}"


def case_high_tier_path_forces_high_from_medium(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    (repo / "package-lock.json").write_text('{"lockfileVersion": 3}\n')
    record = passing_record(
        repo,
        risk_tier="medium",
        task_class="medium",
        completion_record=_completion(files=["package-lock.json"]),
        plan=["update package-lock.json after dependency review"],
    )
    path = write_record(repo, record)
    code, out, err = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
    ok = code == 1 and "diff-derived risk floor" in (out + err).lower()
    return ok, f"exit={code}; output={ (out + err).strip()[:200]!r}"


def case_missing_bugfix_test(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    invoice = repo / "src" / "invoice"
    invoice.mkdir(parents=True)
    (invoice / "round.py").write_text("def round_total(): return 42\n")
    record = passing_record(repo, goal="Fix the rounding bug in the total calculation")
    path = write_record(repo, record)
    code, out, err = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
    ok = code == 1 and "bugfix-test" in (out + err).lower()
    return ok, f"exit={code}; output={ (out + err).strip()[:200]!r}"


def case_stale_review_hash(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    billing = repo / "src" / "billing"
    billing.mkdir(parents=True)
    (billing / "invoice.py").write_text("def round_total(): pass\n")
    tests = repo / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_invoice.py").write_text("def test_round(): pass\n")
    record = passing_record(
        repo,
        independent_review={
            "reviewer": "agent-b",
            "verdict": "approve",
            "fresh_context": True,
            "patched": False,
            "findings": [],
            "diff_sha256": "0" * 64,  # deliberately wrong
        },
    )
    path = write_record(repo, record)
    code, out, err = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
    ok = code == 1 and "review freshness" in (out + err).lower() and "stale" in (out + err).lower()
    return ok, f"exit={code}; output={ (out + err).strip()[:200]!r}"


def case_lying_evidence(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    (repo / "fail.py").write_text("import sys; sys.exit(1)\n")
    write_allowlist(repo, [f"{sys.executable}*"])
    cmd = f"{sys.executable} fail.py"
    record = passing_record(
        repo,
        commands_run=[{"cmd": cmd, "class": "unit", "result": "pass", "evidence": "12 passed"}],
    )
    path = write_record(repo, record)
    code, out, err = run_cli("run-evidence", str(path), cwd=str(repo))
    ok = code == 1 and "did not pass on rerun" in (out + err).lower()
    return ok, f"exit={code}; output={ (out + err).strip()[:200]!r}"


def case_red_green_catch(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    # A test that ALWAYS passes (exit 0) — committed at base. RED is not real.
    (repo / "test_pass.py").write_text("import sys; sys.exit(0)\n")
    _git(repo, "add", "test_pass.py")
    _git(repo, "commit", "-m", "add always-pass test")
    write_allowlist(repo, [f"{sys.executable}*"])
    cmd = f"{sys.executable} test_pass.py"
    record = passing_record(
        repo,
        commands_run=[{"cmd": cmd, "class": "unit", "result": "pass", "evidence": "ok", "red_green": True}],
    )
    path = write_record(repo, record)
    code, out, err = run_cli("run-evidence", str(path), "--red-green", "--base", "HEAD", cwd=str(repo))
    ok = code == 1 and "red not proven" in (out + err).lower()
    return ok, f"exit={code}; output={ (out + err).strip()[:200]!r}"


def case_staged_secret(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    (repo / "config.py").write_text('api_key = "ghp_' + "A" * 36 + '"\n')
    _git(repo, "add", "config.py")
    code, out, err = run_cli("diff-audit", "--staged", cwd=str(repo))
    ok = code == 1 and "secret" in out.lower()
    return ok, f"exit={code}; output={out.strip()[:200]!r}"


def case_attest_review_embeds_hash(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    billing = repo / "src" / "billing"
    billing.mkdir(parents=True)
    (billing / "invoice.py").write_text("def round_total(): pass\n")
    review = {"reviewer": "agent-b", "verdict": "approve", "fresh_context": True, "patched": False}
    review_path = repo / "review.json"
    review_path.write_text(json.dumps(review))
    code, out, err = run_cli("attest-review", str(review_path), "--base", "HEAD", cwd=str(repo))
    try:
        attested = json.loads(out)
    except json.JSONDecodeError:
        attested = {}
    expected = qlreal.diff_sha256("HEAD", cwd=repo)
    ok = code == 0 and attested.get("diff_sha256") == expected and "attested_at" in attested
    return ok, f"exit={code}; hash_match={attested.get('diff_sha256') == expected}; err={err.strip()[:80]!r}"


def case_scan_text_secret(tmp: Path) -> tuple[bool, str]:
    secret_text = 'config = {"api_key": "ghp_' + "B" * 36 + '"}\n'
    code, out, err = run_cli("scan-text", "--stdin", stdin=secret_text, cwd=str(tmp))
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        data = {}
    ok = code == 1 and data.get("clean") is False and len(data.get("findings", [])) >= 1
    return ok, f"exit={code}; clean={data.get('clean')}; findings={len(data.get('findings', []))}"


def case_clean_record_passes_against_diff(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    billing = repo / "src" / "billing"
    billing.mkdir(parents=True)
    (billing / "invoice.py").write_text("def round_total(): return round(sum([]), 2)\n")
    tests = repo / "tests"
    tests.mkdir(parents=True)
    (tests / "test_invoice.py").write_text("def test_round(): assert True\n")
    record = passing_record(
        repo,
        completion_record=_completion(files=["src/billing/invoice.py", "tests/test_invoice.py"]),
    )
    path = write_record(repo, record)
    code, out, err = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
    ok = code == 0
    return ok, f"exit={code}; output={ (out + err).strip()[:200]!r}"


def case_run_evidence_allowlist(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    # No allowlist file -> command is not allowed.
    record = passing_record(
        repo,
        commands_run=[{"cmd": "pytest", "class": "unit", "result": "pass", "evidence": "ok"}],
    )
    path = write_record(repo, record)
    code, out, err = run_cli("run-evidence", str(path), cwd=str(repo))
    ok = code == 1 and "not on allowlist" in (out + err).lower()
    return ok, f"exit={code}; output={ (out + err).strip()[:200]!r}"


def case_verify_umbrella_fails_when_section_fails(tmp: Path) -> tuple[bool, str]:
    """The verify umbrella must FAIL when any constituent section fails (here:
    verify-gates flags a missing implementer), and still emit the unified report.
    """
    repo = make_repo(tmp)
    billing = repo / "src" / "billing"
    billing.mkdir(parents=True)
    (billing / "invoice.py").write_text("def round_total(): return round(sum([]), 2)\n")
    tests = repo / "tests"
    tests.mkdir(parents=True)
    (tests / "test_invoice.py").write_text("def test_round(): assert True\n")
    record = passing_record(
        repo,
        implementer=None,  # forces a verify-gates finding (named implementer required)
        completion_record=_completion(files=["src/billing/invoice.py", "tests/test_invoice.py"]),
    )
    path = write_record(repo, record)
    code, out, err = run_cli("verify", str(path), "--base", "HEAD", cwd=str(repo))
    combined = out + err
    has_report = "unified gate report" in combined
    overall_fail = "Overall: FAIL" in combined
    flagged = "named implementer" in combined
    ok = code == 1 and has_report and overall_fail and flagged
    return ok, f"exit={code}; report={has_report}; overall_fail={overall_fail}; flagged={flagged}"


def case_verify_in_non_git_repo(tmp: Path) -> tuple[bool, str]:
    """In a non-git directory, verify must NOT exit 129 with no report. It should
    emit the unified report with the diff-audit/verify-gates sections recorded as
    failed (could-not-read-diff) and exit non-zero.
    """
    nongit = tmp / "nongit"
    nongit.mkdir()
    record = {
        "task_id": "t-nogit",
        "goal": "rename a local helper for clarity",
        "risk_tier": "low",
        "task_class": "tiny",
        "acceptance_criteria": [],
        "constraints": [],
        "non_goals": [],
        "assumptions": [],
        "verification_plan": [],
        "minimality_decision": {"rung": "one_liner", "reason": "rename"},
        "plan": [],
        "commands_run": [],
        "open_risks": [],
        "review_findings": [],
        "repo_map": {"entry_points": [], "likely_files": [], "callers_checked": [], "tests": []},
        "implementer": "agent-a",
        "validation_contract": None,
        "independent_review": None,
        "completion_record": None,
        "security_sensitive": False,
        "status": "done",
    }
    path = write_record(nongit, record)
    code, out, err = run_cli("verify", str(path), "--base", "HEAD", cwd=str(nongit))
    combined = out + err
    no_129 = code != 129
    has_report = "unified gate report" in combined
    no_traceback = "Traceback" not in combined
    ok = no_129 and has_report and no_traceback and code != 0
    return ok, f"exit={code}; no_129={no_129}; report={has_report}; no_traceback={no_traceback}"


def case_unresolvable_base_falls_back_with_hint(tmp: Path) -> tuple[bool, str]:
    """P1.7: an unresolvable --base must not crash. diff-audit resolves a sane
    fallback and surfaces a human-readable hint in `advisory` (exit 0)."""
    repo = make_repo(tmp)
    code, out, err = run_cli("diff-audit", "--base", "origin/does-not-exist", cwd=str(repo))
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        return False, f"non-json output (exit={code}): {(out + err)[:120]!r}"
    resolved_base = payload.get("base")
    fell_back = bool(resolved_base) and resolved_base != "origin/does-not-exist"
    hint = any(
        "did not resolve" in a or "falling back" in a or "fell back" in a
        for a in payload.get("advisory", [])
    )
    ok = code == 0 and fell_back and hint
    return ok, f"exit={code}; resolved_base={resolved_base!r}; hint={hint}"


def case_verify_object_ac_coverage(tmp: Path) -> tuple[bool, str]:
    """AC-to-command coverage must read proving_command off object acceptance
    criteria: a matching proving_command passes; a non-matching one fails the
    AC coverage section and the umbrella overall.
    """
    repo = make_repo(tmp)
    billing = repo / "src" / "billing"
    billing.mkdir(parents=True)
    (billing / "invoice.py").write_text("def round_total(): return round(sum([]), 2)\n")
    tests = repo / "tests"
    tests.mkdir(parents=True)
    (tests / "test_invoice.py").write_text("def test_round(): assert True\n")
    write_allowlist(repo, [f"{sys.executable}*"])
    cmd = f"{sys.executable} -c pass"
    record = passing_record(
        repo,
        acceptance_criteria=[
            {"criterion": "total rounds once", "proving_command": cmd},
            {"criterion": "no exceptions on empty input", "proving_command": "missing-cmd"},
        ],
        commands_run=[{"cmd": cmd, "class": "unit", "result": "pass", "evidence": "ok"}],
        completion_record=_completion(files=["src/billing/invoice.py", "tests/test_invoice.py"]),
    )
    path = write_record(repo, record)
    code, out, err = run_cli("verify", str(path), "--base", "HEAD", cwd=str(repo))
    combined = out + err
    ac_section_failed = "FAIL] AC coverage" in combined or ("AC coverage" in combined and "missing-cmd" in combined)
    overall_fail = "Overall: FAIL" in combined
    ok = code == 1 and ac_section_failed and overall_fail
    return ok, f"exit={code}; ac_failed={ac_section_failed}; overall_fail={overall_fail}"


def case_record_only_trailing_change_stays_fresh(tmp: Path) -> tuple[bool, str]:
    """A review attested before a .quality-loop/-only change must NOT go stale:
    attestation hashes exclude the record dir."""
    repo = make_repo(tmp)
    billing = repo / "src" / "billing"
    billing.mkdir(parents=True)
    (billing / "invoice.py").write_text("def round_total(): return round(sum([]), 2)\n")
    tests = repo / "tests"
    tests.mkdir(parents=True)
    (tests / "test_invoice.py").write_text("def test_round(): assert True\n")
    # Track a record artifact at base so a later edit shows up in git diff.
    qdir = repo / ".quality-loop"
    qdir.mkdir()
    (qdir / "progress.md").write_text("start\n")
    _git(repo, "add", ".quality-loop/progress.md")
    _git(repo, "commit", "-m", "track progress")
    attested_hash = qlreal.diff_sha256("HEAD", cwd=repo, exclude_record_dir=True)
    # Record-only trailing change AFTER attestation.
    (qdir / "progress.md").write_text("start\nfinal verify evidence recorded\n")
    record = passing_record(
        repo,
        independent_review={
            "reviewer": "agent-b",
            "verdict": "approve",
            "fresh_context": True,
            "patched": False,
            "findings": [],
            "diff_sha256": attested_hash,
        },
        completion_record=_completion(files=["src/billing/invoice.py", "tests/test_invoice.py"]),
    )
    path = write_record(repo, record)
    code, out, err = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
    combined = (out + err).lower()
    ok = code == 0 and "review freshness" not in combined
    return ok, f"exit={code}; output={ (out + err).strip()[:200]!r}"


def case_init_record_scaffolds_allowlist(tmp: Path) -> tuple[bool, str]:
    # Explicit root --output (the deprecated fallback location) still works...
    repo = make_repo(tmp)
    code, out, err = run_cli(
        "init-record", "--goal", "Fix invoice rounding", "--risk-tier", "medium",
        "--output", "agent-record.json", cwd=str(repo),
    )
    allowlist = repo / ".quality-loop" / "allowed-commands"
    root_ok = code == 0 and allowlist.is_file() and "allowed-commands" in out

    # ...and the DEFAULT is the one canonical path, .quality-loop/agent-record.json
    # (1.1: the root default structurally broke review freshness — writing the
    # attested review into a root record changed the hashed diff). init-record
    # must create the directory itself.
    sub = tmp / "default"
    sub.mkdir()
    repo2 = make_repo(sub)
    code2, out2, err2 = run_cli(
        "init-record", "--goal", "Fix invoice rounding", cwd=str(repo2),
    )
    default_record = repo2 / ".quality-loop" / "agent-record.json"
    default_allowlist = repo2 / ".quality-loop" / "allowed-commands"
    default_ok = (
        code2 == 0
        and default_record.is_file()
        and default_allowlist.is_file()
        and ".quality-loop/agent-record.json" in out2
        and not (repo2 / "agent-record.json").exists()
    )
    ok = root_ok and default_ok
    return ok, f"explicit_root(exit={code},ok={root_ok}); default(exit={code2},ok={default_ok})"


def case_partial_install_fails_actionably(tmp: Path) -> tuple[bool, str]:
    """A scripts/ copy missing a sibling module must fail with an actionable
    message, not a raw ImportError traceback (agents have been observed
    stubbing/softening the helper instead of reporting the breakage)."""
    partial = tmp / "partial"
    partial.mkdir()
    src = Path(__file__).resolve().parent.parent / "scripts"
    for name in ("quality_loop.py", "quality_loop_memory.py"):
        (partial / name).write_text((src / name).read_text(encoding="utf-8"), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(partial / "quality_loop.py"), "brief"],
        capture_output=True, text=True, cwd=str(tmp),
    )
    combined = proc.stdout + proc.stderr
    ok = (
        proc.returncode == 2
        and "incomplete install" in combined
        and "Traceback" not in combined
    )
    return ok, f"exit={proc.returncode}; output={combined.strip()[:200]!r}"


def case_ci_anchor_defeats_softened_local_script(tmp: Path) -> tuple[bool, str]:
    """Red-team replay of the documented gate-softening attack (F1).

    An agent can soften the gate script inside the repo under review and make
    the LOCAL invocation pass. CI must still catch the lie because it runs the
    action's OWN pinned copy (simulated here by the real repo's absolute-path
    script) instead of the checkout copy. This pins the VERIFY half of the
    trust-anchor property: a pristine copy catches the lie a softened copy
    hides. The ACTION half — that action.yml actually invokes the pinned copy —
    is pinned separately by case_action_invocations_are_pinned.
    """
    repo = make_repo(tmp)

    # 1. Attacker softens the LOCAL gate script AND commits it — the exact
    #    attack the README documents. Committing keeps the working tree clean,
    #    so the record's "done" claim is a genuine phantom completion.
    local_scripts = repo / "scripts"
    local_scripts.mkdir(parents=True, exist_ok=True)
    softened = local_scripts / "quality_loop.py"
    softened.write_text("import sys\nprint('PASS')\nsys.exit(0)\n", encoding="utf-8")
    _git(repo, "add", "scripts/quality_loop.py")
    _git(repo, "commit", "-m", "soften gate")

    # A garbage record claiming done with no real diff and fabricated evidence
    # (passing_record's evidence strings are self-declared; the tree is clean).
    record = passing_record(repo)
    path = write_record(repo, record)

    # 2. The softened LOCAL copy passes — the local attack "succeeds".
    local = subprocess.run(
        [sys.executable, str(softened), "verify", str(path), "--base", "HEAD"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(repo), check=False,
    )
    local_attack_succeeds = local.returncode == 0

    # 3. The REAL pinned copy (absolute path == GITHUB_ACTION_PATH copy) still
    #    catches the phantom completion against the same repo/record.
    code, out, err = run_cli("verify", str(path), "--base", "HEAD", cwd=str(repo))
    combined = (out + err).lower()
    ci_blocks = code != 0 and "phantom completion" in combined

    ok = local_attack_succeeds and ci_blocks
    return ok, f"local_exit={local.returncode}; ci_exit={code}; ci_flagged_phantom={'phantom completion' in combined}"


def case_verify_reports_helper_integrity(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    billing = repo / "src" / "billing"
    billing.mkdir(parents=True)
    (billing / "invoice.py").write_text("def round_total(): return round(sum([]), 2)\n")
    tests = repo / "tests"
    tests.mkdir(parents=True)
    (tests / "test_invoice.py").write_text("def test_round(): assert True\n")
    write_allowlist(repo, ["pytest*"])
    record = passing_record(
        repo,
        commands_run=[],
        completion_record=_completion(files=["src/billing/invoice.py", "tests/test_invoice.py"]),
    )
    path = write_record(repo, record)
    code, out, err = run_cli("verify", str(path), "--base", "HEAD", cwd=str(repo))
    combined = out + err
    has_section = "helper-integrity" in combined
    hashes = re.findall(r"quality_loop[a-z_]*\.py: [0-9a-f]{64}", combined)
    ok = has_section and len(hashes) == 5
    return ok, f"exit={code}; section={has_section}; hashes={len(hashes)}"


def case_action_invocations_are_pinned(tmp: Path) -> tuple[bool, str]:
    """Pin the ACTION half of the trust anchor: every python invocation in
    action.yml must run the action's own copy via GITHUB_ACTION_PATH. If a
    revert reintroduces `python3 scripts/quality_loop.py` (the checkout copy),
    the documented soften-and-commit attack works end-to-end again."""
    text = (ROOT / "action.yml").read_text(encoding="utf-8")
    offenders = [
        line.strip()
        for line in text.splitlines()
        if ("python3" in line or "python " in line)
        and "GITHUB_ACTION_PATH" not in line
        and not line.strip().startswith("#")
    ]
    ok = not offenders and "GITHUB_ACTION_PATH" in text
    return ok, f"python_lines_unpinned={offenders!r}"


def _default_branch(repo: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), "symbolic-ref", "--short", "HEAD"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    return proc.stdout.strip() or "master"


def case_committed_work_still_diffed(tmp: Path) -> tuple[bool, str]:
    """Commit-first evasion (1.1): work fully committed on a feature branch must
    still be visible to the diff-grounded gates via the auto-resolved default
    base (merge-base vs the origin/main ladder) — with --base defaulting to
    HEAD this record passed silently."""
    repo = make_repo(tmp)
    _git(repo, "checkout", "-b", "feature")
    auth = repo / "src" / "auth"
    auth.mkdir(parents=True)
    (auth / "login.py").write_text("def login(): pass\n")
    _git(repo, "add", "src/auth/login.py")
    _git(repo, "commit", "-m", "add login")
    record = passing_record(
        repo,
        goal="rename a local helper for clarity",
        risk_tier="low",
        task_class="small",
        status="done",
        commands_run=[{"cmd": "read", "class": "lint", "result": "pass", "evidence": "looks good"}],
        validation_contract=None,
        independent_review=None,
        completion_record=None,
        repo_map={"entry_points": [], "likely_files": [], "callers_checked": [], "tests": []},
        plan=[],
        review_findings=[],
    )
    path = write_record(repo, record)
    # Deliberately NO --base: the auto default must see the committed diff.
    code, out, err = run_cli("verify-gates", str(path), "--against-diff", cwd=str(repo))
    ok = code == 1 and "diff-derived risk floor" in (out + err).lower()
    return ok, f"exit={code}; output={ (out + err).strip()[:200]!r}"


def case_honest_committer_no_phantom(tmp: Path) -> tuple[bool, str]:
    """Honest committer (1.1): status done with a CLEAN tree and committed work
    must NOT fire phantom-completion — the auto base keeps the committed diff
    visible instead of reading an empty diff as a lie."""
    repo = make_repo(tmp)
    base_branch = _default_branch(repo)
    _git(repo, "checkout", "-b", "feature")
    billing = repo / "src" / "billing"
    billing.mkdir(parents=True)
    (billing / "invoice.py").write_text("def round_total(): return round(sum([]), 2)\n")
    tests = repo / "tests"
    tests.mkdir(parents=True)
    (tests / "test_invoice.py").write_text("def test_round(): assert True\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "rounding work")
    attested_hash = qlreal.diff_sha256(base_branch, cwd=repo)
    record = passing_record(
        repo,
        independent_review={
            "reviewer": "agent-b",
            "verdict": "approve",
            "fresh_context": True,
            "patched": False,
            "findings": [],
            "diff_sha256": attested_hash,
        },
        completion_record=_completion(files=["src/billing/invoice.py", "tests/test_invoice.py"]),
    )
    path = write_record(repo, record)
    code, out, err = run_cli("verify-gates", str(path), "--against-diff", cwd=str(repo))
    combined = (out + err).lower()
    ok = code == 0 and "phantom completion" not in combined
    return ok, f"exit={code}; output={ (out + err).strip()[:200]!r}"


def case_deleted_test_file_blocks_at_medium(tmp: Path) -> tuple[bool, str]:
    """Hard rule 6 depth (1.5): deleting a test file nets out test declarations
    and must block at medium."""
    repo = make_repo(tmp)
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_calc.py").write_text(
        "def test_a():\n    assert 1 == 1\n\ndef test_b():\n    assert 2 == 2\n"
    )
    _git(repo, "add", "tests/test_calc.py")
    _git(repo, "commit", "-m", "add tests")
    (tests / "test_calc.py").unlink()
    record = passing_record(repo, completion_record=_completion(files=["tests/test_calc.py"]))
    path = write_record(repo, record)
    code, out, err = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
    ok = code == 1 and "net test-declaration loss" in (out + err)
    return ok, f"exit={code}; output={ (out + err).strip()[:200]!r}"


def case_gutted_assertions_flagged(tmp: Path) -> tuple[bool, str]:
    """Hard rule 6 depth (1.5): replacing strong assertions with one weak one
    (net assertion loss) is flagged at medium."""
    repo = make_repo(tmp)
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_calc.py").write_text(
        "def test_total():\n"
        "    assert calc(1) == 1\n"
        "    assert calc(2) == 2\n"
        "    assert calc(3) == 3\n"
    )
    _git(repo, "add", "tests/test_calc.py")
    _git(repo, "commit", "-m", "add tests")
    (tests / "test_calc.py").write_text(
        "def test_total():\n    assert calc(3) is not None\n"
    )
    record = passing_record(repo, completion_record=_completion(files=["tests/test_calc.py"]))
    path = write_record(repo, record)
    code, out, err = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
    ok = code == 1 and "net assertion loss" in (out + err)
    return ok, f"exit={code}; output={ (out + err).strip()[:200]!r}"


def case_test_move_stays_green(tmp: Path) -> tuple[bool, str]:
    """Hard rule 6 depth (1.5): a legitimate test MOVE (deleted from one test
    file, equivalent adds in another in the same diff) nets to zero and stays
    silent — the netting is diff-level, not per-file."""
    repo = make_repo(tmp)
    tests = repo / "tests"
    tests.mkdir()
    body = (
        "def test_a():\n    assert calc(1) == 1\n\n"
        "def test_b():\n    assert calc(2) == 2\n"
    )
    (tests / "test_a.py").write_text(body)
    _git(repo, "add", "tests/test_a.py")
    _git(repo, "commit", "-m", "add tests")
    (tests / "test_a.py").unlink()
    (tests / "test_b.py").write_text(body)
    _git(repo, "add", "-A")  # stage the move so the diff shows both sides
    record = passing_record(
        repo,
        completion_record=_completion(files=["tests/test_a.py", "tests/test_b.py"]),
    )
    path = write_record(repo, record)
    code, out, err = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
    combined = out + err
    ok = code == 0 and "net test-declaration loss" not in combined and "net assertion loss" not in combined
    return ok, f"exit={code}; output={combined.strip()[:200]!r}"


def case_under_fanning_advisory(tmp: Path) -> tuple[bool, str]:
    """Under-fanning (1.5): a medium diff of one new 400-line source file draws
    the advisory in `verify`; a modular diff of the same size stays silent."""
    def build(name: str, files: dict[str, int]) -> tuple[Path, Path]:
        repo = tmp / name
        repo.mkdir()
        _git(repo, "init")
        _git(repo, "config", "user.email", "eval@example.com")
        _git(repo, "config", "user.name", "eval")
        (repo / "README.md").write_text("# t\n")
        _git(repo, "add", "README.md")
        _git(repo, "commit", "-m", "base")
        for fname, lines in files.items():
            (repo / fname).write_text("".join(f"x{i} = {i}\n" for i in range(lines)))
            _git(repo, "add", fname)
        record = passing_record(repo, completion_record=_completion(files=list(files)))
        return repo, write_record(repo, record)

    mono_repo, mono_rec = build("mono", {"big.py": 400})
    code_m, out_m, err_m = run_cli("verify", str(mono_rec), cwd=str(mono_repo))
    mono_warns = "under-fanning" in (out_m + err_m)

    mod_repo, mod_rec = build("modular", {"part_a.py": 250, "part_b.py": 250})
    code_d, out_d, err_d = run_cli("verify", str(mod_rec), cwd=str(mod_repo))
    modular_silent = "under-fanning" not in (out_d + err_d)

    ok = mono_warns and modular_silent
    return ok, f"mono(exit={code_m},warns={mono_warns}); modular(exit={code_d},silent={modular_silent})"


def case_plan_mention_case_insensitive(tmp: Path) -> tuple[bool, str]:
    """Scope integrity (1.6): a plan that names Button.tsx must map the changed
    file regardless of case — the plan text is lowercased, so the path side
    must be lowercased too."""
    repo = make_repo(tmp)
    comp = repo / "src" / "components"
    comp.mkdir(parents=True)
    (comp / "Button.tsx").write_text("export const Button = () => null;\n")
    record = passing_record(
        repo,
        plan=["edit src/components/Button.tsx to add the icon variant"],
    )
    path = write_record(repo, record)
    code, out, err = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
    combined = (out + err).lower()
    ok = code == 0 and "scope integrity" not in combined
    return ok, f"exit={code}; output={ (out + err).strip()[:200]!r}"


def case_mapped_file_does_not_whitelist_subtree(tmp: Path) -> tuple[bool, str]:
    """Scope integrity (1.6): one mapped file whitelists only its OWN directory
    (single level) — a file deeper in the subtree is still unmapped."""
    repo = make_repo(tmp)
    a = repo / "src" / "a"
    (a / "deep").mkdir(parents=True)
    (a / "y.py").write_text("y = 1\n")          # sibling of the mapped file: allowed
    (a / "deep" / "z.py").write_text("z = 1\n")  # subtree: must be flagged
    record = passing_record(repo, completion_record=_completion(files=["src/a/x.py"]))
    path = write_record(repo, record)
    code, out, err = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
    combined = out + err
    flagged_subtree = "scope integrity" in combined.lower() and "src/a/deep/z.py" in combined
    sibling_allowed = "y.py" not in combined
    ok = code == 1 and flagged_subtree and sibling_allowed
    return ok, f"exit={code}; subtree_flagged={flagged_subtree}; sibling_allowed={sibling_allowed}"


def case_bugfix_keywords_word_boundary(tmp: Path) -> tuple[bool, str]:
    """Bugfix detector (1.6): 'debugging' must not trigger via the 'bug'
    substring; a goal saying 'fix' (no 'bug' word) must trigger."""
    def run_goal(name: str, goal: str) -> tuple[int, str]:
        sub = tmp / name
        sub.mkdir()
        repo = make_repo(sub)
        (repo / "logger.py").write_text("LEVEL = 'debug'\n")
        record = passing_record(
            repo,
            goal=goal,
            completion_record=_completion(files=["logger.py"]),
            plan=["edit logger.py"],
        )
        path = write_record(repo, record)
        code, out, err = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
        return code, out + err

    code_d, out_d = run_goal("dbg", "Improve debugging output in the request logger")
    debugging_clean = "bugfix-test" not in out_d.lower()

    code_f, out_f = run_goal("fix", "fix the off-by-one in pagination totals")
    fix_flagged = code_f == 1 and "bugfix-test" in out_f.lower()

    ok = debugging_clean and fix_flagged
    return ok, f"debugging(exit={code_d},clean={debugging_clean}); fix(exit={code_f},flagged={fix_flagged})"


def case_task_class_medium_low_risk_scope_integrity(tmp: Path) -> tuple[bool, str]:
    """Reality classifier parity: a task_class=medium record must not skip the
    medium+ diff-grounded gates by self-declaring risk_tier=low — an unmapped
    changed file still fires scope integrity (same non-trivial definition as
    the engine's collect_gate_findings)."""
    repo = make_repo(tmp)
    other = repo / "src" / "other"
    other.mkdir(parents=True)
    (other / "surprise.py").write_text("x = 1\n")
    record = passing_record(repo, risk_tier="low", task_class="medium")
    path = write_record(repo, record)
    code, out, err = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
    combined = (out + err).lower()
    ok = code == 1 and "scope integrity" in combined and "surprise.py" in combined
    return ok, f"exit={code}; output={ (out + err).strip()[:200]!r}"


def case_bugfix_fixture_not_bugfix(tmp: Path) -> tuple[bool, str]:
    """Bugfix inflections: 'add a test fixture' must NOT trigger bugfix-test
    co-presence (the old greedy \\w* suffix matched 'fixture'); an explicit
    'fix the rounding' goal still fires."""
    def run_goal(name: str, goal: str) -> tuple[int, str]:
        sub = tmp / name
        sub.mkdir()
        repo = make_repo(sub)
        (repo / "loader.py").write_text("DATA = []\n")
        record = passing_record(
            repo,
            goal=goal,
            completion_record=_completion(files=["loader.py"]),
            plan=["edit loader.py"],
        )
        path = write_record(repo, record)
        code, out, err = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
        return code, out + err

    code_x, out_x = run_goal("fixture", "add a test fixture for the invoice loader")
    fixture_clean = "bugfix-test" not in out_x.lower()

    code_f, out_f = run_goal("fix", "fix the rounding in the invoice loader")
    fix_flagged = code_f == 1 and "bugfix-test" in out_f.lower()

    ok = fixture_clean and fix_flagged
    return ok, f"fixture(exit={code_x},clean={fixture_clean}); fix(exit={code_f},flagged={fix_flagged})"


def case_no_origin_auto_base_defaults_to_head(tmp: Path) -> tuple[bool, str]:
    """No-origin repos (2.2b): when no origin/* rung resolves and the ladder
    would fall through to the empty tree, the LOCAL auto default becomes HEAD
    with a one-line advisory — diffing the whole repository forever poisoned
    day one. Commit-first evasion is CI's job by doctrine: under
    --require-terminal the empty-tree fallback remains, as a loud blocking
    finding instead of a note."""
    repo = make_repo(tmp)
    _git(repo, "branch", "-m", "trunk")  # no main/master anywhere
    committed = repo / "src" / "auth"
    committed.mkdir(parents=True)
    (committed / "login.py").write_text("def login(): pass\n")
    _git(repo, "add", "src/auth/login.py")
    _git(repo, "commit", "-m", "add login")
    # Work in flight (uncommitted) stays visible against the HEAD default.
    invoice = repo / "src" / "invoice"
    invoice.mkdir(parents=True)
    (invoice / "round.py").write_text("def round_total(): return 0\n")
    record = passing_record(
        repo,
        completion_record=_completion(files=["src/invoice/round.py"]),
    )
    path = write_record(repo, record)
    # Deliberately NO --base: the auto default must be HEAD with the note.
    code, out, err = run_cli("verify-gates", str(path), "--against-diff", cwd=str(repo))
    combined = out + err
    noted = "no origin baseline" in combined
    committed_invisible = "diff-derived risk floor" not in combined.lower()
    local_ok = code == 0 and noted and committed_invisible

    # CI anchor: verify --require-terminal keeps the empty tree and the
    # unresolvable-baseline hint lands in Findings (Overall: FAIL).
    code_ci, out_ci, err_ci = run_cli(
        "verify", str(path), "--require-terminal", cwd=str(repo)
    )
    ci_combined = out_ci + err_ci
    ci_empty_tree = "4b825dc642cb6eb9a060e54bf8d69288fbee4904" in ci_combined
    ci_blocks = code_ci != 0 and "empty tree" in ci_combined and "Overall: FAIL" in ci_combined
    ok = local_ok and ci_empty_tree and ci_blocks
    return ok, (
        f"local(exit={code},noted={noted},committed_invisible={committed_invisible}); "
        f"ci(exit={code_ci},empty_tree={ci_empty_tree},blocks={ci_blocks})"
    )


def case_local_main_auto_base_defaults_to_head(tmp: Path) -> tuple[bool, str]:
    """Auto-base on a local-only main/master (no remote) whose merge-base with
    HEAD IS HEAD (2.2b): the local default becomes HEAD with the no-origin
    advisory — committed work is CI's job (--require-terminal keeps the empty
    tree there). Contrast case_committed_work_still_diffed, where the local
    branch diverges from main/master and the merge-base default still sees the
    committed diff."""
    repo = make_repo(tmp)  # git init defaults to main/master, no remote
    auth = repo / "src" / "auth"
    auth.mkdir(parents=True)
    (auth / "login.py").write_text("def login(token): return token\n")
    _git(repo, "add", "src/auth/login.py")
    _git(repo, "commit", "-m", "add auth login")  # committed; HEAD == local main
    invoice = repo / "src" / "invoice"
    invoice.mkdir(parents=True)
    (invoice / "round.py").write_text("def round_total(): return 0\n")  # in flight
    record = passing_record(
        repo,
        completion_record=_completion(files=["src/invoice/round.py"]),
    )
    path = write_record(repo, record)
    code, out, err = run_cli("verify-gates", str(path), "--against-diff", cwd=str(repo))
    combined = out + err
    noted = "no origin baseline" in combined
    in_flight_visible_clean = code == 0  # uncommitted work diffs cleanly vs HEAD
    committed_invisible = "diff-derived risk floor" not in combined.lower()

    code_ci, out_ci, err_ci = run_cli("verify", str(path), "--require-terminal", cwd=str(repo))
    ci_combined = out_ci + err_ci
    ci_empty_tree = "4b825dc642cb6eb9a060e54bf8d69288fbee4904" in ci_combined
    ci_blocks = code_ci != 0 and "empty tree" in ci_combined
    ok = in_flight_visible_clean and noted and committed_invisible and ci_empty_tree and ci_blocks
    return ok, (
        f"local(exit={code},noted={noted},committed_invisible={committed_invisible}); "
        f"ci(exit={code_ci},empty_tree={ci_empty_tree},blocks={ci_blocks})"
    )


def case_untracked_symlink_not_disclosed(tmp: Path) -> tuple[bool, str]:
    """The untracked pseudo-diff must NOT follow a symlink: reading its target
    would disclose a file outside the tree through render-prompt. It is
    represented by its link value, and the outside content never appears."""
    repo = make_repo(tmp)
    secret = tmp / "outside-secret.txt"
    secret.write_text("SUPER_SECRET_TOKEN_VALUE\n")
    link = repo / "link.txt"
    try:
        link.symlink_to(secret)
    except (OSError, NotImplementedError) as exc:
        return True, f"symlinks unsupported here ({exc.__class__.__name__}); skipped"
    patch = qlreal.diff_patch("HEAD", cwd=repo, exclude_record_dir=True)
    disclosed = "SUPER_SECRET_TOKEN_VALUE" in patch
    represented = "link.txt" in patch and "symlink ->" in patch
    ok = (not disclosed) and represented
    return ok, f"disclosed={disclosed}; represented={represented}"


def case_attest_covers_untracked_content(tmp: Path) -> tuple[bool, str]:
    """Canonical diff covers untracked files: a new (never git-added) source
    file changed AFTER attestation must stale the review — with a tracked-only
    hash the reviewer could approve without the file pinning anything."""
    repo = make_repo(tmp)
    (repo / "newmod.py").write_text("def feature():\n    return 1\n")  # untracked
    review = {"reviewer": "agent-b", "verdict": "approve", "fresh_context": True, "patched": False}
    review_path = repo / "review.json"
    review_path.write_text(json.dumps(review))
    code_a, out_a, err_a = run_cli("attest-review", str(review_path), "--base", "HEAD", cwd=str(repo))
    try:
        attested = json.loads(out_a)
    except json.JSONDecodeError:
        return False, f"attest output not JSON (exit={code_a}): {(out_a + err_a)[:120]!r}"
    # The untracked file changes after the review was attested.
    (repo / "newmod.py").write_text("def feature():\n    return 2  # changed\n")
    record = passing_record(
        repo,
        independent_review=dict(attested),
        completion_record=_completion(files=["newmod.py", "review.json"]),
    )
    path = write_record(repo, record)
    code, out, err = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
    combined = (out + err).lower()
    ok = code == 1 and "review freshness" in combined and "stale" in combined
    return ok, f"attest_exit={code_a}; verify_exit={code}; output={ (out + err).strip()[:200]!r}"


def case_empty_diff_freshness_is_na(tmp: Path) -> tuple[bool, str]:
    """An empty current diff (e.g. after the reviewed branch is merged and the
    record's base == HEAD) means there is nothing under review against this
    base — freshness is N/A, not stale. Reproduces the v6.0.0 post-merge bug
    where the shipped tag failed its own verify."""
    repo = make_repo(tmp)
    # Attest a review against HEAD while the tree is clean: hash of an empty diff.
    review = {"reviewer": "agent-b", "verdict": "approve", "fresh_context": True, "patched": False}
    rp = repo / "review.json"; rp.write_text(json.dumps(review))
    # Give the record a hash that will NOT match if freshness runs, to prove the
    # empty-diff branch skips the check rather than matching by luck.
    record = passing_record(repo)
    record["independent_review"] = {**review, "diff_sha256": "sha256:" + "de" * 32}
    record["security_review"] = {**review, "diff_sha256": "sha256:" + "ad" * 32}
    record["risk_tier"] = "high"; record["security_sensitive"] = True
    # Clean tree -> git diff HEAD is empty.
    _git(repo, "add", "-A"); _git(repo, "commit", "-m", "clean")
    path = write_record(repo, record)
    code, out, err = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
    combined = (out + err).lower()
    ok = "review freshness" not in combined  # freshness must be N/A on an empty diff
    return ok, f"exit={code}; freshness_flagged={'review freshness' in combined}; out={combined.strip()[:160]!r}"


def case_security_review_freshness_checked(tmp: Path) -> tuple[bool, str]:
    """The freshness gate must bind security_review to the diff, not only
    independent_review — a stale security approval at a risk boundary is the
    exact hole the gate exists to close. With a NON-empty diff and a bogus
    security_review hash, verify-gates must flag it."""
    repo = make_repo(tmp)
    (repo / "src").mkdir()
    (repo / "src" / "mod.py").write_text("x = 1\n")  # non-empty diff
    review = {"reviewer": "agent-b", "verdict": "approve", "fresh_context": True, "patched": False}
    rp = repo / "review.json"; rp.write_text(json.dumps(review))
    code_a, out_a, _ = run_cli("attest-review", str(rp), "--base", "HEAD", cwd=str(repo))
    try:
        good = json.loads(out_a)
    except json.JSONDecodeError:
        return False, f"attest not JSON: {out_a[:120]!r}"
    record = passing_record(
        repo, risk_tier="high", security_sensitive=True,
        independent_review=dict(good),  # correctly attested
        security_review={**review, "diff_sha256": "sha256:" + "00" * 32},  # bogus
        completion_record=_completion(files=["src/mod.py", "review.json"]),
    )
    path = write_record(repo, record)
    code, out, err = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
    combined = (out + err).lower()
    ok = code == 1 and "security_review.diff_sha256" in combined and "stale" in combined
    return ok, f"exit={code}; out={combined.strip()[:200]!r}"


def case_render_prompt_literal_token_survives(tmp: Path) -> tuple[bool, str]:
    """render-prompt substitutes template tokens in ONE pass: a literal
    '{evidence}' inside the diff must survive untouched, not be recursively
    replaced by the evidence table."""
    repo = make_repo(tmp)
    (repo / "README.md").write_text("# test\nmarker {evidence} stays literal\n")
    record = passing_record(repo)
    path = write_record(repo, record)
    code, out, err = run_cli(
        "render-prompt", "--role", "reviewer", "--record", str(path), "--base", "HEAD",
        cwd=str(repo),
    )
    literal_survives = "marker {evidence} stays literal" in out
    evidence_table = "| cmd | class | result | evidence |" in out
    ok = code == 0 and literal_survives and evidence_table
    return ok, f"exit={code}; literal_survives={literal_survives}; evidence_table={evidence_table}"


def case_render_prompt_substitutes(tmp: Path) -> tuple[bool, str]:
    """render-prompt (2.2): the rendered reviewer prompt carries the real
    contract, diff, and evidence — no {contract}/{diff}/{evidence} placeholder
    survives."""
    repo = make_repo(tmp)
    (repo / "README.md").write_text("# test\nchanged line\n")
    record = passing_record(repo)
    path = write_record(repo, record)
    code, out, err = run_cli(
        "render-prompt", "--role", "reviewer", "--record", str(path), "--base", "HEAD",
        cwd=str(repo),
    )
    no_placeholders = all(p not in out for p in ("{contract}", "{diff}", "{evidence}"))
    has_contract = "Add rounding to the total calculation" in out
    has_evidence = "| cmd | class | result | evidence |" in out and "pytest" in out
    has_diff = "changed line" in out
    ok = code == 0 and no_placeholders and has_contract and has_evidence and has_diff
    return ok, (
        f"exit={code}; no_placeholders={no_placeholders}; contract={has_contract}; "
        f"evidence={has_evidence}; diff={has_diff}; err={err.strip()[:80]!r}"
    )


def case_base_env_and_config_precedence(tmp: Path) -> tuple[bool, str]:
    """Default-base precedence (2.2a): --base flag > QUALITY_LOOP_BASE env >
    config "base" > the built-in ladder. The config key seeds the ladder; the
    env var beats the config key."""
    repo = make_repo(tmp)
    _git(repo, "branch", "baseline")  # pin the initial commit
    auth = repo / "src" / "auth"
    auth.mkdir(parents=True)
    (auth / "login.py").write_text("def login(): pass\n")
    _git(repo, "add", "src/auth/login.py")
    _git(repo, "commit", "-m", "add login")  # committed past the baseline
    (repo / "quality-loop.config.json").write_text(json.dumps({"base": "baseline"}))
    _git(repo, "add", "quality-loop.config.json")
    _git(repo, "commit", "-m", "gate config")
    record = passing_record(
        repo,
        goal="rename a local helper for clarity",
        risk_tier="low",
        task_class="small",
        status="done",
        commands_run=[{"cmd": "read", "class": "lint", "result": "pass", "evidence": "looks good"}],
        validation_contract=None,
        independent_review=None,
        completion_record=None,
        repo_map={"entry_points": [], "likely_files": [], "callers_checked": [], "tests": []},
        plan=[],
        review_findings=[],
    )
    path = write_record(repo, record)
    # No --base, no env: the config "base" seeds the ladder, so the committed
    # auth work is diffed against `baseline` and the risk floor fires.
    code_cfg, out_cfg, err_cfg = run_cli("verify-gates", str(path), "--against-diff", cwd=str(repo))
    config_used = code_cfg == 1 and "diff-derived risk floor" in (out_cfg + err_cfg).lower()

    # Env beats config: seeding with the checked-out branch makes the
    # merge-base HEAD itself, so the default degrades to HEAD (with the
    # advisory) and the committed auth work is NOT in the local diff.
    branch = _default_branch(repo)
    code_env, out_env, err_env = run_cli(
        "verify-gates", str(path), "--against-diff", cwd=str(repo),
        env={"QUALITY_LOOP_BASE": branch},
    )
    env_combined = out_env + err_env
    env_won = "diff-derived risk floor" not in env_combined.lower() and "no origin baseline" in env_combined

    ok = config_used and env_won
    return ok, f"config_used(exit={code_cfg})={config_used}; env_beats_config(exit={code_env})={env_won}"


def case_gate_config_markers_and_high_risk(tmp: Path) -> tuple[bool, str]:
    """The two remaining gate-config keys (3.2), additive only: tests.path_markers
    teaches the bugfix-test gate a repo's real test layout; high_risk_paths
    forces the diff-derived floor on repo-specific boundaries the built-ins
    cannot know."""
    # A: without config, a bugfix whose tests live in checks/ draws the
    # co-presence finding; with tests.path_markers ["checks/"] it passes.
    sub_a = tmp / "markers"
    sub_a.mkdir()
    repo_a = make_repo(sub_a)
    (repo_a / "src").mkdir()
    (repo_a / "src" / "round.py").write_text("def round_total(): return 0\n")
    checks = repo_a / "checks"
    checks.mkdir()
    (checks / "check_round.py").write_text("def check(): assert round_total() == 0\n")
    record_a = passing_record(
        repo_a,
        goal="Fix the rounding bug in the total calculation",
        completion_record=_completion(files=["src/round.py", "checks/check_round.py"]),
        plan=["edit src/round.py and checks/check_round.py"],
    )
    path_a = write_record(repo_a, record_a)
    code_1, out_1, err_1 = run_cli("verify-gates", str(path_a), "--against-diff", "--base", "HEAD", cwd=str(repo_a))
    without_cfg_flagged = code_1 == 1 and "bugfix-test" in (out_1 + err_1).lower()

    (repo_a / "quality-loop.config.json").write_text(
        json.dumps({"tests": {"path_markers": ["checks/"]}})
    )
    _git(repo_a, "add", "quality-loop.config.json")
    _git(repo_a, "commit", "-m", "gate config")
    # Re-attest: committing the config changed nothing in the diff vs HEAD,
    # but recompute defensively so the case pins only the marker behavior.
    record_a["independent_review"]["diff_sha256"] = qlreal.diff_sha256("HEAD", cwd=repo_a)
    path_a = write_record(repo_a, record_a)
    code_2, out_2, err_2 = run_cli("verify-gates", str(path_a), "--against-diff", "--base", "HEAD", cwd=str(repo_a))
    with_cfg_clean = code_2 == 0

    # B: high_risk_paths ["identity"] forces the floor on identity/ paths.
    sub_b = tmp / "highrisk"
    sub_b.mkdir()
    repo_b = make_repo(sub_b)
    (repo_b / "quality-loop.config.json").write_text(json.dumps({"high_risk_paths": ["identity"]}))
    _git(repo_b, "add", "quality-loop.config.json")
    _git(repo_b, "commit", "-m", "gate config")
    identity = repo_b / "identity"
    identity.mkdir()
    # Deliberately no boundary keyword in path/plan (no "login"/"auth"): only
    # the config-taught path may force the floor here.
    (identity / "profile.py").write_text("def display_name(): return ''\n")
    record_b = passing_record(
        repo_b,
        completion_record=_completion(files=["identity/profile.py"]),
        plan=["edit identity/profile.py"],
    )
    path_b = write_record(repo_b, record_b)
    code_3, out_3, err_3 = run_cli("verify-gates", str(path_b), "--against-diff", "--base", "HEAD", cwd=str(repo_b))
    floor_forced = code_3 == 1 and "diff-derived risk floor" in (out_3 + err_3).lower()

    ok = without_cfg_flagged and with_cfg_clean and floor_forced
    return ok, (
        f"no_cfg(exit={code_1},flagged={without_cfg_flagged}); "
        f"markers(exit={code_2},clean={with_cfg_clean}); "
        f"high_risk(exit={code_3},forced={floor_forced})"
    )


def case_waiver_must_cite_passing_command(tmp: Path) -> tuple[bool, str]:
    """Waivers cite evidence (3.3): a bugfix test waiver disarms the gate only
    when its text names a pass-labeled commands_run cmd. Free text (or a bare
    `true`) blocks at medium+ and degrades to a note below medium."""
    repo = make_repo(tmp)
    (repo / "src").mkdir()
    (repo / "src" / "round.py").write_text("def round_total(): return 0\n")

    uncited = passing_record(
        repo,
        goal="Fix the rounding bug in the total calculation",
        bugfix_test_waiver=True,  # truthy, cites nothing
        completion_record=_completion(files=["src/round.py"]),
        plan=["edit src/round.py"],
    )
    path = write_record(repo, uncited)
    code_u, out_u, err_u = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
    combined_u = out_u + err_u
    uncited_blocks = code_u == 1 and "waiver must cite a recorded passing command" in combined_u

    cited = dict(uncited)
    cited["bugfix_test_waiver"] = "regression covered by the recorded pytest run (pytest)"
    path = write_record(repo, cited)
    code_c, out_c, err_c = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
    cited_passes = code_c == 0

    low = passing_record(
        repo,
        goal="fix the rounding in the helper",
        risk_tier="low",
        task_class="small",
        status="done",
        acceptance_criteria=["rounding fixed"],
        bugfix_test_waiver=True,
        commands_run=[{"cmd": "read", "class": "lint", "result": "pass", "evidence": "ok"}],
        validation_contract=None,
        independent_review=None,
        completion_record=None,
        repo_map={"entry_points": [], "likely_files": ["src/round.py"], "callers_checked": [], "tests": []},
        plan=["edit src/round.py"],
        review_findings=[],
    )
    path = write_record(repo, low)
    code_l, out_l, err_l = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
    combined_l = out_l + err_l
    low_warns_only = code_l == 0 and "waiver must cite" in combined_l and "note:" in combined_l

    ok = uncited_blocks and cited_passes and low_warns_only
    return ok, (
        f"uncited(exit={code_u},blocks={uncited_blocks}); cited(exit={code_c},passes={cited_passes}); "
        f"low(exit={code_l},warns_only={low_warns_only})"
    )


def case_bare_star_allowlist_authorizes_nothing(tmp: Path) -> tuple[bool, str]:
    """1.2c: an allowlist pattern that matches everything (bare *, ?, blanks)
    authorizes nothing — Stop-time auto-execution must not be a blank check —
    and each such line is named in a warning without failing an otherwise
    valid run."""
    repo = make_repo(tmp)
    write_allowlist(repo, ["*"])
    record = passing_record(
        repo,
        commands_run=[{"cmd": "echo hi", "class": "unit", "result": "pass", "evidence": "ok"}],
    )
    path = write_record(repo, record)
    code, out, err = run_cli("run-evidence", str(path), cwd=str(repo))
    combined = out + err
    star_refused = code == 1 and "not on allowlist" in combined.lower()
    warned = "allowlist line 1" in combined and "matches every command" in combined

    # A real pattern alongside the degenerate line still authorizes its
    # command; the warning names the degenerate line without failing the run.
    sub = tmp / "mixed"
    sub.mkdir()
    repo2 = make_repo(sub)
    write_allowlist(repo2, ["*", f"{sys.executable}*"])
    cmd = f"{sys.executable} -c pass"
    record2 = passing_record(
        repo2,
        commands_run=[{"cmd": cmd, "class": "unit", "result": "pass", "evidence": "ok"}],
    )
    path2 = write_record(repo2, record2)
    code2, out2, err2 = run_cli("run-evidence", str(path2), cwd=str(repo2))
    combined2 = out2 + err2
    real_pattern_ok = code2 == 0 and "allowlist line 1" in combined2

    ok = star_refused and warned and real_pattern_ok
    return ok, (
        f"star(exit={code},refused={star_refused},warned={warned}); "
        f"mixed(exit={code2},ok={real_pattern_ok})"
    )


def case_install_manifest_paths_are_scaffolding(tmp: Path) -> tuple[bool, str]:
    """2.2c: install-manifest-listed paths are CQL's own scaffolding for
    scope-integrity and the diff-size advisory (membership-based — the
    manifest records no hashes), so a fresh install does not read as a
    59-file unmapped change. Without the manifest the same paths are flagged."""
    repo = make_repo(tmp)
    scripts = repo / "scripts"
    scripts.mkdir()
    (scripts / "quality_loop.py").write_text("# shipped helper (fake)\n")
    (repo / "SKILL.md").write_text("# shipped skill (fake)\n")
    (repo / "src").mkdir()
    (repo / "src" / "round.py").write_text("def round_total(): return 0\n")
    manifest_path = repo / ".quality-loop" / "install-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({
        "version": 1,
        "host": "claude-code",
        "files": ["scripts/quality_loop.py", "SKILL.md"],
        "preexisting": [],
        "hook_groups": [],
    }))
    record = passing_record(
        repo,
        completion_record=_completion(files=["src/round.py"]),
        plan=["edit src/round.py"],
    )
    path = write_record(repo, record)
    code, out, err = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
    manifest_exempt = code == 0 and "scope integrity" not in (out + err).lower()

    code_da, out_da, _ = run_cli("diff-audit", "--base", "HEAD", cwd=str(repo))
    try:
        advisory = json.loads(out_da).get("advisory", [])
    except json.JSONDecodeError:
        advisory = None
    untracked_note = next((a for a in advisory or [] if "untracked file(s) included" in a), "")
    audit_excludes = advisory is not None and "scripts/quality_loop.py" not in untracked_note

    manifest_path.unlink()  # .quality-loop/ is hash-excluded, so freshness holds
    code_no, out_no, err_no = run_cli("verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
    combined_no = out_no + err_no
    without_manifest_flagged = (
        code_no == 1
        and "scope integrity" in combined_no.lower()
        and "scripts/quality_loop.py" in combined_no
    )

    # Shape boundary: the manifest is agent-writable checkout data, so listing
    # an arbitrary CONSUMER source path must exempt nothing — only CQL's own
    # shipped path shapes qualify. An unmapped src/ file stays a scope error
    # even when the manifest names it.
    # Put the file in a directory NOT already whitelisted by a mapped file
    # (src/ is mapped via src/round.py's one-level dir whitelist), so the only
    # thing that could exempt it is the manifest — which must not, for a
    # consumer path shape.
    (repo / "lib").mkdir()
    (repo / "lib" / "sneaky.py").write_text("def backdoor(): pass\n")
    manifest_path.write_text(json.dumps({
        "version": 1,
        "host": "claude-code",
        "files": ["scripts/quality_loop.py", "SKILL.md", "lib/sneaky.py"],
        "preexisting": [],
        "hook_groups": [],
    }))
    code_shape, out_shape, err_shape = run_cli(
        "verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo))
    combined_shape = out_shape + err_shape
    consumer_path_not_exempt = (
        code_shape == 1
        and "scope integrity" in combined_shape.lower()
        and "lib/sneaky.py" in combined_shape
        and "scripts/quality_loop.py" not in combined_shape
    )
    (repo / "lib" / "sneaky.py").unlink()

    ok = manifest_exempt and audit_excludes and without_manifest_flagged and consumer_path_not_exempt
    return ok, (
        f"with_manifest(exit={code},exempt={manifest_exempt}); audit_excludes={audit_excludes}; "
        f"without(exit={code_no},flagged={without_manifest_flagged}); "
        f"consumer_path_not_exempt={consumer_path_not_exempt}"
    )


_GO_TEST_FULL = (
    "package calc\n\nimport \"testing\"\n\n"
    "func TestAdd(t *testing.T) {\n"
    "\tif Add(1, 2) != 3 {\n\t\tt.Errorf(\"bad add\")\n\t}\n"
    "\tif Add(0, 0) != 0 {\n\t\tt.Fatalf(\"bad zero\")\n\t}\n}\n\n"
    "func TestSub(t *testing.T) {\n"
    "\tif Sub(2, 1) != 1 {\n\t\tt.Error(\"bad sub\")\n\t}\n}\n"
)
_RUST_TEST_FULL = (
    "#[test]\nfn adds() {\n    assert_eq!(add(1, 2), 3);\n    assert!(add(0, 0) == 0);\n}\n\n"
    "#[test]\nfn subs() {\n    assert_ne!(sub(2, 1), 0);\n}\n"
)


def case_multilang_test_lexicon(tmp: Path) -> tuple[bool, str]:
    """3.1: Hard Rule 6 sees non-Python/JS test files. Gutted Go and Rust test
    files fire net-declaration/assertion loss at medium; a Go test MOVE that
    keeps assertions stays green; Go t.Skip and Rust #[ignore] additions fire
    test-weakening; Java/Ruby/C# patterns are pinned at the function level."""
    def build(name: str, rel: str, full: str) -> Path:
        sub = tmp / name
        sub.mkdir()
        repo = make_repo(sub)
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(full)
        _git(repo, "add", rel)
        _git(repo, "commit", "-m", "add tests")
        return repo

    def gates(repo: Path, files: list[str]) -> tuple[int, str]:
        record = passing_record(repo, completion_record=_completion(files=files))
        path = write_record(repo, record)
        code, out, err = run_cli(
            "verify-gates", str(path), "--against-diff", "--base", "HEAD", cwd=str(repo)
        )
        return code, out + err

    # Gutted Go test file: fewer TestXxx funcs, zero t.Errorf/t.Fatalf.
    repo_go = build("go", "calc_test.go", _GO_TEST_FULL)
    (repo_go / "calc_test.go").write_text(
        "package calc\n\nimport \"testing\"\n\nfunc TestAdd(t *testing.T) {\n\t_ = Add(1, 2)\n}\n"
    )
    code_go, out_go = gates(repo_go, ["calc_test.go"])
    go_gutted = code_go == 1 and "net test-declaration loss" in out_go and "net assertion loss" in out_go

    # Gutted Rust test file: the assert!/assert_eq! macros' bang defeated the
    # old regex — this pins that they now count.
    repo_rs = build("rust", "tests/calc.rs", _RUST_TEST_FULL)
    (repo_rs / "tests" / "calc.rs").write_text(
        "#[test]\nfn adds() {\n    let _ = add(1, 2);\n}\n"
    )
    code_rs, out_rs = gates(repo_rs, ["tests/calc.rs"])
    rust_gutted = code_rs == 1 and "net test-declaration loss" in out_rs and "net assertion loss" in out_rs

    # Equivalent modular refactor: the same Go tests move to another test file
    # in the same diff — netting is diff-level, stays green.
    repo_mv = build("gomove", "calc_test.go", _GO_TEST_FULL)
    (repo_mv / "calc_test.go").unlink()
    (repo_mv / "calc_more_test.go").write_text(_GO_TEST_FULL)
    _git(repo_mv, "add", "-A")
    code_mv, out_mv = gates(repo_mv, ["calc_test.go", "calc_more_test.go"])
    move_clean = code_mv == 0 and "net " not in out_mv

    # Added skip markers: Go t.Skip( and Rust #[ignore] are test-weakening.
    repo_skip = build("goskip", "calc_test.go", _GO_TEST_FULL)
    (repo_skip / "calc_test.go").write_text(
        _GO_TEST_FULL.replace(
            "func TestAdd(t *testing.T) {\n",
            "func TestAdd(t *testing.T) {\n\tt.Skip(\"flaky\")\n",
        )
    )
    code_sk, out_sk = gates(repo_skip, ["calc_test.go"])
    go_skip_flagged = code_sk == 1 and "test-weakening" in out_sk

    repo_ig = build("rustignore", "tests/calc.rs", _RUST_TEST_FULL)
    (repo_ig / "tests" / "calc.rs").write_text(
        _RUST_TEST_FULL.replace("#[test]\nfn adds", "#[test]\n#[ignore]\nfn adds", 1)
    )
    code_ig, out_ig = gates(repo_ig, ["tests/calc.rs"])
    rust_ignore_flagged = code_ig == 1 and "test-weakening" in out_ig

    # Function-level pins for the remaining families (patch-shaped input).
    def patch_for(path: str, removed: list[str], added: list[str]) -> str:
        body = "".join(f"-{line}\n" for line in removed) + "".join(f"+{line}\n" for line in added)
        return f"--- a/{path}\n+++ b/{path}\n{body}"

    java_gut = qlcore.test_shrinkage_hits(patch_for(
        "src/test/CalcTest.java",
        ["    @Test", "    void adds() { assertEquals(3, add(1, 2)); }",
         "    @Test", "    void subs() { assertTrue(sub(2, 1) == 1); }"],
        ["    @Test", "    void adds() { add(1, 2); }"],
    ))
    ruby_gut = qlcore.test_shrinkage_hits(patch_for(
        "spec/calc_spec.rb",
        ['  it "adds" do', "    expect(add(1, 2)).to eq(3)", "  end",
         '  it "subs" do', "    expect(sub(2, 1)).to eq(1)", "  end"],
        ['  it "adds" do', "    add(1, 2)", "  end"],
    ))
    csharp_gut = qlcore.test_shrinkage_hits(patch_for(
        "tests/CalcTests.cs",
        ["    [Fact]", "    public void Adds() { Assert.Equal(3, Add(1, 2)); }",
         "    [Fact]", "    public void Subs() { Assert.True(Sub(2, 1) == 1); }"],
        ["    [Fact]", "    public void Adds() { Add(1, 2); }"],
    ))
    weaken_pins = [
        qlcore.test_weakening_hits(patch_for("src/test/CalcTest.java", [], ["    @Disabled"])),
        qlcore.test_weakening_hits(patch_for("spec/calc_spec.rb", [], ['  xit "adds" do'])),
        qlcore.test_weakening_hits(patch_for("tests/CalcTests.cs", [], ['    [Fact(Skip = "slow")]'])),
    ]
    fn_pins = bool(java_gut and ruby_gut and csharp_gut and all(weaken_pins))

    ok = go_gutted and rust_gutted and move_clean and go_skip_flagged and rust_ignore_flagged and fn_pins
    return ok, (
        f"go_gutted={go_gutted}; rust_gutted={rust_gutted}; move_clean={move_clean}; "
        f"go_skip={go_skip_flagged}; rust_ignore={rust_ignore_flagged}; fn_pins={fn_pins} "
        f"(java={bool(java_gut)},ruby={bool(ruby_gut)},csharp={bool(csharp_gut)},weaken={[bool(w) for w in weaken_pins]})"
    )


def _low_risk_done_record() -> dict:
    """A tiny low-risk record that passes the whole verify umbrella: no pass
    commands (run-evidence skipped), string AC (valid at low), no boundary or
    bugfix keywords, terminal status with a non-empty diff (no phantom)."""
    return {
        "task_id": "t-marker",
        "goal": "rename a local helper for clarity",
        "task_class": "small",
        "risk_tier": "low",
        "acceptance_criteria": ["helper renamed"],
        "constraints": [],
        "non_goals": [],
        "assumptions": [],
        "verification_plan": ["manual read-through"],
        "minimality_decision": {"rung": "reuse", "reason": "existing helper covers it"},
        "plan": ["edit src/mod.py"],
        "commands_run": [],
        "open_risks": [],
        "review_findings": [],
        "status": "done",
    }


def case_verify_writes_last_verified_marker(tmp: Path) -> tuple[bool, str]:
    """The verify umbrella writes .quality-loop/last-verified.json ONLY on an
    overall PASS — {diff_sha256 (canonical), base (resolved), status,
    verified_at} — and a failing verify removes any stale marker, so the
    stop-gate fast path can never skip on a diff/status the umbrella did not
    actually pass."""
    repo = make_repo(tmp)
    src = repo / "src"
    src.mkdir()
    (src / "mod.py").write_text("def helper():\n    return 2\n")
    record_path = repo / "record.json"
    record_path.write_text(json.dumps(_low_risk_done_record()))

    code_pass, out_pass, err_pass = run_cli("verify", "record.json", "--base", "HEAD", cwd=str(repo))
    marker_path = repo / ".quality-loop" / "last-verified.json"
    try:
        marker = json.loads(marker_path.read_text())
    except (OSError, json.JSONDecodeError):
        marker = {}
    expected_hash = qlreal.canonical_diff_sha256("HEAD", cwd=repo)
    marker_ok = bool(
        marker.get("diff_sha256") == expected_hash
        and marker.get("base") == "HEAD"
        and marker.get("status") == "done"
        and isinstance(marker.get("verified_at"), str) and marker["verified_at"]
    )
    wrote_on_pass = code_pass == 0 and marker_ok

    # Now a FAILING verify (medium record, no implementer, unallowlisted pass
    # command) must remove the stale marker: absence == "run the full umbrella".
    record_path.write_text(json.dumps(passing_record(repo, implementer=None)))
    code_fail, out_fail, _ = run_cli("verify", "record.json", "--base", "HEAD", cwd=str(repo))
    removed_on_fail = code_fail != 0 and not marker_path.exists()

    ok = wrote_on_pass and removed_on_fail
    return ok, (
        f"pass(exit={code_pass},marker_ok={marker_ok}); "
        f"fail(exit={code_fail},removed={removed_on_fail}); "
        f"marker={marker!r}"[:300]
    )


def case_canonical_diff_sha256_single_source(tmp: Path) -> tuple[bool, str]:
    """canonical_diff_sha256 IS the hash attest-review embeds and freshness
    checks (one implementation), and it stales when untracked content changes."""
    repo = make_repo(tmp)
    (repo / "mod.py").write_text("def helper():\n    return 2\n")
    review_path = repo / "review.json"
    review_path.write_text(json.dumps({"reviewer": "agent-b", "verdict": "approve"}))
    code, out, err = run_cli("attest-review", str(review_path), "--base", "HEAD", cwd=str(repo))
    try:
        attested = json.loads(out)
    except json.JSONDecodeError:
        attested = {}
    canonical = qlreal.canonical_diff_sha256("HEAD", cwd=repo)
    same_impl = (
        code == 0
        and attested.get("diff_sha256") == canonical
        and canonical == qlreal.diff_sha256("HEAD", cwd=repo, exclude_record_dir=True)
    )
    (repo / "extra.py").write_text("x = 1\n")
    stales = qlreal.canonical_diff_sha256("HEAD", cwd=repo) != canonical
    ok = same_impl and stales
    return ok, f"exit={code}; same_impl={same_impl}; stales_on_new_content={stales}"


CASES = [
    ("action.yml python invocations all run the pinned copy", case_action_invocations_are_pinned),
    ("phantom completion (done + empty diff) is caught", case_phantom_completion),
    ("unmapped changed file is caught (scope integrity)", case_unmapped_file),
    ("auth path under a low tier is caught (diff-derived risk floor)", case_auth_path_low_tier),
    ("high-tier changed path forces high gates even from medium", case_high_tier_path_forces_high_from_medium),
    ("missing bugfix test is caught (bugfix-test co-presence)", case_missing_bugfix_test),
    ("stale review hash is caught (review freshness)", case_stale_review_hash),
    ("lying evidence (recorded pass fails on rerun) is caught", case_lying_evidence),
    ("faked RED (command passes at base) is caught by --red-green", case_red_green_catch),
    ("staged secret is caught by diff-audit --staged", case_staged_secret),
    ("attest-review embeds a recomputed diff sha256", case_attest_review_embeds_hash),
    ("scan-text --stdin catches a secret", case_scan_text_secret),
    ("a clean, well-mapped record passes --against-diff", case_clean_record_passes_against_diff),
    ("run-evidence refuses a command not on the allowlist", case_run_evidence_allowlist),
    ("verify umbrella fails when a constituent section fails (verify-gates)", case_verify_umbrella_fails_when_section_fails),
    ("verify in a non-git repo emits a report instead of exit 129", case_verify_in_non_git_repo),
    ("unresolvable --base falls back to a sane ref with a hint (P1.7)", case_unresolvable_base_falls_back_with_hint),
    ("verify AC coverage reads proving_command off object acceptance criteria", case_verify_object_ac_coverage),
    ("record-only trailing change does not stale an attested review", case_record_only_trailing_change_stays_fresh),
    ("init-record scaffolds the run-evidence allowlist", case_init_record_scaffolds_allowlist),
    ("partial scripts/ install fails with an actionable message", case_partial_install_fails_actionably),
    ("softened local gate script passes locally but CI pinned copy still blocks (F1 trust anchor)", case_ci_anchor_defeats_softened_local_script),
    ("verify reports helper-integrity hashes for all five modules", case_verify_reports_helper_integrity),
    ("committed-but-unpushed work is still diffed by the auto default base (commit-first evasion)", case_committed_work_still_diffed),
    ("honest committer: done + clean tree + committed work is not phantom completion", case_honest_committer_no_phantom),
    ("deleted test file blocks at medium (net test-declaration loss)", case_deleted_test_file_blocks_at_medium),
    ("gutted assertions block at medium (net assertion loss)", case_gutted_assertions_flagged),
    ("legit test move (delete + equivalent adds elsewhere) stays green", case_test_move_stays_green),
    ("under-fanned monolith diff draws the advisory; modular diff stays silent", case_under_fanning_advisory),
    ("plan mention maps a changed file case-insensitively (Button.tsx)", case_plan_mention_case_insensitive),
    ("mapped file whitelists its own directory only, not the subtree", case_mapped_file_does_not_whitelist_subtree),
    ("bugfix keywords are word-boundary matched ('debugging' clean, 'fix' fires)", case_bugfix_keywords_word_boundary),
    ("render-prompt substitutes {contract}/{diff}/{evidence} for the reviewer role", case_render_prompt_substitutes),
    ("task_class=medium with risk_tier=low still fires scope integrity (classifier parity)", case_task_class_medium_low_risk_scope_integrity),
    ("'add a test fixture' is not a bugfix; 'fix the rounding' is (explicit inflections)", case_bugfix_fixture_not_bugfix),
    ("no-origin repo: local auto base is HEAD with a note; CI keeps the empty tree", case_no_origin_auto_base_defaults_to_head),
    ("local-only main/master at HEAD: local auto base is HEAD; CI keeps the empty tree", case_local_main_auto_base_defaults_to_head),
    ("default-base precedence: env beats config 'base' beats the ladder", case_base_env_and_config_precedence),
    ("tests.path_markers and high_risk_paths extend the gates additively", case_gate_config_markers_and_high_risk),
    ("bugfix test waiver must cite a recorded passing command", case_waiver_must_cite_passing_command),
    ("bare-* allowlist line authorizes nothing and is named in a warning", case_bare_star_allowlist_authorizes_nothing),
    ("install-manifest paths are scaffolding for scope integrity and audit sizing", case_install_manifest_paths_are_scaffolding),
    ("multi-language test lexicon: gutted Go/Rust tests fire; moves stay green", case_multilang_test_lexicon),
    ("untracked symlink is not followed/disclosed by the canonical diff", case_untracked_symlink_not_disclosed),
    ("untracked file content is pinned by attestation (edit after attest goes stale)", case_attest_covers_untracked_content),
    ("empty current diff makes review freshness N/A, not stale (post-merge)", case_empty_diff_freshness_is_na),
    ("security_review freshness is checked, not only independent_review", case_security_review_freshness_checked),
    ("render-prompt keeps a literal {evidence} token in the diff intact (single pass)", case_render_prompt_literal_token_survives),
    ("verify writes the last-verified marker on PASS and removes it on FAIL", case_verify_writes_last_verified_marker),
    ("canonical_diff_sha256 is the one attest/freshness hash and stales on new content", case_canonical_diff_sha256_single_source),
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
    print(f"\n{total - failures}/{total} reality eval cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
