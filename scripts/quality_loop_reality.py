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
``git_capture`` / ``run_git`` / ``redact`` / ``SECRET_PATTERNS`` / ``load_json``
from ``quality_loop_core``.

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

import quality_loop_core as qlc

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
# Explicit inflections, word-boundary matched: "fix"/"fixed"/"fixes"/"fixing"
# and "bugfix" count, but "fixture"/"prefix" do not (the old greedy \w* suffix
# classified "add a test fixture" as a bugfix) and "debugging" does not trigger
# via the "bug" substring.
_BUGFIX_GOAL_PATTERNS = [
    re.compile(r"\b(?:fix(?:ed|es|ing)?|bugfix(?:es)?)\b"),
    re.compile(r"\b(?:bugs?|broken|crash(?:e[sd]|ing)?|regressions?|defects?)\b"),
]
_WAIVER_KEYS = ("test_waiver", "no_test_waiver", "bugfix_test_waiver")


# The git wrapper lives in quality_loop_core; these preserve the module-local
# names and exact error behavior (git_capture never raises; run_git prints
# redacted stderr and exits on failure).
_git = qlc.git_capture
_git_or_fail = qlc.run_git


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


def _is_scaffolding_untracked(path: str) -> bool:
    """Loop scaffolding (the record, .quality-loop/, caches) is process output,
    not the change under review — mirrors diff-audit's untracked sweep."""
    norm = path.replace("\\", "/")
    if norm.startswith(".quality-loop/") or "/.quality-loop/" in norm:
        return True
    if "__pycache__/" in norm or norm.endswith(".pyc"):
        return True
    return norm.split("/")[-1] == "agent-record.json"


def _untracked_pseudo_diff(cwd: Path) -> str:
    """Deterministic diff-shaped view of untracked (non-ignored) files.

    ``git diff <base>`` is blind to untracked files, so a brand-new source file
    would be invisible to the reviewer render and the attestation hash — a
    reviewer could approve without seeing it, and it could change afterwards
    without staling the review. Appending the content in a stable pseudo-diff
    closes that hole for render and hash alike.
    """
    code, out, _ = _git(["ls-files", "--others", "--exclude-standard"], cwd)
    if code != 0:
        return ""
    chunks: list[str] = []
    for f in sorted(p.strip() for p in out.splitlines() if p.strip()):
        if _is_scaffolding_untracked(f):
            continue
        path = cwd / f
        # Never follow an untracked symlink: reading its target would disclose a
        # file outside the tree through render-prompt. Represent it by its link
        # value so a change still stales the hash, without reading the target.
        if path.is_symlink():
            try:
                target = os.readlink(path)
            except OSError:
                target = "(unreadable)"
            chunks.append(f"diff --untracked a/{f} b/{f}\nsymlink -> {target}\n")
            continue
        try:
            raw = path.read_bytes()
        except OSError as exc:
            chunks.append(
                f"diff --untracked a/{f} b/{f}\n(unreadable untracked file: {exc.__class__.__name__})\n"
            )
            continue
        # A raw-byte sha keeps the hash byte-faithful (CRLF/final-newline/
        # invalid-byte changes all stale it); the decoded +lines stay human-
        # reviewable in the rendered prompt.
        digest = hashlib.sha256(raw).hexdigest()
        content = raw.decode("utf-8", errors="replace")
        body = "".join("+" + line + "\n" for line in content.splitlines())
        chunks.append(
            f"diff --untracked a/{f} b/{f}\n--- /dev/null\n+++ b/{f}\nsha256 {digest}\n{body}"
        )
    return "".join(chunks)


def diff_patch(base: str = "HEAD", cwd: Path | None = None, exclude_record_dir: bool = False) -> str:
    cwd = cwd or Path.cwd()
    args = ["diff", base]
    if exclude_record_dir:
        # Record artifacts under .quality-loop/ (progress, rerun sidecars, the
        # record itself) legitimately change after a review is attested; they
        # must not invalidate the attestation.
        args += ["--", ".", ":(exclude).quality-loop"]
    return _git_or_fail(args, cwd) + _untracked_pseudo_diff(cwd)


