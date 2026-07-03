#!/usr/bin/env python3
"""Reality layer for the Coding Quality Loop — record↔reality verification.

Closes the three "free lies" in v1.4.0 by grounding the record in git:

  1. ``verify-gates --against-diff`` reads the real diff and catches phantom
     completion, unmapped scope, a diff-derived risk floor, missing bugfix
     tests, and stale review hashes.
  2. ``run-evidence`` re-executes recorded ``commands_run``; ``--red-green``
     replays a ``red_green`` command in a worktree at base (expect fail) and at
     HEAD (expect pass), catching a faked RED→GREEN. Worktree unavailable →
     explicit "not proven", never a silent pass.
  3. ``attest-review`` embeds a recomputed ``git diff | sha256`` into the review
     object so review freshness is checkable, not self-attested.

Stdlib-only, portable, no network. Mirrors ``quality_loop_memory.py`` and reuses
``run_git`` / ``redact`` / ``SECRET_PATTERNS`` / ``has_evidence`` / ``load_json``
from ``quality_loop``.

Record schema gains **optional** fields only (``diff_sha256``, ``files_changed``,
``red_green``) — no adopter break.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import quality_loop as ql

# High-tier path components/anchors — a changed *path* matching these forces
# high-risk gates, grounding detect_risk_floor in git rather than prose.
_HIGH_TIER_DIR_COMPONENTS = {
    "auth", "payments", "migrations", "terraform",
}
_HIGH_TIER_FILE_NAMES = {
    # lockfiles
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Pipfile.lock", "go.sum", "Cargo.lock", "Gemfile.lock",
}
_BUGFIX_GOAL_KEYWORDS = ("bug", "broken", "crash", "regression", "defect")
_WAIVER_KEYS = ("test_waiver", "no_test_waiver", "bugfix_test_waiver")


def _git(args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """Run git without raising. Returns (returncode, stdout, stderr)."""
    proc = subprocess.run(
        ["git", *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd) if cwd else None,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _git_or_fail(args: list[str], cwd: Path | None = None) -> str:
    """Run git, printing redacted stderr and exiting on failure (matches ql.run_git)."""
    code, out, err = _git(args, cwd)
    if code != 0:
        print(ql.redact(err.strip()), file=sys.stderr)
        raise SystemExit(code)
    return out


def changed_files(base: str = "HEAD", cwd: Path | None = None) -> list[str]:
    """Tracked changes plus untracked (non-ignored) files relative to base."""
    cwd = cwd or Path.cwd()
    tracked = [
        f.strip()
        for f in _git_or_fail(["diff", "--name-only", base], cwd).splitlines()
        if f.strip()
    ]
    untracked = [
        f.strip()
        for f in _git_or_fail(["ls-files", "--others", "--exclude-standard"], cwd).splitlines()
        if f.strip()
    ]
    # de-dup, preserve order
    seen: set[str] = set()
    files: list[str] = []
    for f in tracked + untracked:
        if f not in seen:
            seen.add(f)
            files.append(f)
    return files


def diff_patch(base: str = "HEAD", cwd: Path | None = None) -> str:
    cwd = cwd or Path.cwd()
    return _git_or_fail(["diff", base], cwd)


def diff_sha256(base: str = "HEAD", cwd: Path | None = None) -> str:
    """sha256 of the current diff (the normalization is the git diff itself)."""
    return hashlib.sha256(diff_patch(base, cwd).encode("utf-8")).hexdigest()


def _path_matches_high_tier(path: str) -> bool:
    name = path.split("/")[-1]
    if name in _HIGH_TIER_FILE_NAMES:
        return True
    if name == ".env" or name.startswith(".env."):
        return True
    for component in path.split("/")[:-1]:
        if component in _HIGH_TIER_DIR_COMPONENTS:
            return True
    return False


def _allowed_paths_and_globs(record: dict[str, Any]) -> tuple[set[str], set[str]]:
    paths: set[str] = set()
    repo_map = record.get("repo_map") or {}
    # likely_files/entry_points are the primary mapped scope; tests and
    # callers_checked are legitimate change targets too, so include them to
    # avoid false-flagging a regression test as "unmapped".
    for key in ("likely_files", "entry_points", "tests", "callers_checked"):
        for entry in repo_map.get(key, []) or []:
            p = str(entry).split(":")[0].strip()
            if p:
                paths.add(p)
    cr = record.get("completion_record")
    if isinstance(cr, dict):
        for f in cr.get("files_changed", []) or []:
            p = str(f).strip()
            if p:
                paths.add(p)
    globs: set[str] = set()
    for p in paths:
        globs.add(p)
        parts = p.split("/")
        if len(parts) > 1:
            globs.add("/".join(parts[:-1]) + "/**")
    return paths, globs


def _file_is_mapped(path: str, paths: set[str], globs: set[str], plan_text: str) -> bool:
    if path in paths:
        return True
    for g in globs:
        if fnmatch.fnmatch(path, g):
            return True
    # Fuzzy: the plan is prose; accept a basename or path substring mention.
    basename = path.split("/")[-1]
    if path in plan_text or basename in plan_text:
        return True
    return False


def _has_waiver(record: dict[str, Any]) -> bool:
    for key in _WAIVER_KEYS:
        val = record.get(key)
        if val:
            return True
    return False


def _diff_audit_blocking_warnings(base: str, cwd: Path) -> list[str]:
    """Secret and test-weakening warnings from the real diff — promoted to
    blocking by verify-gates --against-diff at medium+."""
    warnings: list[str] = []
    patch = diff_patch(base, cwd)
    added_lines = "\n".join(
        line[1:] for line in patch.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )
    if any(p.search(added_lines) for p in ql.SECRET_PATTERNS):
        warnings.append("possible secret added in diff")
    if any(
        p.search(line) for line in patch.splitlines() for p in ql.TEST_WEAKENING_PATTERNS
    ):
        warnings.append("possible test-weakening (added skip/xfail/.only) in diff")
    return warnings


def verify_gates_against_diff(
    record: dict[str, Any],
    risk: str,
    base: str = "HEAD",
    cwd: Path | None = None,
    record_path: Path | None = None,
) -> list[str]:
    """Diff-grounded findings that complement the record-only verify-gates.

    Returns a list of human-readable findings (empty = clean).
    """
    cwd = cwd or Path.cwd()
    findings: list[str] = []
    files = changed_files(base, cwd)
    if record_path is not None:
        try:
            record_rel = str(record_path.resolve().relative_to(cwd.resolve()))
        except ValueError:
            record_rel = record_path.name
        files = [f for f in files if f != record_rel]
    status = record.get("status")
    non_trivial = risk in {"medium", "high"} or bool(record.get("security_sensitive"))

    # 1. Phantom completion: package/done ∧ empty diff → fail.
    if status in {"package", "done"} and not files:
        findings.append(
            "phantom completion: status is package/done but the working-tree diff is empty"
        )

    # 2. Scope integrity: changed files ⊄ repo_map ∪ plan ∪ completion_record.
    if files and non_trivial:
        paths, globs = _allowed_paths_and_globs(record)
        plan_text = " ".join(str(p) for p in record.get("plan", []) or []).lower()
        unmapped = [
            f for f in files
            if not _file_is_mapped(f, paths, globs, plan_text)
        ]
        if unmapped:
            findings.append(
                "scope integrity: %d changed file(s) not mapped in repo_map/plan/"
                "completion_record.files_changed: %s"
                % (len(unmapped), ", ".join(unmapped[:5]))
            )

    # 3. Diff-derived risk floor: high-tier paths force high-risk gates.
    forced = [f for f in files if _path_matches_high_tier(f)]
    if forced and risk != "high":
        findings.append(
            "diff-derived risk floor: changed paths force high-tier gates: %s"
            % ", ".join(forced[:5])
        )

    # 4. Bugfix-test co-presence: bugfix + no test in diff + no waiver → fail.
    goal = str(record.get("goal", "")).lower()
    is_bugfix = any(k in goal for k in _BUGFIX_GOAL_KEYWORDS)
    if is_bugfix and files and not _has_waiver(record):
        tests_in_diff = [
            f for f in files if any(m in f.lower() for m in ql.TEST_PATH_MARKERS)
        ]
        if not tests_in_diff:
            findings.append(
                "bugfix-test co-presence: goal mentions a bug/fix but no test file is "
                "present in the diff and no waiver is recorded"
            )

    # 5. Review freshness: independent_review.diff_sha256 recomputed at medium+.
    review = record.get("independent_review")
    if non_trivial and isinstance(review, dict):
        recorded_hash = review.get("diff_sha256")
        try:
            actual_hash = diff_sha256(base, cwd)
        except SystemExit:
            actual_hash = None
        if not recorded_hash:
            findings.append(
                "review freshness: independent_review has no diff_sha256 at medium+ risk "
                "(attest the review with `attest-review`)"
            )
        elif actual_hash and recorded_hash != actual_hash:
            findings.append(
                "review freshness: independent_review.diff_sha256 does not match the "
                "current diff (stale review — re-attest after the last edit)"
            )

    # 6. Promote diff-audit secret/test-weakening warnings to blocking at medium+.
    if non_trivial:
        try:
            findings.extend(_diff_audit_blocking_warnings(base, cwd))
        except SystemExit:
            pass

    return findings


def attest_review(
    review: dict[str, Any],
    base: str = "HEAD",
    cwd: Path | None = None,
) -> dict[str, Any]:
    """Embed a recomputed diff sha256 into a review object (the reviewer's last act)."""
    cwd = cwd or Path.cwd()
    out = dict(review)
    out["diff_sha256"] = diff_sha256(base, cwd)
    out["attested_at"] = datetime.now().isoformat(timespec="seconds")
    return out


def _load_allowlist(cwd: Path) -> list[str]:
    candidates = [cwd / ".quality-loop" / "allowed-commands"]
    for path in candidates:
        if path.is_file():
            patterns: list[str] = []
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                patterns.append(line)
            return patterns
    return []


def _command_allowed(cmd: str, patterns: list[str]) -> bool:
    if not patterns:
        return False
    for pat in patterns:
        if fnmatch.fnmatch(cmd, pat):
            return True
    return False


def _run_command(cmd: str, cwd: Path, timeout: int) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(cwd),
            timeout=timeout,
            check=False,
        )
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout[-2000:],
            "stderr": proc.stderr[-2000:],
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "exit_code": None,
            "stdout": (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else "",
            "timed_out": True,
        }
    except OSError as exc:
        return {"exit_code": None, "stdout": "", "stderr": str(exc), "timed_out": False}


