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

sys.path.insert(0, str(ROOT / "scripts"))
import quality_loop_reality as qlreal  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"


def run_cli(*args: str, cwd: str | None = None, stdin: str | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        input=stdin,
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
        "acceptance_criteria": ["total rounds once"],
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
    repo = make_repo(tmp)
    code, out, err = run_cli(
        "init-record", "--goal", "Fix invoice rounding", "--risk-tier", "medium",
        "--output", "agent-record.json", cwd=str(repo),
    )
    allowlist = repo / ".quality-loop" / "allowed-commands"
    ok = code == 0 and allowlist.is_file() and "allowed-commands" in out
    return ok, f"exit={code}; allowlist_exists={allowlist.is_file()}"


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
    ok = has_section and len(hashes) == 4
    return ok, f"exit={code}; section={has_section}; hashes={len(hashes)}"


CASES = [
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
    ("verify reports helper-integrity hashes for all four modules", case_verify_reports_helper_integrity),
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