def diff_sha256(base: str = "HEAD", cwd: Path | None = None, exclude_record_dir: bool = False) -> str:
    """sha256 of the current diff (the normalization is the git diff itself)."""
    return hashlib.sha256(diff_patch(base, cwd, exclude_record_dir).encode("utf-8")).hexdigest()


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


def _allowed_paths_and_globs(record: dict[str, Any]) -> tuple[set[str], set[str], set[str]]:
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
    # Explicit mapped entries may themselves be globs and stay fnmatch-checked;
    # a mapped FILE additionally whitelists its own directory but only one
    # level (dirs, exact-match), never a recursive parent/'/**' glob —
    # fnmatch's '*' crosses '/', so that glob whitelisted whole subtrees.
    globs: set[str] = set(paths)
    dirs: set[str] = set()
    for p in paths:
        parts = p.split("/")
        if len(parts) > 1:
            dirs.add("/".join(parts[:-1]))
    return paths, globs, dirs


def _file_is_mapped(
    path: str, paths: set[str], globs: set[str], dirs: set[str], plan_text: str
) -> bool:
    if path in paths:
        return True
    if "/".join(path.split("/")[:-1]) in dirs:
        return True
    for g in globs:
        if fnmatch.fnmatch(path, g):
            return True
    # Fuzzy: the plan is prose; accept a basename or path substring mention.
    # plan_text is lowercased by the caller, so lowercase this side too
    # (Button.tsx-style paths must not silently miss).
    basename = path.split("/")[-1]
    if path.lower() in plan_text or basename.lower() in plan_text:
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
    if any(p.search(added_lines) for p in qlc.SECRET_PATTERNS):
        warnings.append("possible secret added in diff")
    weakened = qlc.test_weakening_hits(patch)
    if weakened:
        warnings.append(
            "possible test-weakening (added skip/xfail/.only) in test files: "
            + ", ".join(weakened)
        )
    # Deleted/gutted tests (net declaration or assertion loss) are the other
    # half of Hard Rule 6; like the skip patterns, blocking at medium+ only.
    warnings.extend(qlc.test_shrinkage_hits(patch))
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
    # Record artifacts are process output, not the change under review: they
    # must not trip scope integrity or mask phantom completion as real work.
    files = [f for f in files if not f.startswith(".quality-loop/")]
    status = record.get("status")
    # Same non-trivial definition as the engine's collect_gate_findings: a
    # task_class=medium/mission record must not skip scope integrity, review
    # freshness, or the medium+ promotions by self-declaring risk_tier=low.
    non_trivial = (
        record.get("task_class") in {"medium", "mission"}
        or risk in {"medium", "high"}
        or bool(record.get("security_sensitive"))
    )

    # 1. Phantom completion: package/done ∧ empty diff → fail.
    if status in {"package", "done"} and not files:
        findings.append(
            "phantom completion: status is package/done but the working-tree diff is empty"
        )

    # 2. Scope integrity: changed files ⊄ repo_map ∪ plan ∪ completion_record.
    if files and non_trivial:
        paths, globs, dirs = _allowed_paths_and_globs(record)
        # A malformed record (scalar plan) must degrade to a finding, not crash:
        # str-join on a non-iterable raises TypeError.
        plan_val = record.get("plan")
        plan_items = plan_val if isinstance(plan_val, list) else ([plan_val] if plan_val else [])
        plan_text = " ".join(str(p) for p in plan_items).lower()
        unmapped = [
            f for f in files
            if not _file_is_mapped(f, paths, globs, dirs, plan_text)
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
    is_bugfix = any(p.search(goal) for p in _BUGFIX_GOAL_PATTERNS)
    if is_bugfix and files and not _has_waiver(record):
        tests_in_diff = [
            f for f in files if any(m in f.lower() for m in qlc.TEST_PATH_MARKERS)
        ]
        if not tests_in_diff:
            findings.append(
                "bugfix-test co-presence: goal mentions a bug/fix but no test file is "
                "present in the diff and no waiver is recorded"
            )

    # 5. Review freshness: recomputed at medium+ for BOTH the independent and the
    # security review — a stale security approval at a risk boundary is exactly
    # what the freshness gate exists to catch.
    if non_trivial:
        try:
            # Attestation hashes exclude .quality-loop/ so record-only trailing
            # commits (evidence, progress) do not go stale. Records attested by
            # older versions carry the full-diff hash; accept either.
            valid_hashes = {diff_sha256(base, cwd, exclude_record_dir=True), diff_sha256(base, cwd)}
            # An empty current diff means there is nothing under review against
            # this base (e.g. the reviewed work is now the base itself, after a
            # merge) — freshness is N/A, not stale. The terminal-status phantom
            # gate already covers the "done with nothing shipped" case.
            current_empty = not diff_patch(base, cwd, exclude_record_dir=True).strip()
        except SystemExit:
            valid_hashes = set()
            current_empty = False
        for review_key in ("independent_review", "security_review"):
            review = record.get(review_key)
            if not isinstance(review, dict):
                continue
            recorded_hash = review.get("diff_sha256")
            if not recorded_hash:
                findings.append(
                    f"review freshness: {review_key} has no diff_sha256 at medium+ risk "
                    "(attest the review with `attest-review`)"
                )
            elif not current_empty and valid_hashes and recorded_hash not in valid_hashes:
                findings.append(
                    f"review freshness: {review_key}.diff_sha256 does not match the "
                    "current diff (stale review — re-attest after the last non-record edit; "
                    "changes under .quality-loop/ are excluded)"
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
    """Embed a recomputed diff sha256 into a review object (the reviewer's last act).

    The hash excludes .quality-loop/ so that record-only follow-up commits
    (completion record, progress, rerun sidecars) do not invalidate the review.
    """
    cwd = cwd or Path.cwd()
    out = dict(review)
    out["diff_sha256"] = diff_sha256(base, cwd, exclude_record_dir=True)
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
                "run-evidence: command not on allowlist (.quality-loop/allowed-commands): %s "
                "— to allow it, add a matching line (globs ok) to .quality-loop/allowed-commands"
                % qlc.redact(cmd)
            )
            reruns.append({
                "cmd": qlc.redact(cmd),
                "recorded_result": "pass",
                "rerun_result": "not_allowed",
            })
            continue
        result = _run_command(cmd, cwd, timeout)
        passed = result["exit_code"] == 0 and not result["timed_out"]
        reruns.append({
            "cmd": qlc.redact(cmd),
            "recorded_result": "pass",
            "rerun_result": "pass" if passed else ("timeout" if result["timed_out"] else "fail"),
            "exit_code": result["exit_code"],
            "stderr_tail": qlc.redact(result["stderr"]) if result["stderr"] else "",
        })
        if not passed:
            detail = (
                f"timeout after {timeout}s — if the suite is legitimately slow, "
                "increase the limit with --timeout or QUALITY_LOOP_TIMEOUT"
                if result["timed_out"]
                else f"exit {result['exit_code']}"
            )
            findings.append(
                "run-evidence: recorded-pass command did not pass on rerun: %s (%s)"
                % (qlc.redact(cmd), detail)
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
                    % (qlc.redact(cmd), rg["red_reason"])
                )
            if rg["green"] != "pass":
                findings.append(
                    "run-evidence --red-green: GREEN not proven for %s — %s"
                    % (qlc.redact(cmd), rg["green_reason"])
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
        "cmd": qlc.redact(cmd),
        "red": "not_proven",
        "red_reason": "",
        "green": "not_proven",
        "green_reason": "",
    }
    worktree_dir = tempfile.mkdtemp(prefix="ql-rg-")
    code, _, err = _git(["worktree", "add", "--detach", worktree_dir, base], cwd)
    if code != 0:
        out["red_reason"] = "worktree unavailable: %s" % qlc.redact(err.strip())
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
        for pattern in qlc.SECRET_PATTERNS:
            match = pattern.search(line)
            if match:
                snippet = qlc.redact(line.strip())
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
    record = qlc.load_json(record_path)
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