def run_evidence(
    record: dict[str, Any],
    base: str = "HEAD",
    red_green: bool = False,
    cwd: Path | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """Re-execute recorded pass commands; optionally replay red_green in a worktree.

    Never mutates the record. Writes a sidecar ``.quality-loop/rerun-<task>.json``.
    Returns a result dict with per-command rerun outcomes and a list of findings.
    """
    cwd = cwd or Path.cwd()
    task_id = str(record.get("task_id", "unknown"))
    commands = [
        c for c in record.get("commands_run", []) or []
        if isinstance(c, dict) and c.get("result") == "pass"
    ]
    allowlist = _load_allowlist(cwd)
    findings: list[str] = []
    reruns: list[dict[str, Any]] = []

    for cmd_entry in commands:
        cmd = str(cmd_entry.get("cmd", "")).strip()
        if not cmd:
            continue
        if not _command_allowed(cmd, allowlist):
            findings.append(
                "run-evidence: command not on allowlist (.quality-loop/allowed-commands): %s"
                % ql.redact(cmd)
            )
            reruns.append({
                "cmd": ql.redact(cmd),
                "recorded_result": "pass",
                "rerun_result": "not_allowed",
            })
            continue
        result = _run_command(cmd, cwd, timeout)
        passed = result["exit_code"] == 0 and not result["timed_out"]
        reruns.append({
            "cmd": ql.redact(cmd),
            "recorded_result": "pass",
            "rerun_result": "pass" if passed else ("timeout" if result["timed_out"] else "fail"),
            "exit_code": result["exit_code"],
            "stderr_tail": ql.redact(result["stderr"]) if result["stderr"] else "",
        })
        if not passed:
            findings.append(
                "run-evidence: recorded-pass command did not pass on rerun: %s (%s)"
                % (ql.redact(cmd), "timeout" if result["timed_out"] else f"exit {result['exit_code']}")
            )

    red_green_results: list[dict[str, Any]] = []
    if red_green:
        rg_commands = [c for c in commands if c.get("red_green")]
        if not rg_commands:
            findings.append("run-evidence --red-green: no commands_run entry marked red_green: true")
        for cmd_entry in rg_commands:
            cmd = str(cmd_entry.get("cmd", "")).strip()
            rg = _red_green_check(cmd, base, cwd, timeout)
            red_green_results.append(rg)
            if rg["red"] != "fail":
                findings.append(
                    "run-evidence --red-green: RED not proven for %s — %s"
                    % (ql.redact(cmd), rg["red_reason"])
                )
            if rg["green"] != "pass":
                findings.append(
                    "run-evidence --red-green: GREEN not proven for %s — %s"
                    % (ql.redact(cmd), rg["green_reason"])
                )

    result = {
        "task_id": task_id,
        "base": base,
        "rerun_at": datetime.now().isoformat(timespec="seconds"),
        "commands": reruns,
        "red_green": red_green_results,
        "findings": findings,
    }
    # Sidecar — never the record.
    sidecar = cwd / ".quality-loop" / f"rerun-{task_id}.json"
    try:
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass
    return result


def _red_green_check(cmd: str, base: str, cwd: Path, timeout: int) -> dict[str, Any]:
    """Replay a command at base (expect fail) and HEAD (expect pass).

    Worktree unavailable → explicit "not proven", never a silent pass.
    """
    out: dict[str, Any] = {
        "cmd": ql.redact(cmd),
        "red": "not_proven",
        "red_reason": "",
        "green": "not_proven",
        "green_reason": "",
    }
    worktree_dir = tempfile.mkdtemp(prefix="ql-rg-")
    code, _, err = _git(["worktree", "add", "--detach", worktree_dir, base], cwd)
    if code != 0:
        out["red_reason"] = "worktree unavailable: %s" % ql.redact(err.strip())
        out["green_reason"] = "worktree unavailable (RED unproven)"
        # best-effort cleanup of the empty temp dir
        try:
            os.rmdir(worktree_dir)
        except OSError:
            pass
        return out
    try:
        red_result = _run_command(cmd, Path(worktree_dir), timeout)
        if red_result["timed_out"]:
            out["red"] = "timeout"
            out["red_reason"] = "command timed out at base"
        elif red_result["exit_code"] == 0:
            out["red"] = "pass"
            out["red_reason"] = "command passed at base (RED was not real — test does not reproduce the bug)"
        else:
            out["red"] = "fail"
            out["red_reason"] = "command failed at base as expected (RED proven)"
        # GREEN: run in the current working tree (HEAD = current state).
        green_result = _run_command(cmd, cwd, timeout)
        if green_result["timed_out"]:
            out["green"] = "timeout"
            out["green_reason"] = "command timed out at HEAD"
        elif green_result["exit_code"] == 0:
            out["green"] = "pass"
            out["green_reason"] = "command passed at HEAD as expected (GREEN proven)"
        else:
            out["green"] = "fail"
            out["green_reason"] = "command failed at HEAD (GREEN not real)"
    finally:
        _git(["worktree", "remove", "--force", worktree_dir], cwd)
    return out


def scan_text(text: str) -> list[dict[str, Any]]:
    """Secret-scan-as-a-service: return findings (line, redacted snippet) for input text."""
    findings: list[dict[str, Any]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pattern in ql.SECRET_PATTERNS:
            match = pattern.search(line)
            if match:
                snippet = ql.redact(line.strip())
                findings.append({
                    "line": lineno,
                    "snippet": snippet[:160],
                })
                break  # one finding per line is enough
    return findings


# --- Subcommand handlers ----------------------------------------------------


def cmd_attest_review(args: Any) -> int:
    review_path = Path(args.review)
    try:
        review = json.loads(review_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: could not read review {args.review!r}: {exc}", file=sys.stderr)
        return 1
    if not isinstance(review, dict):
        print(f"error: review {args.review!r} is not a JSON object", file=sys.stderr)
        return 1
    try:
        attested = attest_review(review, base=args.base, cwd=Path.cwd())
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 1
    output = json.dumps(attested, indent=2)
    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
        print(f"attested review written to {args.output}")
    else:
        print(output)
    return 0


def cmd_run_evidence(args: Any) -> int:
    record_path = Path(args.record)
    record = ql.load_json(record_path)
    try:
        result = run_evidence(
            record,
            base=args.base,
            red_green=getattr(args, "red_green", False),
            cwd=Path.cwd(),
            timeout=args.timeout,
        )
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 1
    findings = result["findings"]
    summary = {
        "task_id": result["task_id"],
        "commands_rerun": len(result["commands"]),
        "red_green_checks": len(result["red_green"]),
        "findings": findings,
        "sidecar": str(Path.cwd() / ".quality-loop" / f"rerun-{result['task_id']}.json"),
    }
    print(json.dumps(summary, indent=2))
    return 1 if findings else 0


def cmd_scan_text(args: Any) -> int:
    text = sys.stdin.read()
    findings = scan_text(text)
    print(json.dumps({"findings": findings, "clean": not findings}, indent=2))
    return 1 if findings else 0
