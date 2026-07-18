#!/usr/bin/env python3
"""Utility helpers for the Coding Quality Loop skill.

These checks are intentionally lightweight and portable. They complement, but do
not replace, CI, tests, security scanners, or human review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

try:
    import quality_loop_control as qlctl
    import quality_loop_core as qlcore
    import quality_loop_memory as qlmem
    import quality_loop_reality as qlreal
    import quality_loop_routing as qlroute
except ImportError as _exc:  # pragma: no cover - exercised via subprocess eval
    # A partial copy of scripts/ produces a confusing ImportError; agents have
    # been observed "repairing" the helper (and weakening gates) instead of
    # reporting it. Fail loud and actionable instead.
    sys.stderr.write(
        "coding-quality-loop: incomplete install — %s.\n"
        "The helper needs all sibling modules in the same directory: "
        "quality_loop.py, quality_loop_core.py, quality_loop_control.py, "
        "quality_loop_memory.py, quality_loop_reality.py, quality_loop_routing.py.\n"
        "Copy the full scripts/ directory or re-run scripts/install.py. "
        "Do not hand-edit or stub the helper.\n" % _exc
    )
    raise SystemExit(2)

# Re-export the shared primitives moved into quality_loop_core so that
# `import quality_loop; quality_loop.<name>` (evals) keeps working and this
# module's own references resolve. Explicit names, never a star import.
from quality_loop_core import (  # noqa: E402
    MINIMALITY_REQUIRED_STATUSES,
    POST_IMPLEMENT_STATUSES,
    POST_INTAKE_STATUSES,
    REVIEW_READY_STATUSES,
    SECRET_PATTERNS,
    TERMINAL_STATUSES,
    TEST_PATH_MARKERS,
    TEST_WEAKENING_PATTERNS,
    BRIEF_CHAR_LIMIT_DEFAULT,
    _nonempty,
    atomic_write_text,
    brief_char_limit,
    brief_entry_chars,
    git_capture,
    has_evidence,
    load_json,
    redact,
    require_list,
    require_number,
    require_str,
    run_git,
    write_json,
)


RISK_TIERS = {"low", "medium", "high"}
STATUSES = {
    "intake",
    "explore",
    "plan",
    "minimality_gate",
    "implement",
    "verify",
    "review",
    "package",
    "retrospect",
    "done",
    "iterating",
    "escalated",
}

MINIMALITY_RUNGS = {
    "skip",
    "delete",
    "reuse",
    "stdlib",
    "native",
    "existing_dependency",
    "one_liner",
    "minimal_new_code",
}
# Optional per-run process-tax metrics (R3). All fields are optional numbers.
RUN_METRICS_FIELDS = {"tokens_in", "tokens_out", "cost_usd", "duration_sec"}
COMMAND_RESULTS = {"pass", "fail", "blocked"}
COMMAND_CLASSES = {
    "format",
    "lint",
    "typecheck",
    "unit",
    "integration",
    "e2e",
    "security",
    "build",
    "migration_dry_run",
}
APPROVING_VERDICTS = {"approve", "approved"}
NON_APPROVING_VERDICTS = {
    "request_changes",
    "needs_discussion",
    "fail",
    "failed",
    "blocked",
    "reject",
    "rejected",
}
REVIEW_VERDICTS = APPROVING_VERDICTS | NON_APPROVING_VERDICTS
BLOCKING_SEVERITIES = {"blocking", "blocker"}
# SECRET_PATTERNS, redact + entropy helpers, TEST_PATH_MARKERS, and
# TEST_WEAKENING_PATTERNS moved to quality_loop_core and are re-exported at the
# top of this module.
DEPENDENCY_FILES = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "requirements.txt",
    "pyproject.toml",
    "poetry.lock",
    "Pipfile",
    "Pipfile.lock",
    "go.mod",
    "go.sum",
    "Cargo.toml",
    "Cargo.lock",
    "Gemfile",
    "Gemfile.lock",
}
MIGRATION_DIR_MARKERS = {"migration", "migrations", "alembic", "prisma", "flyway", "liquibase"}
MIGRATION_FILE_MARKERS = {"schema.sql", "schema.prisma", "changelog.xml", "db.changelog.xml"}

# Risk boundaries detected from the record's own text. A self-declared low/tiny
# tier must not let auth/payment/migration/secret/infra work bypass the heavy
# gates, so detect_risk_floor scans the goal/criteria/plan and forces a floor.
BOUNDARY_KEYWORDS = {
    # Bare common-English words (admin, grant, session, token) are deliberately
    # excluded: they over-fire on benign copy/docs ("admin dashboard copy",
    # "design token", "session summary") and that noise IS the process theater the
    # skill disclaims. Precise multi-word and domain terms are kept.
    "authn": (
        "auth", "authentication", "authenticate", "login", "log in", "signin",
        "sign-in", "oauth", "sso", "jwt", "credential", "mfa", "2fa",
        "totp", "multi-factor",
    ),
    "authz": (
        "authorization", "authorize", "authz", "permission", "rbac", "acl",
        "access control", "privilege", "admin endpoint",
    ),
    "secrets": (
        "secret", "api key", "api-key", "password", "private key",
        "credentials", "access key", "signing key", "vault", "kms",
    ),
    "crypto": (
        "tls", "ssl", "certificate", "encrypt", "encryption", "decrypt", "decryption",
        "bcrypt", "scrypt", "argon2", "csrf", "cors", "saml", "xss",
    ),
    "payments": (
        "payment", "billing", "charge", "refund", "stripe", "checkout",
        "payout", "subscription", "chargeback", "pci",
    ),
    "data_migration": (
        "migration", "migrate", "schema change", "alter table", "drop table", "backfill",
    ),
    "destructive": ("delete from", "truncate", "drop database", "rm -rf", "wipe"),
    "infra": ("production deploy", "prod deploy", "terraform", "kubernetes", "infrastructure"),
    "concurrency": (
        "concurrency", "race condition", "data race", "deadlock", "thread safety",
        "lock contention",
    ),
    "data_loss": (
        "data loss", "data corruption", "partial write", "double write",
        "atomicity", "write ahead log",
    ),
    "pii": (
        "pii", "personally identifiable", "personal data", "gdpr", "ccpa",
        "data retention",
    ),
}
# Word-boundary matched so "auth" does not fire on "author", "token" not on
# "tokenizer", "sso" not on "blossom", "charge" not on "recharge".
BOUNDARY_PATTERNS = {
    boundary: [re.compile(r"\b" + re.escape(w) + r"\b") for w in words]
    for boundary, words in BOUNDARY_KEYWORDS.items()
}


# has_evidence and _nonempty moved to quality_loop_core (re-exported at top);
# they are deliberately different predicates — see the note in the core module.


# Required content for shipping artifacts when supplied as an inline object. Each
# tuple is an "at least one of these keys must be non-empty" group, so portable
# field-name variants are accepted without forcing one rigid schema.
ARTIFACT_REQUIRED_FIELDS = {
    "validation_contract": (
        ("goal",),
        ("acceptance_criteria", "done_when", "criteria"),
        ("evidence", "required_evidence", "checks", "proof"),
    ),
    "completion_record": (
        ("goal",),
        ("acceptance_criteria", "criteria", "done_when"),
        ("evidence", "verification", "verification_evidence", "checks"),
    ),
}


def artifact_findings(value: Any, kind: str, base_dir: Path) -> list[str]:
    """Deep validation for shipping artifacts (validation_contract / completion_record).

    A shape-only check accepts placeholders the shipping gate should reject. This
    rejects: bare booleans/numbers, empty strings, string paths that do not
    resolve to an existing file, and objects missing the descriptive fields their
    kind requires. A string is treated as a path to a real artifact file
    (resolved relative to the record, then the working directory) to keep records
    portable while still requiring the artifact to actually exist.
    """
    if value is None:
        return [f"non-trivial work requires a {kind} with evidence"]
    if isinstance(value, bool) or (isinstance(value, (int, float)) and not isinstance(value, str)):
        return [f"{kind} must be a real artifact (object or existing file path), not {value!r}"]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return [f"non-trivial work requires a {kind} with evidence"]
        resolved = next((p for p in (base_dir / text, Path(text)) if p.is_file()), None)
        if resolved is None:
            return [f"{kind} path does not exist: {text!r} (expected a real artifact file)"]
        # A file path must satisfy the same content contract as an inline object,
        # otherwise any existing file (e.g. LICENSE) would pass the gate.
        try:
            body = resolved.read_text(errors="replace")[:100_000].lower()
        except OSError:
            return [f"{kind} file could not be read: {text!r}"]
        missing = [
            "/".join(group)
            for group in ARTIFACT_REQUIRED_FIELDS.get(kind, ())
            if not any((key in body or key.replace("_", " ") in body) for key in group)
        ]
        if missing:
            return [f"{kind} file {text!r} is missing required content: {', '.join(missing)}"]
        return []
    if isinstance(value, dict):
        if not value:
            return [f"non-trivial work requires a {kind} with evidence"]
        missing = [
            "/".join(group)
            for group in ARTIFACT_REQUIRED_FIELDS.get(kind, ())
            if not any(_nonempty(value.get(key)) for key in group)
        ]
        if missing:
            return [f"{kind} object is missing required content: {', '.join(missing)}"]
        return []
    return [f"{kind} must be an object or an existing file path"]


def review_findings(review: Any, label: str, implementer: Any) -> list[str]:
    """Findings that block a record on an independent/security review artifact.

    Requires a distinct, named reviewer (not the implementer), an approving
    verdict, fresh context, no self-patching, and no unresolved blocking findings.
    """
    findings: list[str] = []
    if not isinstance(review, dict):
        findings.append(f"{label} is required and must be a review object")
        return findings
    reviewer = review.get("reviewer") or review.get("validator")
    if not isinstance(reviewer, str) or not reviewer.strip():
        findings.append(f"{label} needs a named reviewer")
    elif isinstance(implementer, str) and reviewer.strip() == implementer.strip():
        findings.append(f"{label} reviewer cannot be the implementer ({reviewer})")
    verdict = str(review.get("verdict", "")).lower()
    if verdict not in APPROVING_VERDICTS:
        findings.append(f"{label} verdict is not approving (got {review.get('verdict')!r})")
    if review.get("fresh_context") is not True:
        findings.append(f"{label} must be done with fresh context")
    if review.get("patched") is True:
        findings.append(f"{label} reviewer must not patch the code under review")
    for finding in review.get("findings", []) or []:
        if isinstance(finding, dict) and str(finding.get("severity", "")).lower() in BLOCKING_SEVERITIES:
            findings.append(f"{label} has an unresolved blocking finding")
            break
    return findings


def detect_risk_floor(record: dict[str, Any]) -> tuple[str, list[str]]:
    """Ground-truth boundary detection from the record's own text.

    Scans goal + acceptance criteria + plan for boundary keywords (word-boundary
    matched) so a self-declared low/tiny tier cannot bypass the heavy gates.
    Returns ('high', [markers]) when any boundary term is present, else ('low', []).
    """
    haystack = " ".join(
        str(x).lower()
        for x in (
            [record.get("goal", "")]
            + list(record.get("acceptance_criteria", []) or [])
            + list(record.get("plan", []) or [])
        )
    )
    markers = sorted(
        boundary
        for boundary, pats in BOUNDARY_PATTERNS.items()
        if any(p.search(haystack) for p in pats)
    )
    return ("high", markers) if markers else ("low", [])


# load_json and write_json (atomic) moved to quality_loop_core, re-exported at top.


def init_record(args: argparse.Namespace) -> int:
    status = "intake"
    record = {
        "task_id": args.task_id or str(uuid.uuid4()),
        "goal": args.goal,
        "acceptance_criteria": [],
        "constraints": [],
        "non_goals": [],
        "assumptions": [],
        "risk_tier": args.risk_tier,
        "task_class": None,
        "implementer": None,
        "security_sensitive": False,
        "verification_plan": [],
        "validation_contract": None,
        "independent_review": None,
        "security_review": None,
        "completion_record": None,
        "repair_attempts": 0,
        "repeated_failure": False,
        "harness_update": None,
        "repo_map": {
            "entry_points": [],
            "likely_files": [],
            "callers_checked": [],
            "tests": [],
            "patterns_to_follow": [],
        },
        "minimality_decision": None,
        "plan": [],
        "commands_run": [],
        "open_risks": [],
        "review_findings": [],
        "next_action": "Complete intake and acceptance criteria.",
        "status": status,
    }
    write_json(Path(args.output), record)
    print(args.output)
    # Scaffold the run-evidence allowlist next to the record so verification
    # commands can be re-executed later. Live runs showed agents never create
    # this file on their own, which turns run-evidence into a guaranteed FAIL.
    record_dir = Path(args.output).resolve().parent
    # A record living inside .quality-loop/ must not nest a second .quality-loop/.
    base = record_dir if record_dir.name == ".quality-loop" else record_dir / ".quality-loop"
    allowlist = base / "allowed-commands"
    if not allowlist.exists():
        try:
            allowlist.parent.mkdir(parents=True, exist_ok=True)
            allowlist.write_text(
                "# Commands run-evidence may re-execute (one per line, globs ok).\n"
                "# Add every verification command you record in commands_run, e.g.:\n"
                "# npm test\n"
                "# pytest tests/*\n",
                encoding="utf-8",
            )
            print(f"scaffolded {allowlist} — add your verification commands to it")
        except OSError:
            pass
    return 0




def check_record(args: argparse.Namespace) -> int:
    record = load_json(Path(args.record))
    errors: list[str] = []
    warnings: list[str] = []

    required = [
        "task_id",
        "goal",
        "acceptance_criteria",
        "constraints",
        "non_goals",
        "assumptions",
        "risk_tier",
        "verification_plan",
        "status",
    ]
    for key in required:
        if key not in record:
            errors.append(f"missing required field: {key}")

    require_str(errors, record.get("task_id"), "task_id")
    require_str(errors, record.get("goal"), "goal")
    if record.get("risk_tier") not in RISK_TIERS:
        errors.append("risk_tier must be one of: low, medium, high")
    status = record.get("status")
    if status not in STATUSES:
        errors.append("status is not a valid lifecycle state")
    # A legacy `phase` field (from the retired three-phase model) is tolerated and
    # ignored — no gate consumes it, so its value is never validated.

    minimality = record.get("minimality_decision")
    if minimality is not None:
        if not isinstance(minimality, dict):
            errors.append("minimality_decision must be an object")
        else:
            if minimality.get("rung") not in MINIMALITY_RUNGS:
                errors.append("minimality_decision.rung is invalid")
            if not minimality.get("reason"):
                errors.append("minimality_decision.reason is required")
    if status in MINIMALITY_REQUIRED_STATUSES and not minimality:
        errors.append("minimality_decision is required at minimality_gate or later")

    for array_key in [
        "acceptance_criteria",
        "constraints",
        "non_goals",
        "assumptions",
        "verification_plan",
        "plan",
        "commands_run",
        "open_risks",
        "review_findings",
    ]:
        if array_key in record:
            require_list(errors, record[array_key], array_key)

    commands = record.get("commands_run")
    if isinstance(commands, list):
        for idx, cmd in enumerate(commands):
            if not isinstance(cmd, dict):
                errors.append(f"commands_run[{idx}] must be an object")
                continue
            require_str(errors, cmd.get("cmd"), f"commands_run[{idx}].cmd")
            if cmd.get("result") not in COMMAND_RESULTS:
                errors.append(f"commands_run[{idx}].result must be one of: pass, fail, blocked")
            cls = cmd.get("class")
            if cls is not None and cls not in COMMAND_CLASSES:
                errors.append(
                    f"commands_run[{idx}].class is not a recognized class: {cls!r}"
                )

    for artifact_key in ("validation_contract", "completion_record", "harness_update"):
        value = record.get(artifact_key)
        if value is None:
            continue
        if isinstance(value, (bool, int, float)) and not isinstance(value, str):
            errors.append(
                f"{artifact_key} must be an object or a path/string with evidence, "
                "not a bare boolean/number"
            )
        elif isinstance(value, str) and not value.strip():
            errors.append(f"{artifact_key} must not be an empty string")

    repair_attempts = record.get("repair_attempts")
    if repair_attempts is not None:
        if isinstance(repair_attempts, bool) or not isinstance(repair_attempts, int):
            errors.append("repair_attempts must be an integer")
        elif repair_attempts < 0:
            errors.append("repair_attempts must be >= 0")
    if "repeated_failure" in record and not isinstance(record.get("repeated_failure"), bool):
        errors.append("repeated_failure must be a boolean")

    # Optional run_metrics (R3 process-tax instrumentation). Absent is fine; when
    # present, every value must be a non-negative number and no unknown keys are
    # allowed inside the object.
    run_metrics = record.get("run_metrics")
    if run_metrics is not None:
        if not isinstance(run_metrics, dict):
            errors.append("run_metrics must be an object")
        else:
            for key, value in run_metrics.items():
                if key not in RUN_METRICS_FIELDS:
                    errors.append(f"run_metrics has unknown key: {key!r}")
                else:
                    require_number(errors, value, f"run_metrics.{key}")

    if "implementer" in record and record["implementer"] is not None:
        require_str(errors, record["implementer"], "implementer")

    # Optional multi-model routing evidence (v4.2): per-role model attribution
    # and escalation events. Absent is fine; when present the shape must hold so
    # the R5 evidence base stays machine-readable.
    models_used = record.get("models_used")
    if models_used is not None and require_list(errors, models_used, "models_used"):
        for idx, entry in enumerate(models_used):
            if not isinstance(entry, dict):
                errors.append(f"models_used[{idx}] must be an object")
                continue
            for req in ("role", "model"):
                require_str(errors, entry.get(req), f"models_used[{idx}].{req}")
            attempts = entry.get("attempts")
            if attempts is not None and (
                isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1
            ):
                errors.append(f"models_used[{idx}].attempts must be an integer >= 1")
            for num_key in ("tokens_in", "tokens_out", "cost_usd"):
                val = entry.get(num_key)
                if val is not None and (
                    isinstance(val, bool) or not isinstance(val, (int, float)) or val < 0
                ):
                    errors.append(f"models_used[{idx}].{num_key} must be a non-negative number")
    escalations = record.get("escalations")
    if escalations is not None and require_list(errors, escalations, "escalations"):
        for idx, entry in enumerate(escalations):
            if not isinstance(entry, dict):
                errors.append(f"escalations[{idx}] must be an object")
                continue
            for req in ("step", "from_model", "to_model"):
                require_str(errors, entry.get(req), f"escalations[{idx}].{req}")
            if entry.get("trigger") != "verified_failure":
                errors.append(
                    f"escalations[{idx}].trigger must be 'verified_failure' -- the only "
                    f"recordable escalation is one backed by failing check evidence"
                )
            failing = entry.get("failing_commands")
            if (
                not isinstance(failing, list)
                or not failing
                or not all(isinstance(c, str) and c.strip() for c in failing)
            ):
                errors.append(
                    f"escalations[{idx}].failing_commands must be a non-empty array of "
                    f"command strings"
                )
            from_model = entry.get("from_model")
            to_model = entry.get("to_model")
            if (
                isinstance(from_model, str) and isinstance(to_model, str)
                and from_model.strip() and from_model == to_model
            ):
                errors.append(f"escalations[{idx}]: from_model and to_model must differ")
            attempts = entry.get("attempts")
            if attempts is not None and (
                isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1
            ):
                errors.append(f"escalations[{idx}].attempts must be an integer >= 1")

    for review_key in ("independent_review", "security_review"):
        review = record.get(review_key)
        if review is None:
            continue
        if not isinstance(review, dict):
            errors.append(f"{review_key} must be an object")
            continue
        verdict = str(review.get("verdict", "")).lower()
        if verdict not in REVIEW_VERDICTS:
            errors.append(f"{review_key}.verdict must be a recognized review verdict")

    if status in POST_INTAKE_STATUSES:
        if not record.get("acceptance_criteria"):
            warnings.append("acceptance_criteria is empty after INTAKE")
        if not record.get("verification_plan"):
            warnings.append("verification_plan is empty after PLAN")

    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    for warning in warnings:
        print(f"warning: {warning}")
    print("record ok")
    return 1 if warnings and args.strict else 0


# The entropy helpers, redact, and run_git moved to quality_loop_core (redact and
# run_git are re-exported at the top of this module).


# Scaffolding the loop writes into the working tree (the record, its sidecars,
# the allowlist, byte-compiled helpers). It is process output, not "the change,"
# so it must be excluded from the untracked-file sweep — the same reason the
# attestation hash excludes .quality-loop/. Keeping "the diff" consistent
# everywhere stops the audit from counting its own scaffolding as changed lines.
def _is_scaffolding_path(path: str) -> bool:
    norm = path.replace("\\", "/")
    if norm.startswith(".quality-loop/") or "/.quality-loop/" in norm:
        return True
    if "__pycache__/" in norm or norm.endswith(".pyc"):
        return True
    return norm.split("/")[-1] == "agent-record.json"


# Empty tree object — diffing against it treats every tracked file as new, a
# sane last resort when no base ref resolves (e.g. a brand-new repo).
_EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def _resolve_base(base: str) -> tuple[str, str | None]:
    """Resolve a git base ref, falling back through common defaults.

    Returns (resolved_ref, hint). ``hint`` is a human-readable note when the
    requested base was unresolvable and a fallback was chosen, else None. A
    fresh or detached checkout often lacks ``origin/main``; rather than surface
    git's raw ``fatal: Needed a single revision`` (exit 128), pick a sane
    fallback and tell the caller what happened.
    """
    def _resolves(ref: str) -> bool:
        # Route through the core git wrapper (Side B centralized all git
        # subprocess in quality_loop_core); returncode 0 means the ref resolves.
        code, _, _ = qlcore.git_capture(["rev-parse", "--verify", "--quiet", ref + "^{commit}"])
        return code == 0

    if _resolves(base):
        return base, None
    for cand in ("origin/main", "origin/master", "main", "master", "HEAD"):
        if cand != base and _resolves(cand):
            return cand, (
                f"base {base!r} did not resolve; using {cand!r}. "
                "Pass --base <ref> explicitly on a fresh/detached checkout."
            )
    return _EMPTY_TREE_SHA, (
        f"base {base!r} did not resolve and no fallback ref exists; "
        "diffing against the empty tree (all tracked files treated as new)."
    )


# Intentional simplifications (P3.17) are marked with an inline `cql:` comment
# naming the ceiling and the upgrade path. diff-audit surfaces a count only
# (advisory), so the ceilings stay visible without blocking the change.
_SHORTCUT_MARKER_RE = re.compile(r"(?:#|//|/\*|<!--)\s*cql:", re.IGNORECASE)


def is_migration_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    parts = [part for part in normalized.split("/") if part]
    if not parts:
        return False
    basename = parts[-1]
    if basename in MIGRATION_FILE_MARKERS or basename.endswith(".changelog.xml"):
        return True
    if any(part in MIGRATION_DIR_MARKERS for part in parts):
        return True
    return any(left == "db" and right == "migrate" for left, right in zip(parts, parts[1:]))


def diff_audit(args: argparse.Namespace) -> int:
    # Findings split by severity. blocking = a real correctness/safety problem
    # that must stop a commit (leaked secret, silently weakened test). advisory =
    # "look here before you ship" signal that must NOT fail the loop on its own
    # (benign lockfile bump, large but legitimate diff, scaffolding sweep). The
    # git pre-commit hook keys off the exit code, so advisory-only stays exit 0.
    advisory: list[str] = []
    blocking: list[str] = []
    base_label: str

    staged = bool(getattr(args, "staged", False))
    if staged:
        diff = run_git(["diff", "--cached", "--numstat"])
        name_only = run_git(["diff", "--cached", "--name-only"])
        patch = run_git(["diff", "--cached"])
        untracked: list[str] = []
        base_label = "staged"
    else:
        resolved, hint = _resolve_base(args.base or "HEAD")
        if hint:
            advisory.append(hint)
        base_label = resolved
        diff = run_git(["diff", "--numstat", resolved])
        name_only = run_git(["diff", "--name-only", resolved])
        patch = run_git(["diff", resolved])
        # Untracked files are invisible to `git diff`, so a brand-new module (the
        # common agent-work case) bypasses the secret/size scan entirely. Fold them
        # in, but drop the loop's own scaffolding — it is process output, not "the
        # change" (same rationale as the attestation hash's .quality-loop/ skip).
        untracked = [
            f.strip()
            for f in run_git(["ls-files", "--others", "--exclude-standard"]).splitlines()
            if f.strip() and not _is_scaffolding_path(f.strip())
        ]

    files = [line.strip() for line in name_only.splitlines() if line.strip()]
    added = 0
    deleted = 0
    binary = 0

    for line in diff.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        a, d = parts[0], parts[1]
        if a == "-" or d == "-":
            binary += 1
            continue
        added += int(a)
        deleted += int(d)

    if not staged:
        for f in untracked:
            try:
                content = Path(f).read_text(errors="replace")
            except (OSError, ValueError) as exc:
                # A file we cannot read is a file we cannot scan for secrets.
                # Surfacing it (advisory) beats the old silent `continue`, which
                # let an unreadable new file slip past the secret sweep unnoticed.
                advisory.append(
                    f"could not scan untracked file for secrets: {f} ({exc.__class__.__name__})"
                )
                if f not in files:
                    files.append(f)
                continue
            added += len(content.splitlines())
            if f not in files:
                files.append(f)
            if any(p.search(content) for p in SECRET_PATTERNS):
                blocking.append(f"possible secret in untracked file: {f}")
        if untracked:
            advisory.append(
                f"{len(untracked)} untracked file(s) included in audit: " + ", ".join(untracked)
            )

    if len(files) > args.max_files:
        advisory.append(f"large file count: {len(files)} files changed")
    if added + deleted > args.max_lines:
        advisory.append(f"large diff: {added + deleted} changed lines")

    dependency_edits = [f for f in files if os.path.basename(f) in DEPENDENCY_FILES]
    if dependency_edits:
        advisory.append("dependency files changed: " + ", ".join(dependency_edits))

    migration_edits = [f for f in files if is_migration_path(f)]
    if migration_edits:
        advisory.append("migration/schema-related files changed: " + ", ".join(migration_edits))

    added_lines = "\n".join(
        line[1:] for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++")
    )
    for pattern in SECRET_PATTERNS:
        if pattern.search(added_lines):
            blocking.append("possible secret added in diff")
            break

    weakened = qlcore.test_weakening_hits(patch)
    if weakened:
        blocking.append(
            "possible test-weakening (added skip/xfail/.only) in test files: "
            + ", ".join(weakened)
        )

    marker_count = sum(1 for line in patch.splitlines() if _SHORTCUT_MARKER_RE.search(line))
    if marker_count:
        advisory.append(
            f"{marker_count} intentional shortcut marker(s) (cql:) in diff — "
            "confirm each names a ceiling and an upgrade path"
        )

    result = {
        "base": base_label,
        "files_changed": files,
        "file_count": len(files),
        "lines_added": added,
        "lines_deleted": deleted,
        "binary_files_changed": binary,
        "blocking": blocking,
        "advisory": advisory,
    }

    print(json.dumps(result, indent=2))
    return 1 if blocking else 0


_EXEC_CLASSES = {"unit", "integration", "typecheck", "build", "lint"}
_REVIEW_READY_STATUS = REVIEW_READY_STATUSES  # single-sourced in quality_loop_core

# Table-driven risk-tier evidence rules. Each tier lists ordered (check, message)
# pairs; the check name is resolved by _tier_check_fails. Keeping this as data
# rather than nested if/elif blocks makes the per-tier evidence floor auditable
# at a glance and adds a new tier or rule without touching control flow.
_RISK_TIER_RULES: dict[str, list[tuple[str, str]]] = {
    "low": [
        ("needs_check_or_plan", "low risk still needs a targeted check or rationale"),
    ],
    "medium": [
        ("needs_exec", "medium risk needs at least one relevant executable check"),
        ("needs_review_status", "medium risk must reach review/package/done status before review evidence is accepted"),
        ("needs_review_findings", "medium risk should include fresh-context review result or rationale"),
    ],
    "high": [
        ("needs_exec", "high risk needs relevant executable checks"),
        ("needs_security", "high risk needs security review/check evidence or blocked rationale"),
        ("needs_review_status", "high risk must reach review/package/done status before review evidence is accepted"),
        ("needs_risk_doc", "high risk needs explicit risk/review documentation"),
    ],
}


def _tier_check_fails(
    name: str,
    *,
    commands: list[Any],
    command_classes: set[str],
    status: str,
    record: dict[str, Any],
) -> bool:
    status_ok = status in _REVIEW_READY_STATUS
    if name == "needs_check_or_plan":
        return not commands and not record.get("verification_plan")
    if name == "needs_exec":
        return not (_EXEC_CLASSES & command_classes)
    if name == "needs_review_status":
        return not status_ok
    if name == "needs_review_findings":
        # medium's original `elif`: only meaningful once status is review-ready.
        return status_ok and len(record.get("review_findings", [])) == 0
    if name == "needs_security":
        return "security" not in command_classes
    if name == "needs_risk_doc":
        return not record.get("open_risks") and len(record.get("review_findings", [])) == 0
    return False


def _risk_tier_findings(
    risk: str,
    commands: list[Any],
    command_classes: set[str],
    status: str,
    record: dict[str, Any],
) -> list[str]:
    rules = _RISK_TIER_RULES.get(risk)
    if rules is None:
        return ["invalid risk tier"]
    findings: list[str] = []
    for check, message in rules:
        if _tier_check_fails(
            check,
            commands=commands,
            command_classes=command_classes,
            status=status,
            record=record,
        ):
            findings.append(message)
    return findings


def _read_delegation_ledger(base_dir: Path) -> list[dict[str, Any]]:
    """Load ``.quality-loop/delegations.jsonl`` near ``base_dir`` (best-effort).

    The ledger is written by hand/orchestrator; a half-flushed or malformed line
    must never break a gate, so unreadable files yield [] and bad lines are
    skipped. Absent ledger (most repos) yields [] and every ledger-grounded
    check no-ops.
    """
    ledger = base_dir / ".quality-loop" / "delegations.jsonl"
    if not ledger.is_file() and base_dir.name == ".quality-loop":
        ledger = base_dir / "delegations.jsonl"
    entries: list[dict[str, Any]] = []
    try:
        raw_text = ledger.read_text(encoding="utf-8")
    except OSError:
        return entries
    for raw in raw_text.splitlines():
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict):
            entries.append(obj)
    return entries


def _nearest_config(base_dir: Path) -> dict[str, Any]:
    """Read the nearest ``quality-loop.config.json`` walking up from ``base_dir``.

    Bounded walk (repo root is normally one level up from ``.quality-loop/``).
    Returns {} on absence or any read/parse error — config only tunes advisory
    thresholds here, so a broken config falls back to defaults, never a crash.
    """
    start = base_dir.resolve()
    for directory in [start, *list(start.parents)[:6]]:
        candidate = directory / "quality-loop.config.json"
        if candidate.is_file():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return {}
            return data if isinstance(data, dict) else {}
    return {}


def _brief_size_advisories(delegations: list[dict[str, Any]], limit: int) -> list[str]:
    """Advisory notes for delegation briefs exceeding ``limit`` chars (never blocking)."""
    notes: list[str] = []
    for entry in delegations:
        chars = brief_entry_chars(entry)
        if chars > limit:
            who = entry.get("task_id") or entry.get("role") or "?"
            notes.append(
                f"delegation brief for {who!r} is {chars} chars (advisory limit {limit}); "
                f"a tighter brief keeps the sub-agent's context focused"
            )
    return notes


def verify_gates(args: argparse.Namespace) -> int:
    record_path = Path(args.record)
    base_dir = record_path.resolve().parent
    record = load_json(record_path)
    risk = record.get("risk_tier")
    status = record.get("status")
    task_class = record.get("task_class")
    implementer = record.get("implementer")
    security_sensitive = bool(record.get("security_sensitive"))
    raw_commands = record.get("commands_run", [])
    findings: list[str] = []
    soft_warnings: list[str] = []

    # Ground-truth risk floor: if the record's own text hits a known boundary, a
    # self-declared low/tiny tier cannot bypass the heavy gates. Forcing risk and
    # security_sensitive here makes the floor flow into every downstream check.
    _, boundary_markers = detect_risk_floor(record)
    if boundary_markers:
        if risk != "high":
            findings.append(
                "declared risk_tier %r downgrades a detected boundary (markers: %s); "
                "forcing high-risk gates" % (risk, ", ".join(boundary_markers))
            )
        risk = "high"
        security_sensitive = True

    # Defensive: tolerate malformed commands_run without crashing.
    commands = [c for c in raw_commands if isinstance(c, dict)] if isinstance(raw_commands, list) else []
    malformed = (len(raw_commands) - len(commands)) if isinstance(raw_commands, list) else 1
    if malformed:
        findings.append(f"{malformed} malformed command entry(ies) in commands_run")

    command_classes = {cmd.get("class") for cmd in commands if cmd.get("result") == "pass"}
    blocked = [cmd for cmd in commands if cmd.get("result") == "blocked"]
    # A fail entry superseded by a LATER pass of the same command is a resolved
    # failure (the honest RED->GREEN shape an escalation leaves behind), not an
    # outstanding one. Only outstanding failures block. The command string must
    # be a real, non-empty match -- two entries that both omit `cmd` are not
    # "the same command" (None == None must never excuse a failure).
    failed = [
        cmd for idx, cmd in enumerate(commands)
        if cmd.get("result") == "fail"
        and not (
            isinstance(cmd.get("cmd"), str) and cmd.get("cmd", "").strip()
            and any(
                later.get("cmd") == cmd.get("cmd") and later.get("result") == "pass"
                for later in commands[idx + 1:]
            )
        )
    ]
    missing_class = [cmd for cmd in commands if not cmd.get("class")]

    non_trivial = (
        task_class in {"medium", "mission"}
        or risk in {"medium", "high"}
        or security_sensitive
    )
    if task_class is None:
        soft_warnings.append("task_class is unset; defaulting to risk-tier-derived gates")

    # Extend the deep-evidence principle to commands: a 'pass' with no verifiable
    # evidence handle is the cheapest way to game the gate, so require one.
    unevidenced = [
        c for c in commands if c.get("result") == "pass" and not has_evidence(c.get("evidence"))
    ]
    if non_trivial and unevidenced:
        findings.append(
            f"{len(unevidenced)} pass-labeled command(s) missing verifiable evidence"
        )

    if failed:
        findings.append(f"{len(failed)} verification command(s) failed")
    if missing_class:
        findings.append(f"{len(missing_class)} command(s) missing class field")

    if non_trivial:
        if not isinstance(implementer, str) or not implementer.strip():
            findings.append("non-trivial work requires a named implementer")
        findings.extend(
            artifact_findings(record.get("validation_contract"), "validation_contract", base_dir)
        )
        findings.extend(
            review_findings(record.get("independent_review"), "independent_review", implementer)
        )
        # UNDERSTAND gate: the first Hard Rule (map the change before editing) is
        # only real if it is checked. By implementation, the context map must
        # locate the change and corroborate it with callers or tests.
        if status in POST_IMPLEMENT_STATUSES:
            repo_map = record.get("repo_map") or {}
            located = (repo_map.get("entry_points") or []) or (repo_map.get("likely_files") or [])
            corroborated = (repo_map.get("callers_checked") or []) or (repo_map.get("tests") or [])
            if not (located and corroborated):
                findings.append(
                    "non-trivial work requires a substantive context map (repo_map): "
                    "entry_points/likely_files plus callers_checked or tests"
                )
        if status in TERMINAL_STATUSES:
            if record.get("completion_record") is None:
                findings.append(
                    f"non-trivial work at status '{status}' requires a completion_record with evidence"
                )
            else:
                findings.extend(
                    artifact_findings(record.get("completion_record"), "completion_record", base_dir)
                )

    if security_sensitive or risk == "high":
        findings.extend(
            review_findings(record.get("security_review"), "security_review", implementer)
        )

    repair_attempts = record.get("repair_attempts")
    repeated = bool(record.get("repeated_failure")) or (
        isinstance(repair_attempts, int)
        and not isinstance(repair_attempts, bool)
        and repair_attempts >= 2
    )
    if repeated and not has_evidence(record.get("harness_update")):
        findings.append(
            "repeated verification failure requires a durable harness_update "
            "(retrospective evidence: rule/test/hook/checklist/template), "
            "not a repeated chat correction"
        )

    # Escalation evidence gate (v4.2 model routing): a recorded model escalation
    # is legitimate only when it cites deterministic failing evidence already in
    # commands_run. Model self-report ("it looked stuck", "tests pass") is not
    # evidence -- confident-wrong is the dominant failure mode on cheap and
    # frontier models alike. (The `escalated` status stays a human-input valve
    # governed by escalation_reason; this gate binds only model-tier escalation.)
    escalations = record.get("escalations")
    escalations = escalations if isinstance(escalations, list) else []
    # Only fail entries that carry an evidence handle can back an escalation: a
    # bare {"result": "fail"} row is free to fabricate. Still a floor, not proof
    # (all rows are self-reported); run-evidence re-execution is the backstop.
    failed_cmds = {
        c.get("cmd") for c in commands
        if c.get("result") == "fail" and isinstance(c.get("cmd"), str)
        and has_evidence(c.get("evidence"))
    }
    for esc in escalations:
        if not isinstance(esc, dict):
            continue  # shape errors are check-record's job
        cited = esc.get("failing_commands")
        cited = [c for c in cited if isinstance(c, str)] if isinstance(cited, list) else []
        unmatched = [c for c in cited if c not in failed_cmds]
        if not cited or unmatched:
            detail = f" (unmatched or unevidenced: {', '.join(unmatched)})" if unmatched else ""
            findings.append(
                f"escalation to {esc.get('to_model')!r} cites no evidenced failing "
                f"check in commands_run{detail}; self-report escalation is not evidence"
            )

    if status in POST_IMPLEMENT_STATUSES and not record.get("minimality_decision"):
        findings.append("minimality_decision is required before implementation can pass gates")

    findings.extend(
        _risk_tier_findings(risk, commands, command_classes, status, record)
    )

    if blocked:
        findings.append(f"{len(blocked)} verification command(s) blocked; ensure rationale is recorded")

    # Ledger-grounded advisories (delegation ledger, when present). Brief size is
    # purely advisory: an oversized hand-off brief signals context bloat but
    # never blocks a ship. Absent ledger (most repos) no-ops.
    delegations = _read_delegation_ledger(base_dir)
    if delegations:
        limit = brief_char_limit(_nearest_config(base_dir))
        soft_warnings.extend(_brief_size_advisories(delegations, limit))

    for note in soft_warnings:
        print(f"note: {note}")

    # Reality layer: ground the record in the real git diff when --against-diff
    # is requested. This catches phantom completion, unmapped scope, a diff-
    # derived risk floor, missing bugfix tests, stale review hashes, and promotes
    # diff-audit secret/test-weakening warnings to blocking at medium+.
    if getattr(args, "against_diff", False):
        try:
            diff_findings = qlreal.verify_gates_against_diff(
                record,
                risk,
                base=getattr(args, "base", "HEAD"),
                cwd=Path.cwd(),
                record_path=record_path,
            )
            findings.extend(diff_findings)
        except SystemExit as exc:
            findings.append(
                "could not read git diff for --against-diff (exit %s); "
                "ensure this is a git repository" % (exc.code,)
            )

    if findings:
        for finding in findings:
            print(f"warning: {finding}")
        return 1

    print("verification gates look sufficient for recorded risk tier")
    return 0


REQUIRED_STEPS = [
    "INTAKE",
    "EXPLORE",
    "MINIMALITY_GATE",
    "PLAN",
    "IMPLEMENT_SLICE",
    "VERIFY",
    "REVIEW",
    "PACKAGE",
    "RETROSPECT",
]

# Single source of truth for the config schema/version. check_config rejects a
# config that does not declare this version so the skill, config, CHANGELOG, and
# npm package cannot silently drift apart.
EXPECTED_CONFIG_VERSION = "5.1.0"

# Step model-class floor (P3.18): the planner (PLAN) and orchestrator
# (ORCHESTRATE) steps must route to the strongest reasoning class so "the right
# LLM for the right job" is deterministically backed, not just prose.
# check_config enforces this.
STRONG_REASONING_STEPS = {"PLAN", "ORCHESTRATE"}


def _reviewer_heterogeneity(
    profiles: dict[str, Any], steps: list[Any], routing: Any
) -> list[str]:
    """Return errors if the implementer and validator collapse to one model.

    medium+ tasks require an independent reviewer, which is meaningless if the
    same model both writes and reviews the diff. Three checks: (1) the profile
    ``model`` fields, (2) if model_routing is configured, the resolved model for
    the implementer leg (``main_session`` or the default host's IMPLEMENT_SLICE
    class) vs the reviewer leg (the ``quality-loop-reviewer`` agent entry or the
    default host's REVIEW class) -- across hosts, and (3) the resolved model
    FAMILIES (explicit ``family`` field or well-known-prefix match), because a
    different id is not a different reviewer when both ids are the same model
    behind aliases (``sonnet`` vs ``claude-sonnet-4-5``). Placeholder models and
    unknown families are skipped so an unfilled config does not false-positive;
    ``allow_same_family: true`` is the explicit escape hatch for same-family
    (never same-model) setups.
    """
    errors: list[str] = []

    impl_profile = profiles.get("implementer", {}) if isinstance(profiles, dict) else {}
    rev_profile = profiles.get("fresh_reviewer", {}) if isinstance(profiles, dict) else {}
    impl_model = impl_profile.get("model") if isinstance(impl_profile, dict) else None
    rev_model = rev_profile.get("model") if isinstance(rev_profile, dict) else None
    if (
        isinstance(impl_model, str) and isinstance(rev_model, str)
        and impl_model and rev_model
        and impl_model.strip().lower() == rev_model.strip().lower()
        and not _is_placeholder_model(impl_model)
    ):
        errors.append(
            f"reviewer heterogeneity: implementer and fresh_reviewer are both "
            f"routed to {impl_model!r}; medium+ tasks require a different model "
            f"for review (use a different model or model_class)"
        )

    if not isinstance(routing, dict):
        return errors
    topo = qlroute.resolve_routing({"model_routing": routing})
    host_models = topo["host_models"]
    default_host = topo["default_host"]

    impl_class = None
    rev_class = None
    for step in (steps if isinstance(steps, list) else []):
        if not isinstance(step, dict):
            continue
        if step.get("step") == "IMPLEMENT_SLICE":
            impl_class = step.get("model_class")
        elif step.get("step") == "REVIEW":
            rev_class = step.get("model_class")

    main_session = topo["main_session"]
    if main_session:
        impl_host = main_session.get("host")
        impl_cls = main_session.get("class") or impl_class
        impl_block = qlroute.class_block(host_models, impl_host, impl_cls)
        impl_resolved = main_session.get("model") or impl_block.get("model")
        # The block's declared family describes the block's model; it must not
        # be applied to an explicit main_session.model override.
        impl_declared_family = (
            impl_block.get("family") if not main_session.get("model") else None
        )
    else:
        impl_host = default_host
        impl_cls = impl_class
        impl_block = qlroute.class_block(host_models, impl_host, impl_cls)
        impl_resolved = impl_block.get("model")
        impl_declared_family = impl_block.get("family")

    # The `quality-loop-reviewer` agents entry (string or object) is what
    # setup-models actually writes into the reviewer's agent file, so it is the
    # effective reviewer; the REVIEW step's model_class is doctrine. When both
    # are concrete and resolve to different models the config disagrees with
    # itself -- flag it rather than silently trusting either.
    rev_agent_entry = topo["agents"].get("quality-loop-reviewer")
    step_block = qlroute.class_block(host_models, default_host, rev_class)
    step_resolved = step_block.get("model")
    if rev_agent_entry and rev_agent_entry.get("class"):
        rev_host = rev_agent_entry.get("host")
        rev_cls = rev_agent_entry.get("class")
        if (
            rev_class and rev_cls != rev_class
            and not _is_placeholder_model(step_resolved)
        ):
            entry_block = qlroute.class_block(host_models, rev_host, rev_cls)
            entry_resolved = entry_block.get("model")
            if (
                not _is_placeholder_model(entry_resolved)
                and entry_resolved.strip().lower() != step_resolved.strip().lower()
            ):
                errors.append(
                    f"reviewer heterogeneity: steps.REVIEW model_class={rev_class!r} "
                    f"resolves to {step_resolved!r} but model_routing.agents."
                    f"quality-loop-reviewer ({rev_cls!r} on host {rev_host!r}) "
                    f"resolves to {entry_resolved!r}; align them -- the agents "
                    f"entry is what setup-models applies"
                )
    else:
        rev_host = default_host
        rev_cls = rev_class
    rev_block = qlroute.class_block(host_models, rev_host, rev_cls)
    rev_resolved = rev_block.get("model")

    if not (impl_host and rev_host and impl_cls and rev_cls):
        return errors

    # An explicit distinct main_session.model breaks the "same class => same
    # model" implication, so the same-class branch must not fire over it.
    ms_model = (
        main_session.get("model")
        if main_session and isinstance(main_session.get("model"), str)
        else None
    )
    if impl_host == rev_host and impl_cls == rev_cls:
        distinct_override = (
            ms_model and isinstance(rev_resolved, str) and rev_resolved.strip()
            and ms_model.strip().lower() != rev_resolved.strip().lower()
        )
        if not distinct_override and not (
            _is_placeholder_model(impl_resolved) or _is_placeholder_model(rev_resolved)
        ):
            errors.append(
                f"reviewer heterogeneity: IMPLEMENT_SLICE and REVIEW both "
                f"use model_class={impl_cls!r} on host {impl_host!r}; medium+ "
                f"tasks require a different model for review (use a different "
                f"model or model_class)"
            )
        if not distinct_override:
            return errors

    if _is_placeholder_model(impl_resolved) or _is_placeholder_model(rev_resolved):
        return errors

    # Case-insensitive: `GPT-5.6-SOL` vs `gpt-5.6-sol` is one model, not two.
    if impl_resolved.strip().lower() == rev_resolved.strip().lower():
        errors.append(
            f"reviewer heterogeneity: implementer ({impl_resolved!r} on host "
            f"{impl_host!r}) and fresh_reviewer ({rev_resolved!r} on host "
            f"{rev_host!r}) resolve to the same model; use a different model "
            f"for review"
        )
        return errors

    impl_family = qlroute.model_family(impl_resolved, impl_declared_family)
    rev_family = qlroute.model_family(rev_resolved, rev_block.get("family"))
    if (
        impl_family and rev_family and impl_family == rev_family
        and not topo["allow_same_family"]
    ):
        errors.append(
            f"reviewer heterogeneity: implementer ({impl_resolved!r} on host "
            f"{impl_host!r}) and fresh_reviewer ({rev_resolved!r} on host "
            f"{rev_host!r}) resolve to the same model family {impl_family!r}; "
            f"harness diversity does not guarantee model heterogeneity -- use a "
            f"different family for review, or set \"allow_same_family\": true "
            f"to accept the risk explicitly"
        )
    return errors


# One implementation for the package (family checks in the routing module need
# it too); this preserves the module-local name for existing call sites.
_is_placeholder_model = qlroute.is_placeholder_model



def check_config(args: argparse.Namespace) -> int:
    config = load_json(Path(args.config))
    errors: list[str] = []

    for key in ("version", "profiles", "steps"):
        if key not in config:
            errors.append(f"missing required field: {key}")

    version = config.get("version")
    if "version" in config and version != EXPECTED_CONFIG_VERSION:
        errors.append(
            f"config version is {version!r}; expected {EXPECTED_CONFIG_VERSION!r} "
            f"(the skill, config, CHANGELOG, and npm package share one version)"
        )

    profiles = config.get("profiles", {})
    if not isinstance(profiles, dict) or not profiles:
        errors.append("profiles must be a non-empty object")

    steps = config.get("steps", [])
    if not isinstance(steps, list) or not steps:
        errors.append("steps must be a non-empty array")
    else:
        seen = []
        for idx, step in enumerate(steps):
            name = step.get("step")
            seen.append(name)
            if name not in REQUIRED_STEPS:
                errors.append(f"step[{idx}] has unknown step name: {name!r}")
            profile = step.get("profile")
            if profile not in profiles:
                errors.append(f"step {name!r} references undefined profile: {profile!r}")
            if not step.get("required_artifacts"):
                errors.append(f"step {name!r} must declare required_artifacts")
            if not step.get("gates"):
                errors.append(f"step {name!r} must declare gates")
            if name in STRONG_REASONING_STEPS and step.get("model_class") not in (
                None,
                "strong_reasoning",
            ):
                errors.append(
                    f"step {name!r} is reasoning-heavy and must route to "
                    f"model_class 'strong_reasoning', not "
                    f"{step.get('model_class')!r}"
                )
        missing_steps = [s for s in REQUIRED_STEPS if s not in seen]
        if missing_steps:
            errors.append("missing lifecycle steps: " + ", ".join(missing_steps))

    if "policy_guard" not in config:
        errors.append("config should define policy_guard for deterministic enforcement")

    routing = config.get("routing_defaults", {})
    for tier in ("low", "medium", "high"):
        if tier not in routing:
            errors.append(f"routing_defaults missing tier: {tier}")

    memory = config.get("memory")
    if memory is not None:
        errors.extend(qlmem.validate_memory_config(memory))

    control = config.get("control_plane")
    if control is not None:
        errors.extend(qlctl.validate_control_plane(control))

    routing = config.get("model_routing")
    if routing is not None:
        errors.extend(qlroute.validate_model_routing(routing))

    errors.extend(_reviewer_heterogeneity(profiles, steps, routing))

    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print("config ok")
    return 0


def _latest_run_summary(runs_dir: Path) -> dict[str, Any]:
    """Read the most recent run journal and return a compact summary."""
    if not runs_dir.is_dir():
        return {}
    run_dirs = sorted(
        (d for d in runs_dir.iterdir() if d.is_dir()),
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    for run_dir in run_dirs:
        journal = run_dir / "journal.jsonl"
        if not journal.is_file():
            continue
        events: list[dict[str, Any]] = []
        for line in journal.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if not events:
            continue
        steps = [str(e.get("step", "")) for e in events if e.get("step")]
        last = events[-1]
        return {
            "run_id": run_dir.name,
            "steps": steps,
            "last_step": str(last.get("step", "")),
            "last_event": last,
            "event_count": len(events),
        }
    return {}


def _latest_record_summary(cwd: Path) -> dict[str, Any]:
    """Return open risks and status from the most recent agent record."""
    for path in (cwd / ".quality-loop" / "agent-record.json", cwd / "agent-record.json"):
        if path.is_file():
            try:
                data = load_json(path)
            except (json.JSONDecodeError, OSError):
                return {"path": str(path), "error": "invalid JSON"}
            return {
                "path": str(path),
                "task_id": data.get("task_id", "?"),
                "goal": data.get("goal", ""),
                "status": data.get("status", "?"),
                "risk_tier": data.get("risk_tier", "?"),
                "open_risks": data.get("open_risks", []),
                "review_findings": data.get("review_findings", []),
            }
    return {}


def _progress_tail(cwd: Path, max_lines: int = 15) -> str:
    for path in (cwd / ".quality-loop" / "progress.md", cwd / "progress.md"):
        if path.is_file():
            lines = path.read_text(encoding="utf-8").splitlines()
            return "\n".join(lines[-max_lines:]) if lines else ""
    return ""


def cmd_brief(args: argparse.Namespace) -> int:
    cwd = Path(getattr(args, "cwd", ".")).resolve()
    runs_dir = cwd / ".quality-loop" / "runs"
    run_summary = _latest_run_summary(runs_dir)
    record_summary = _latest_record_summary(cwd)
    progress = _progress_tail(cwd)

    budget = max(100, getattr(args, "budget", 800))
    mem_dir = qlmem.resolve_memory_dir(args.location, cwd=cwd)
    project_lessons = qlmem.load_lessons(mem_dir)
    global_dir = qlmem.resolve_global_memory_dir()
    global_lessons = qlmem.load_lessons(global_dir)
    goal = record_summary.get("goal", "") if isinstance(record_summary, dict) else ""
    risk = record_summary.get("risk_tier", "low") if isinstance(record_summary, dict) else "low"
    risk = risk if risk in RISK_TIERS else "low"
    if not global_lessons:
        selected_project = qlmem.recall(project_lessons, goal or "", [], risk, budget)
        selected_global: list[dict[str, Any]] = []
        project_budget = budget
        global_budget = 0
    else:
        project_budget = max(1, int(budget * 0.6))
        global_budget = max(1, budget - project_budget)
        selected_project = qlmem.recall(project_lessons, goal or "", [], risk, project_budget)
        selected_global = qlmem.recall(global_lessons, goal or "", [], risk, global_budget)
    selected = selected_project + selected_global
    if selected_global:
        lessons_text = qlmem.format_digest(selected_project, project_budget) + "\n[global] " + qlmem.format_digest(selected_global, global_budget)
    else:
        lessons_text = qlmem.format_digest(selected_project, budget)

    sections: list[str] = []
    if record_summary and "error" not in record_summary:
        sections.append(
            "## Last record\n"
            f"goal: {record_summary.get('goal', '?')}\n"
            f"status: {record_summary.get('status', '?')}  risk: {record_summary.get('risk_tier', '?')}"
        )
        risks = record_summary.get("open_risks", [])
        if risks:
            risk_lines = "\n".join(f"  - {r}" for r in risks[:8])
            sections.append(f"## Open risks\n{risk_lines}")
    elif record_summary and "error" in record_summary:
        sections.append(f"## Last record\n{record_summary['error']}")
    else:
        sections.append("## Last record\nnone found")

    if run_summary:
        steps_str = " -> ".join(run_summary["steps"][-8:])
        sections.append(
            "## Last run\n"
            f"run: {run_summary['run_id']}  steps: {steps_str}\n"
            f"last event: {run_summary['last_step']}"
        )
    else:
        sections.append("## Last run\nnone found")

    sections.append(f"## Lessons ({len(selected)} recalled)\n{lessons_text}")

    if progress:
        sections.append(f"## Progress (tail)\n{progress}")
    else:
        sections.append("## Progress\nno progress.md found")

    config_path = getattr(args, "config", None)
    routing_info = qlroute.brief_routing_info(cwd, Path(config_path) if config_path else None)
    sections.append("## Model routing\n" + "\n".join(routing_info["lines"]))

    next_hint = "Run the loop on the next task, or resume an incomplete one."
    if record_summary and "error" not in record_summary and record_summary.get("status") not in ("done", "?"):
        next_hint = f"Resume incomplete task: {record_summary.get('goal', '?')} (status: {record_summary.get('status', '?')})"
    elif run_summary and run_summary.get("last_step") == "PACKAGE":
        next_hint = "Last run shipped. Run retrospective or start the next task."
    sections.append(f"## Suggested next step\n{next_hint}")

    if getattr(args, "json", False):
        print(json.dumps({
            "record": record_summary,
            "run": run_summary,
            "lessons_recalled": len(selected),
            "lessons_digest": lessons_text,
            "progress": progress,
            "model_routing": routing_info,
            "next_step": next_hint,
        }, indent=2, default=str))
    else:
        print("\n\n".join(sections))
    return 0




def _run_case_gates(
    record: dict[str, Any], delegations: list[dict[str, Any]] | None = None
) -> tuple[int, list[str], list[str]]:
    """Run the real verify_gates on a record in-process, capturing findings.

    Writes the record to a temp file (verify_gates loads from disk and resolves
    artifact paths relative to it) and captures the ``warning:`` (blocking
    findings) and ``note:`` (advisory) lines it emits. When ``delegations`` is
    given, they are written to a temp ``.quality-loop/delegations.jsonl`` so
    ledger-grounded checks (brief size, isolation evidence) run against a real
    ledger. This exercises the exact production code path a running loop would
    hit — no parallel classifier to drift from the shipping gate.
    """
    import contextlib
    import io
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        rec_path = Path(tmp) / "agent-record.json"
        rec_path.write_text(json.dumps(record))
        if delegations:
            ledger_dir = Path(tmp) / ".quality-loop"
            ledger_dir.mkdir(parents=True, exist_ok=True)
            (ledger_dir / "delegations.jsonl").write_text(
                "\n".join(json.dumps(d) for d in delegations) + "\n"
            )
        vg_args = argparse.Namespace(record=str(rec_path), against_diff=False, base="HEAD")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = verify_gates(vg_args)
    findings: list[str] = []
    advisories: list[str] = []
    for line in buf.getvalue().splitlines():
        stripped = line.strip()
        if stripped.startswith("warning:"):
            findings.append(stripped[len("warning:"):].strip())
        elif stripped.startswith("note:"):
            advisories.append(stripped[len("note:"):].strip())
    return rc, findings, advisories


def _eval_record_case(case: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    """Assert the record gates (risk floor + verify-gates findings/advisories)."""
    record = case.get("record", {})
    mismatches: list[str] = []

    floor, markers = detect_risk_floor(record)
    gates_rc, findings, advisories = _run_case_gates(record, delegations=case.get("delegations"))

    if "risk_floor" in expect and expect["risk_floor"] != floor:
        mismatches.append(f"risk_floor: expected {expect['risk_floor']!r}, got {floor!r}")
    for marker in expect.get("floor_markers", []):
        if marker not in markers:
            mismatches.append(f"floor_markers missing {marker!r} (got {markers})")
    if "gates_exit" in expect and expect["gates_exit"] != gates_rc:
        mismatches.append(f"gates_exit: expected {expect['gates_exit']}, got {gates_rc}")
    for needle in expect.get("findings_include", []):
        if not any(needle in f for f in findings):
            mismatches.append(f"expected a finding containing {needle!r}; got {findings}")
    for needle in expect.get("findings_exclude", []):
        if any(needle in f for f in findings):
            mismatches.append(f"unexpected finding containing {needle!r}; got {findings}")
    for needle in expect.get("advisories_include", []):
        if not any(needle in a for a in advisories):
            mismatches.append(f"expected an advisory containing {needle!r}; got {advisories}")
    for needle in expect.get("advisories_exclude", []):
        if any(needle in a for a in advisories):
            mismatches.append(f"unexpected advisory containing {needle!r}; got {advisories}")
    return mismatches


def _eval_version_case(case: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    """Assert the version trust chain against explicit inputs (no git/env)."""
    spec = case.get("version", {})
    errors, warnings = version_consistency_findings(
        spec.get("package"),
        spec.get("skill"),
        spec.get("tag"),
        enforce_tag=bool(spec.get("enforce_tag")),
    )
    rc = 1 if errors else 0
    mismatches: list[str] = []
    if "exit" in expect and expect["exit"] != rc:
        mismatches.append(f"exit: expected {expect['exit']}, got {rc} (errors={errors})")
    for needle in expect.get("errors_include", []):
        if not any(needle in e for e in errors):
            mismatches.append(f"expected an error containing {needle!r}; got {errors}")
    for needle in expect.get("warnings_include", []):
        if not any(needle in w for w in warnings):
            mismatches.append(f"expected a warning containing {needle!r}; got {warnings}")
    for needle in expect.get("errors_exclude", []):
        if any(needle in e for e in errors):
            mismatches.append(f"unexpected error containing {needle!r}; got {errors}")
    return mismatches


_EVAL_CASE_HANDLERS = {
    "record_gates": _eval_record_case,
    "version": _eval_version_case,
}


def eval_cases(args: argparse.Namespace) -> int:
    cases_dir = Path(args.cases_dir)
    if cases_dir.is_dir():
        case_files = sorted(cases_dir.glob("*.json"))
    else:
        case_files = [cases_dir]
    if not case_files:
        print(f"error: no eval cases found in {cases_dir}", file=sys.stderr)
        return 2

    if args.config:
        cfg_args = argparse.Namespace(config=args.config)
        if check_config(cfg_args) != 0:
            print("error: config check failed", file=sys.stderr)
            return 1

    total = 0
    failed = 0
    for case_file in case_files:
        case = load_json(case_file)
        name = case.get("name", case_file.stem)
        expect = case.get("expect", {})
        handler = _EVAL_CASE_HANDLERS.get(case.get("check", "record_gates"))
        if handler is None:
            mismatches = [f"unknown case check kind: {case.get('check')!r}"]
        else:
            mismatches = handler(case, expect)

        total += 1
        if mismatches:
            failed += 1
            print(f"FAIL {name}")
            for mismatch in mismatches:
                print(f"  - {mismatch}")
        else:
            print(f"PASS {name}")

    print(f"\n{total - failed}/{total} eval cases passed")
    return 1 if failed else 0


def _check_ac_coverage(record: dict[str, Any]) -> list[str]:
    """Check that each acceptance criterion with a proving_command has a matching pass command."""
    findings: list[str] = []
    criteria = record.get("acceptance_criteria", [])
    commands = record.get("commands_run", [])
    pass_cmds = [c.get("cmd", "") for c in commands if isinstance(c, dict) and c.get("result") == "pass"]

    for idx, ac in enumerate(criteria):
        if isinstance(ac, dict) and ac.get("proving_command"):
            proving = ac["proving_command"]
            if proving not in pass_cmds:
                findings.append(
                    f"acceptance_criteria[{idx}].proving_command {proving!r} not found in "
                    f"commands_run with result=pass"
                )
        elif isinstance(ac, dict) and not ac.get("proving_command"):
            findings.append(
                f"acceptance_criteria[{idx}] has no proving_command; "
                f"each criterion should name the check that proves it"
            )
    return findings


HELPER_MODULES = (
    "quality_loop.py",
    "quality_loop_core.py",
    "quality_loop_memory.py",
    "quality_loop_reality.py",
    "quality_loop_routing.py",
)


def helper_integrity() -> dict[str, str]:
    """sha256 of each helper module as installed, so hooks/CI can detect a
    locally modified gate script by comparing against the pinned release."""
    here = Path(__file__).resolve().parent
    out: dict[str, str] = {}
    for name in HELPER_MODULES:
        path = here / name
        try:
            out[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            out[name] = "missing"
    return out


# ---------------------------------------------------------------------------
# Version trust chain
# ---------------------------------------------------------------------------
# For a project whose brand is checkable claims, the release surface itself must
# pass a gate: the npm package version, the SKILL.md frontmatter version, and the
# latest git tag must agree. package.json <-> SKILL.md drift is a hard failure
# everywhere (they ship together). A tag that lags the files is expected between
# releases, so it is a local warning; it is only hard-failed on a release-framed
# CI event (push to main / a tag / a release) where the tag is supposed to match.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_PACKAGE_JSON = _REPO_ROOT / "packages" / "npm" / "package.json"
_SKILL_MD = _REPO_ROOT / "SKILL.md"
_SKILL_VERSION_RE = re.compile(r"^\s*version:\s*\"?([^\"\n]+?)\"?\s*$", re.MULTILINE)


def _read_package_version(path: Path) -> str | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    version = data.get("version") if isinstance(data, dict) else None
    return version if isinstance(version, str) and version.strip() else None


def _read_skill_version(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    # Only trust a version line inside the leading YAML frontmatter block.
    if text.startswith("---"):
        end = text.find("\n---", 3)
        text = text[: end if end != -1 else len(text)]
    match = _SKILL_VERSION_RE.search(text)
    return match.group(1).strip() if match else None


def _latest_git_tag() -> str | None:
    """Most recent semver-ish tag, or None when the repo has no tags (a shallow
    or fresh clone legitimately has none — never treat that as a hard error)."""
    code, out, _ = qlcore.git_capture(["tag", "--sort=-v:refname"])
    if code != 0:
        return None
    for line in out.splitlines():
        tag = line.strip()
        if tag:
            return tag
    return None


def _ci_enforces_tag() -> bool:
    """A release-framed CI event is where the tag is expected to match: a push to
    main, a tag push, or a published release. Ordinary PR CI only warns so a tag
    that intentionally lags the files does not block the PR."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return False
    if os.environ.get("GITHUB_EVENT_NAME") == "release":
        return True
    ref = os.environ.get("GITHUB_REF", "")
    return ref == "refs/heads/main" or ref.startswith("refs/tags/")


def version_consistency_findings(
    package_version: str | None,
    skill_version: str | None,
    tag: str | None,
    *,
    enforce_tag: bool,
) -> tuple[list[str], list[str]]:
    """Pure version trust-chain check. Returns (errors, warnings).

    - package.json vs SKILL.md mismatch (or either missing) is always an error.
    - tag vs package.json mismatch is an error only when ``enforce_tag`` (a
      release-framed CI event), otherwise a warning. A missing tag is always a
      warning — a fresh/shallow clone has none.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if package_version is None:
        errors.append("could not read npm package version (packages/npm/package.json)")
    if skill_version is None:
        errors.append("could not read SKILL.md frontmatter version")
    if (
        package_version is not None
        and skill_version is not None
        and package_version != skill_version
    ):
        errors.append(
            f"version mismatch: package.json is {package_version!r} but SKILL.md is "
            f"{skill_version!r} (they ship together and must match)"
        )

    reference = package_version or skill_version
    tag_version = tag[1:] if isinstance(tag, str) and tag.startswith("v") else tag
    if tag is None:
        warnings.append("no git tags found; skipping tag-consistency check")
    elif reference is not None and tag_version != reference:
        msg = (
            f"latest git tag {tag!r} does not match the file version {reference!r}"
        )
        (errors if enforce_tag else warnings).append(
            msg + ("" if enforce_tag else " (warning locally; enforced on release CI)")
        )
    return errors, warnings


def check_version(args: argparse.Namespace) -> int:
    package_version = _read_package_version(_PACKAGE_JSON)
    skill_version = _read_skill_version(_SKILL_MD)
    tag = _latest_git_tag()
    enforce_tag = bool(getattr(args, "enforce_tag", False)) or _ci_enforces_tag()

    errors, warnings = version_consistency_findings(
        package_version, skill_version, tag, enforce_tag=enforce_tag
    )
    print(
        "versions: package.json=%s SKILL.md=%s latest-tag=%s (tag %s)"
        % (
            package_version,
            skill_version,
            tag,
            "enforced" if enforce_tag else "advisory",
        )
    )
    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    return 1 if errors else 0


def verify(args: argparse.Namespace) -> int:
    """Umbrella verification: record-shape gates + diff-grounded checks + evidence re-execution + AC coverage."""
    import contextlib
    import io

    record_path = Path(args.record)
    record = load_json(record_path)
    requested_base = getattr(args, "base", "HEAD")
    # Resolve the base once and reuse it for every diff-grounded section. On a
    # fresh/detached checkout the requested ref (often origin/main) may not exist;
    # rather than let each section die with git's raw exit 128, fall back to a
    # sane ref and tell the caller how to pin it explicitly.
    base, base_hint = _resolve_base(requested_base)
    all_findings: list[str] = []
    all_warnings: list[str] = []
    if base_hint:
        all_warnings.append(base_hint)
    sections: list[tuple[str, int, str]] = []  # (name, exit_code, output)

    def _run_section(fn) -> tuple[int, str]:
        """Run a section callable, capturing stdout/stderr.

        Survives a SystemExit (e.g. git's 129 when not in a repository) so the
        unified report is always emitted. Returns (exit_code, captured_output).
        """
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                rc = fn()
        except SystemExit as exc:
            rc = exc.code if isinstance(exc.code, int) and exc.code is not None else 1
            if not buf.getvalue().strip():
                buf.write(f"section aborted (exit {rc})")
        return int(rc), buf.getvalue().strip()

    # 1. Record-shape + diff-grounded gates
    vg_args = argparse.Namespace(record=str(record_path), against_diff=True, base=base)
    vg_rc, vg_out = _run_section(lambda: verify_gates(vg_args))
    sections.append(("verify-gates (record + diff)", vg_rc, vg_out))
    if vg_rc != 0:
        for line in vg_out.splitlines():
            line = line.strip()
            if line.startswith("warning:"):
                all_warnings.append(line[len("warning:"):].strip())

    # 2. Diff audit (wrapped so a non-git repo produces a failed section, not a
    #    bare exit 129 with no report). Parse regardless of exit code: advisory
    #    findings are emitted at exit 0 and must still surface as warnings, while
    #    blocking findings (exit 1) roll into all_findings and fail the umbrella.
    da_args = argparse.Namespace(base=base, staged=False, max_files=12, max_lines=600)
    da_rc, da_out = _run_section(lambda: diff_audit(da_args))
    sections.append(("diff-audit", da_rc, da_out))
    try:
        result = json.loads(da_out)
        all_findings.extend(result.get("blocking", []))
        all_warnings.extend(result.get("advisory", []))
    except json.JSONDecodeError:
        if da_rc != 0 and da_out and "section aborted" not in da_out:
            all_findings.append(da_out)

    # 3. Evidence re-execution (if pass commands exist)
    pass_cmds = [c for c in record.get("commands_run", []) if isinstance(c, dict) and c.get("result") == "pass"]
    if pass_cmds:
        re_args = argparse.Namespace(
            record=str(record_path), base=base,
            red_green=getattr(args, "red_green", False), timeout=30,
        )
        re_rc, re_out = _run_section(lambda: qlreal.cmd_run_evidence(re_args))
        sections.append(("run-evidence (re-execution)", re_rc, re_out))
        if re_rc != 0:
            try:
                result = json.loads(re_out)
                for f in result.get("findings", []):
                    all_findings.append(f)
            except json.JSONDecodeError:
                all_findings.append("run-evidence reported failures (see output above)")
    else:
        sections.append(("run-evidence", 0, "skipped (no pass commands in record)"))

    # 4. AC-to-command coverage
    ac_findings = _check_ac_coverage(record)
    if ac_findings:
        sections.append(("AC coverage", 1, "\n".join(ac_findings)))
        all_findings.extend(ac_findings)
    else:
        sections.append(("AC coverage", 0, "ok"))

    # 5. Helper integrity (informational): sha256 of the helper modules so a
    #    hook/CI can compare against the pinned release and catch a locally
    #    modified (softened) gate script. verify cannot block on this itself —
    #    a tampered copy would lie — the value is the externally checkable hash.
    integrity = helper_integrity()
    sections.append((
        "helper-integrity (informational)",
        0,
        "\n".join(f"{name}: {digest}" for name, digest in sorted(integrity.items())),
    ))

    # 6. Require-terminal (opt-in; the CI action passes this): work must not ship
    #    with an unclosed loop. If the diff vs --base is non-empty and the record
    #    status is not terminal (package/done), fail. Uses the same diff mechanism
    #    (tracked changes + untracked non-ignored files) as the reality layer.
    if getattr(args, "require_terminal", False):
        rec_status = record.get("status")
        d_code, d_out, _ = git_capture(["diff", "--name-only", base])
        u_code, u_out, _ = git_capture(["ls-files", "--others", "--exclude-standard"])
        diff_nonempty = (d_code == 0 and bool(d_out.strip())) or (u_code == 0 and bool(u_out.strip()))
        if diff_nonempty and rec_status not in TERMINAL_STATUSES:
            finding = (
                f"work shipped without closing the loop: status is {rec_status!r} "
                f"with a non-empty diff vs {base}"
            )
            all_findings.append(finding)
            sections.append(("require-terminal", 1, finding))
        else:
            sections.append((
                "require-terminal",
                0,
                f"status={rec_status!r}; diff_nonempty={diff_nonempty}",
            ))

    # Unified report
    print("=" * 60)
    print("VERIFY — unified gate report")
    print(f"base: {base}" + (f" (requested {requested_base!r})" if base != requested_base else ""))
    if base_hint:
        print(f"note: {base_hint}")
    print("=" * 60)
    for name, rc, output in sections:
        status = "PASS" if rc == 0 else "FAIL"
        print(f"\n[{status}] {name}")
        if output and output != "ok":
            for line in output.splitlines():
                print(f"  {line}")

    print("\n" + "-" * 60)
    if all_findings:
        print(f"Findings ({len(all_findings)}):")
        for f in all_findings:
            print(f"  - {f}")
    if all_warnings:
        print(f"Warnings ({len(all_warnings)}):")
        for w in all_warnings:
            print(f"  - {w}")

    # Umbrella fails if ANY constituent section failed (verify-gates, diff-audit,
    # run-evidence, AC coverage) OR if any finding was recorded. Warnings alone
    # from diff-audit are reported but a non-zero section rc still fails the
    # umbrella, so a section exit code can never be silently swallowed.
    section_fail = any(rc != 0 for _, rc, _ in sections)
    overall = 1 if (all_findings or section_fail) else 0
    print(f"\nOverall: {'FAIL' if overall else 'PASS'}")
    return overall


def main() -> int:
    parser = argparse.ArgumentParser(description="Coding Quality Loop helper")
    sub = parser.add_subparsers(required=True)

    p_init = sub.add_parser("init-record", help="Create a new agent state record")
    p_init.add_argument("--goal", required=True)
    p_init.add_argument("--risk-tier", choices=sorted(RISK_TIERS), default="medium")
    p_init.add_argument("--task-id")
    p_init.add_argument("--output", default="agent-record.json")
    p_init.set_defaults(func=init_record)

    p_check = sub.add_parser("check-record", help="Validate a state record")
    p_check.add_argument("record")
    p_check.add_argument("--strict", action="store_true", help="Exit non-zero on warnings")
    p_check.set_defaults(func=check_record)

    p_diff = sub.add_parser("diff-audit", help="Summarize and flag git diff risks")
    p_diff.add_argument("--base", default="HEAD")
    p_diff.add_argument("--staged", action="store_true", help="Audit the staged (cached) diff instead of a base ref — pre-commit mode")
    p_diff.add_argument("--max-files", type=int, default=12)
    p_diff.add_argument("--max-lines", type=int, default=600)
    p_diff.set_defaults(func=diff_audit)

    p_gates = sub.add_parser("verify-gates", help="Check verification evidence against risk tier")
    p_gates.add_argument("record")
    p_gates.add_argument("--against-diff", action="store_true", help="Also verify the record against the real git diff (phantom completion, scope integrity, review freshness, etc.)")
    p_gates.add_argument("--base", default="HEAD", help="Git base ref for --against-diff (default HEAD)")
    p_gates.set_defaults(func=verify_gates)

    p_verify = sub.add_parser("verify", help="Umbrella: record gates + diff audit + evidence re-execution + AC coverage in one command")
    p_verify.add_argument("record")
    p_verify.add_argument("--base", default="HEAD", help="Git base ref (default HEAD)")
    p_verify.add_argument("--red-green", action="store_true", help="Also replay red_green commands at base (expect fail) and HEAD (expect pass)")
    p_verify.add_argument("--require-terminal", action="store_true", help="Fail if the diff vs --base is non-empty while the record status is not package/done (loop shipped unclosed)")
    p_verify.set_defaults(func=verify)

    p_config = sub.add_parser("check-config", help="Validate an orchestration config")
    p_config.add_argument("config")
    p_config.set_defaults(func=check_config)

    p_version = sub.add_parser(
        "check-version",
        help="Assert the npm package, SKILL.md, and latest git tag versions agree",
    )
    p_version.add_argument(
        "--enforce-tag",
        action="store_true",
        help="Hard-fail on a tag/file mismatch (auto-enabled on release-framed CI events)",
    )
    p_version.set_defaults(func=check_version)

    p_eval = sub.add_parser("eval-cases", help="Run static eval cases against expected gates")
    p_eval.add_argument("cases_dir", help="Directory of *.json cases or a single case file")
    p_eval.add_argument("--config", help="Optional orchestration config to validate first")
    p_eval.set_defaults(func=eval_cases)


    p_mrecall = sub.add_parser("memory-recall", help="Recall relevant prior lessons (budget-capped)")
    p_mrecall.add_argument("--goal", default="")
    p_mrecall.add_argument("--files", default="")
    p_mrecall.add_argument("--risk", choices=sorted(RISK_TIERS), default="low")
    p_mrecall.add_argument("--budget", type=int, default=1500)
    p_mrecall.add_argument("--location", choices=["checked_in", "local"], default="checked_in")
    p_mrecall.add_argument("--json", action="store_true")
    p_mrecall.add_argument("--no-bump", action="store_true", help="Read-only: do not increment hit counts or rewrite the store")
    p_mrecall.set_defaults(func=qlmem.cmd_recall)

    p_mcommit = sub.add_parser("memory-commit", help="Distill an agent record into durable lessons")
    p_mcommit.add_argument("record", nargs="?", help="Agent record JSON (required unless --lesson is given)")
    p_mcommit.add_argument("--lesson", help="Commit this exact lesson instead of distilling the record")
    p_mcommit.add_argument("--kind", choices=sorted(qlmem.LESSON_KINDS), default="gotcha", help="Kind for an explicit --lesson (distillation derives the kind otherwise)")
    p_mcommit.add_argument("--scope", help="Override scope glob, e.g. 'src/payments/**'")
    p_mcommit.add_argument("--location", choices=["checked_in", "local"], default="checked_in")
    p_mcommit.add_argument("--global", dest="global_store", action="store_true", help="Write to the cross-project global store (~/.quality-loop/global/)")
    p_mcommit.set_defaults(func=qlmem.cmd_commit)

    p_mprune = sub.add_parser("memory-prune", help="Dedup + cap the lessons ledger")
    p_mprune.add_argument("--max", type=int, default=200)
    p_mprune.add_argument("--max-age-days", type=int, default=365)
    p_mprune.add_argument("--location", choices=["checked_in", "local"], default="checked_in")
    p_mprune.add_argument("--global", dest="global_store", action="store_true", help="Prune the cross-project global store")
    p_mprune.set_defaults(func=qlmem.cmd_prune)

    p_mstatus = sub.add_parser("memory-status", help="Show memory store location and lesson counts")
    p_mstatus.add_argument("--location", choices=["checked_in", "local"], default="checked_in")
    p_mstatus.set_defaults(func=qlmem.cmd_status)

    p_attest = sub.add_parser("attest-review", help="Embed a recomputed diff sha256 into a review object")
    p_attest.add_argument("review", help="Path to a review JSON object to attest")
    p_attest.add_argument("--base", default="HEAD", help="Git base ref for the diff hash (default HEAD)")
    p_attest.add_argument("--output", help="Write the attested review here instead of stdout")
    p_attest.set_defaults(func=qlreal.cmd_attest_review)

    p_evidence = sub.add_parser("run-evidence", help="Re-execute recorded pass commands against the real environment")
    p_evidence.add_argument("record")
    p_evidence.add_argument("--base", default="HEAD", help="Git base ref for red-green worktree (default HEAD)")
    p_evidence.add_argument("--red-green", action="store_true", help="Replay red_green commands at base (expect fail) and HEAD (expect pass)")
    p_evidence.add_argument("--timeout", type=int, default=30, help="Per-command timeout in seconds (default 30)")
    p_evidence.set_defaults(func=qlreal.cmd_run_evidence)

    p_scan = sub.add_parser("scan-text", help="Secret-scan text from stdin (for host hook shims)")
    p_scan.add_argument("--stdin", action="store_true", help="Read text to scan from stdin")
    p_scan.set_defaults(func=qlreal.cmd_scan_text)

    p_brief = sub.add_parser("brief", help="Print a session-start project briefing (last run, risks, lessons, progress)")
    p_brief.add_argument("--budget", type=int, default=800, help="Char budget for lesson recall (default 800)")
    p_brief.add_argument("--location", choices=["checked_in", "local"], default="checked_in")
    p_brief.add_argument("--cwd", default=".", help="Working directory (default .)")
    p_brief.add_argument("--config", help="Path to quality-loop.config.json for model routing (auto-detected in cwd if omitted)")
    p_brief.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    p_brief.set_defaults(func=cmd_brief)

    p_setup = sub.add_parser("setup-models", help="Apply model_routing config to host agent files (claude-code/droid) or print settings (codex/pi)")
    p_setup.add_argument("--config", help="Path to quality-loop.config.json (auto-detected in target if omitted)")
    p_setup.add_argument("--host", choices=sorted(qlroute.SUPPORTED_HOSTS), help="Single-host configs: override model_routing.host (retarget). Multi-host topologies (object agents / main_session): apply only this host's slice (pure filter)")
    p_setup.add_argument("--target", default=".", help="Project root (default .)")
    p_setup.add_argument("--dry-run", action="store_true", help="Show what would change without writing files")
    p_setup.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    p_setup.set_defaults(func=qlroute.cmd_setup_models)

    p_cindex = sub.add_parser("control-index", help="Build/update the local control-plane index (SQLite) from host transcripts + CQL artifacts")
    p_cindex.add_argument("--cwd", default=".", help="Repo root (default .)")
    p_cindex.add_argument("--all-projects", action="store_true", help="Index every project under ~/.claude/projects, not just this repo's")
    p_cindex.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    p_cindex.set_defaults(func=qlctl.cmd_index)

    p_cserve = sub.add_parser("control-serve", help="Serve the control-plane dashboard + read-only JSON API on 127.0.0.1")
    p_cserve.add_argument("--cwd", default=".", help="Repo root (default .)")
    p_cserve.add_argument("--port", type=int, help=f"Port (default: control_plane.port or {qlctl.DEFAULT_PORT})")
    p_cserve.set_defaults(func=qlctl.cmd_serve)

    p_cingest = sub.add_parser("control-ingest", help="Record one host hook event from stdin JSON (no-op unless control_plane.enabled; never fails)")
    p_cingest.add_argument("--cwd", default=".", help="Repo root (default .)")
    p_cingest.add_argument("--event", required=True, help="Event name (SessionStart, SessionEnd, ...)")
    p_cingest.add_argument("--host", default="claude-code", help="Host emitting the event (default claude-code)")
    p_cingest.set_defaults(func=qlctl.cmd_ingest)

    p_cstatus = sub.add_parser("control-status", help="Show control-plane DB and server state")
    p_cstatus.add_argument("--cwd", default=".", help="Repo root (default .)")
    p_cstatus.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    p_cstatus.set_defaults(func=qlctl.cmd_status)

    p_cstop = sub.add_parser("control-stop", help="Stop the running control-plane server")
    p_cstop.add_argument("--cwd", default=".", help="Repo root (default .)")
    p_cstop.set_defaults(func=qlctl.cmd_stop)

    p_creport = sub.add_parser("control-report", help="Print a per-task audit bundle (goal, rung, plan, delegations, verdicts+findings, spend, sessions) as markdown or JSON")
    p_creport.add_argument("--cwd", default=".", help="Repo root (default .)")
    p_creport.add_argument("--task-id", required=True, help="Task id to report on (matches the record artifact title)")
    p_creport.add_argument("--json", action="store_true", help="Emit the bundle as JSON instead of markdown")
    p_creport.set_defaults(func=qlctl.cmd_report)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
