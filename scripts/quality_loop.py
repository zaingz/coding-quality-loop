#!/usr/bin/env python3
"""Utility helpers for the Coding Quality Loop skill.

These checks are intentionally lightweight and portable. They complement, but do
not replace, CI, tests, security scanners, or human review.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

import quality_loop_memory as qlmem


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
SECRET_PATTERNS = [
    re.compile(
        r"(?i)(api[_-]?key|secret|token|password|passwd|pwd|credential|private[_-]?key)"
        r"\s*[:=]\s*['\"][^'\"]{8,}['\"]"
    ),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[A-Z0-9]{16}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    # Unquoted assignment - the most common .env/shell/YAML leak shape - with a
    # placeholder guard that skips only obvious stubs (REPLACE_ME / <...> / ${...} /
    # example / dummy). It anchors on exact stub words, NOT a 'your_' prefix, so a
    # real value like `api_key = your_realProductionKey` is still flagged.
    re.compile(
        r"(?i)(api[_-]?key|secret|token|password|passwd|pwd|credential|private[_-]?key)\s*[:=]\s*"
        r"(?!['\"]?(?:replace_me|change_me|changeme|placeholder|example|dummy|xxx+|<|\$\{))[^\s'\"]{8,}"
    ),
    re.compile(r"(?:sk|rk)_live_[A-Za-z0-9]{16,}"),
    re.compile(r"gh[opusr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"ASIA[A-Z0-9]{16}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{35}"),
]
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
MIGRATION_MARKERS = (
    "migration",
    "migrations",
    "db/migrate",
    "schema.sql",
    "alembic",
    "prisma",
    "flyway",
    "liquibase",
    "changelog",
)
# Test-weakening markers: an agent that fixes "green" by skipping/deleting tests
# is gaming the gate. These flag added skip/xfail/.only lines in test files.
TEST_PATH_MARKERS = ("test", "spec", "__tests__")
TEST_WEAKENING_PATTERNS = [
    # Match @skip / @pytest.mark.skip / @mark.skipif / @unittest.skip etc.
    re.compile(r"^\+.*@(?:[\w.]*\.)?(?:skipif|xfail|skip)\b"),
    re.compile(r"^\+.*\.(?:only|skip)\s*\("),
    re.compile(r"^\+.*\b(?:it|test|describe)\.skip\b"),
]

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
}
# Word-boundary matched so "auth" does not fire on "author", "token" not on
# "tokenizer", "sso" not on "blossom", "charge" not on "recharge".
BOUNDARY_PATTERNS = {
    boundary: [re.compile(r"\b" + re.escape(w) + r"\b") for w in words]
    for boundary, words in BOUNDARY_KEYWORDS.items()
}


def has_evidence(value: Any) -> bool:
    """True only for real evidence: a non-empty path/string or a non-empty object.

    Bare booleans and numbers are placeholders, not evidence, and never satisfy
    a shipping gate.
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return bool(value)
    return False


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


def _nonempty(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    if isinstance(value, (int, float)):
        return True
    return False


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


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        print(f"error: file not found: {path}", file=sys.stderr)
        raise SystemExit(2)
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {path}: {exc}", file=sys.stderr)
        raise SystemExit(2)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent) as tmp:
        tmp.write(json.dumps(data, indent=2) + "\n")
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def init_record(args: argparse.Namespace) -> int:
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
        "status": "intake",
    }
    write_json(Path(args.output), record)
    print(args.output)
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

    if not isinstance(record.get("task_id"), str) or not record.get("task_id", "").strip():
        errors.append("task_id must be a non-empty string")
    if not isinstance(record.get("goal"), str) or not record.get("goal", "").strip():
        errors.append("goal must be a non-empty string")
    if record.get("risk_tier") not in RISK_TIERS:
        errors.append("risk_tier must be one of: low, medium, high")
    status = record.get("status")
    if status not in STATUSES:
        errors.append("status is not a valid lifecycle state")

    minimality = record.get("minimality_decision")
    if minimality is not None:
        if not isinstance(minimality, dict):
            errors.append("minimality_decision must be an object")
        else:
            if minimality.get("rung") not in MINIMALITY_RUNGS:
                errors.append("minimality_decision.rung is invalid")
            if not minimality.get("reason"):
                errors.append("minimality_decision.reason is required")
    if status in {"minimality_gate", "implement", "verify", "review", "package", "done", "iterating"} and not minimality:
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
        if array_key in record and not isinstance(record[array_key], list):
            errors.append(f"{array_key} must be an array")

    commands = record.get("commands_run")
    if isinstance(commands, list):
        for idx, cmd in enumerate(commands):
            if not isinstance(cmd, dict):
                errors.append(f"commands_run[{idx}] must be an object")
                continue
            if not isinstance(cmd.get("cmd"), str) or not cmd.get("cmd", "").strip():
                errors.append(f"commands_run[{idx}].cmd must be a non-empty string")
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

    if "implementer" in record and record["implementer"] is not None:
        if not isinstance(record["implementer"], str) or not record["implementer"].strip():
            errors.append("implementer must be a non-empty string")

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

    if status in {"plan", "minimality_gate", "implement", "verify", "review", "package", "done"}:
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


def redact(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def run_git(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        print(redact(proc.stderr.strip()), file=sys.stderr)
        raise SystemExit(proc.returncode)
    return proc.stdout


def diff_audit(args: argparse.Namespace) -> int:
    base = args.base or "HEAD"
    diff = run_git(["diff", "--numstat", base])
    name_only = run_git(["diff", "--name-only", base])
    patch = run_git(["diff", base])

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

    # Untracked files are invisible to `git diff`, so a brand-new module (the
    # common agent-work case) bypasses the secret/size scan entirely. Fold them in.
    untracked = [
        f.strip()
        for f in run_git(["ls-files", "--others", "--exclude-standard"]).splitlines()
        if f.strip()
    ]
    untracked_warnings: list[str] = []
    for f in untracked:
        try:
            content = Path(f).read_text(errors="replace")
        except (OSError, ValueError):
            continue
        added += len(content.splitlines())
        if f not in files:
            files.append(f)
        if any(p.search(content) for p in SECRET_PATTERNS):
            untracked_warnings.append(f"possible secret in untracked file: {f}")
    if untracked:
        untracked_warnings.append(
            f"{len(untracked)} untracked file(s) included in audit: " + ", ".join(untracked)
        )

    warnings: list[str] = list(untracked_warnings)
    if len(files) > args.max_files:
        warnings.append(f"large file count: {len(files)} files changed")
    if added + deleted > args.max_lines:
        warnings.append(f"large diff: {added + deleted} changed lines")

    dependency_edits = [f for f in files if os.path.basename(f) in DEPENDENCY_FILES]
    if dependency_edits:
        warnings.append("dependency files changed: " + ", ".join(dependency_edits))

    migration_edits = [f for f in files if any(marker in f.lower() for marker in MIGRATION_MARKERS)]
    if migration_edits:
        warnings.append("migration/schema-related files changed: " + ", ".join(migration_edits))

    added_lines = "\n".join(
        line[1:] for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++")
    )
    for pattern in SECRET_PATTERNS:
        if pattern.search(added_lines):
            warnings.append("possible secret added in diff")
            break

    test_files = [f for f in files if any(m in f.lower() for m in TEST_PATH_MARKERS)]
    if test_files and any(
        p.search(line) for line in patch.splitlines() for p in TEST_WEAKENING_PATTERNS
    ):
        warnings.append(
            "possible test-weakening (added skip/xfail/.only) in test files: "
            + ", ".join(test_files)
        )

    result = {
        "base": base,
        "files_changed": files,
        "file_count": len(files),
        "lines_added": added,
        "lines_deleted": deleted,
        "binary_files_changed": binary,
        "warnings": warnings,
    }

    print(json.dumps(result, indent=2))
    return 1 if warnings else 0


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
    failed = [cmd for cmd in commands if cmd.get("result") == "fail"]
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
        if status in {"implement", "verify", "review", "package", "done", "iterating"}:
            repo_map = record.get("repo_map") or {}
            located = (repo_map.get("entry_points") or []) or (repo_map.get("likely_files") or [])
            corroborated = (repo_map.get("callers_checked") or []) or (repo_map.get("tests") or [])
            if not (located and corroborated):
                findings.append(
                    "non-trivial work requires a substantive context map (repo_map): "
                    "entry_points/likely_files plus callers_checked or tests"
                )
        if status in {"package", "done"}:
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

    if status in {"implement", "verify", "review", "package", "done", "iterating"} and not record.get("minimality_decision"):
        findings.append("minimality_decision is required before implementation can pass gates")

    if risk == "low":
        if not commands and not record.get("verification_plan"):
            findings.append("low risk still needs a targeted check or rationale")
    elif risk == "medium":
        if not ({"unit", "integration", "typecheck", "build", "lint"} & command_classes):
            findings.append("medium risk needs at least one relevant executable check")
        if status not in {"review", "package", "done"}:
            findings.append("medium risk must reach review/package/done status before review evidence is accepted")
        elif len(record.get("review_findings", [])) == 0:
            findings.append("medium risk should include fresh-context review result or rationale")
    elif risk == "high":
        if not ({"unit", "integration", "typecheck", "build", "lint"} & command_classes):
            findings.append("high risk needs relevant executable checks")
        if "security" not in command_classes:
            findings.append("high risk needs security review/check evidence or blocked rationale")
        if status not in {"review", "package", "done"}:
            findings.append("high risk must reach review/package/done status before review evidence is accepted")
        if not record.get("open_risks") and len(record.get("review_findings", [])) == 0:
            findings.append("high risk needs explicit risk/review documentation")
    else:
        findings.append("invalid risk tier")

    if blocked:
        findings.append(f"{len(blocked)} verification command(s) blocked; ensure rationale is recorded")

    for note in soft_warnings:
        print(f"note: {note}")

    if findings:
        for finding in findings:
            print(f"warning: {finding}")
        return 1

    print("verification gates look sufficient for recorded risk tier")
    return 0


REQUIRED_STEPS = [
    "INTAKE",
    "EXPLORE",
    "PLAN",
    "MINIMALITY_GATE",
    "IMPLEMENT_SLICE",
    "VERIFY",
    "REVIEW",
    "PACKAGE",
]

LOW_SIGNALS = {"docs", "copy", "comment", "formatting", "ui_copy"}
MEDIUM_SIGNALS = {
    "multi_file",
    "behavior_change",
    "api_contract",
    "shared_utility",
    "persistence_adjacent",
    "auth_adjacent",
}
HIGH_SIGNALS = {
    "authn",
    "authz",
    "payments",
    "billing",
    "data_migration",
    "destructive",
    "secrets",
    "production_infra",
    "external_side_effect",
    "concurrency",
}

# Signals that scope the task class (effort/blast-radius), orthogonal to risk tier.
TINY_SIGNALS = {
    "docs",
    "copy",
    "comment",
    "formatting",
    "ui_copy",
    "typo",
    "one_line_config",
    "obvious_test_update",
}
MISSION_SIGNALS = {"multi_day", "multi_module", "multi_repo", "uncertain_architecture"}

# Risk boundaries that require a dedicated security-reviewer pass and a hard gate.
SECURITY_BOUNDARY_SIGNALS = {
    "authn",
    "authz",
    "payments",
    "billing",
    "secrets",
    "data_migration",
    "pii",
    "upload_download",
    "network",
    "shell",
    "dependency_change",
}

GATES_LOW = ["self_review"]
GATES_MEDIUM = [
    "targeted_tests",
    "relevant_tests",
    "typecheck_or_build",
    "caller_review",
    "fresh_review",
]
GATES_HIGH = GATES_MEDIUM + ["security_review", "rollback_plan", "human_approval"]


def derive_risk_tier(signals: list[str]) -> str:
    signal_set = set(signals)
    if signal_set & HIGH_SIGNALS:
        return "high"
    if signal_set & MEDIUM_SIGNALS:
        return "medium"
    return "low"


def required_gates_for_tier(tier: str) -> list[str]:
    return {"low": GATES_LOW, "medium": GATES_MEDIUM, "high": GATES_HIGH}.get(tier, [])


def derive_task_class(signals: list[str]) -> str:
    signal_set = set(signals)
    if signal_set & MISSION_SIGNALS:
        return "mission"
    if signal_set & (MEDIUM_SIGNALS | HIGH_SIGNALS):
        return "medium"
    if signal_set and signal_set <= TINY_SIGNALS:
        return "tiny"
    return "small"


def requires_security_reviewer(signals: list[str]) -> bool:
    return bool(set(signals) & SECURITY_BOUNDARY_SIGNALS)


def minimality_flags(proposed: dict[str, Any]) -> list[str]:
    introduces = proposed.get("introduces", [])
    lower_rung_available = proposed.get("lower_rung_available", False)
    if introduces and lower_rung_available:
        return ["overengineering"]
    return []


def evaluate_input(case_input: dict[str, Any]) -> dict[str, Any]:
    signals = case_input.get("signals", [])
    tier = derive_risk_tier(signals)
    task_class = derive_task_class(signals)
    proposed = case_input.get("proposed_solution", {})
    security = requires_security_reviewer(signals)
    # The completion-record shipping gate fires for the same work the runtime
    # verify_gates treats as non-trivial: medium/mission class, medium/high risk,
    # or security-sensitive. A small low-risk task ships with handoff evidence
    # (contract + evidence + risks), not a formal completion record.
    requires_completion = (
        task_class in {"medium", "mission"} or tier in {"medium", "high"} or security
    )
    return {
        "risk_tier": tier,
        "task_class": task_class,
        "required_gates": required_gates_for_tier(tier),
        "minimality_flags": minimality_flags(proposed),
        "escalate": tier == "high",
        "requires_validation_contract": task_class in {"medium", "mission"},
        "requires_independent_review": task_class in {"medium", "mission"},
        "requires_completion_record": requires_completion,
        "requires_security_reviewer": security,
        "hard_gate": security or tier == "high",
        "harness_update": "repeated_mistake" in set(signals),
    }


def check_config(args: argparse.Namespace) -> int:
    config = load_json(Path(args.config))
    errors: list[str] = []

    for key in ("version", "profiles", "steps"):
        if key not in config:
            errors.append(f"missing required field: {key}")

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

    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print("config ok")
    return 0


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
        expected = case.get("expected", {})
        actual = evaluate_input(case.get("input", {}))
        mismatches: list[str] = []
        comparable_keys = (
            "risk_tier",
            "task_class",
            "required_gates",
            "minimality_flags",
            "escalate",
            "requires_validation_contract",
            "requires_independent_review",
            "requires_completion_record",
            "requires_security_reviewer",
            "hard_gate",
            "harness_update",
        )
        for key in comparable_keys:
            if key in expected and expected[key] != actual[key]:
                mismatches.append(f"{key}: expected {expected[key]!r}, got {actual[key]!r}")
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
    p_diff.add_argument("--max-files", type=int, default=12)
    p_diff.add_argument("--max-lines", type=int, default=600)
    p_diff.set_defaults(func=diff_audit)

    p_gates = sub.add_parser("verify-gates", help="Check verification evidence against risk tier")
    p_gates.add_argument("record")
    p_gates.set_defaults(func=verify_gates)

    p_config = sub.add_parser("check-config", help="Validate an orchestration config")
    p_config.add_argument("config")
    p_config.set_defaults(func=check_config)

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
    p_mcommit.add_argument("record")
    p_mcommit.add_argument("--lesson", help="Commit this exact lesson instead of distilling the record")
    p_mcommit.add_argument("--kind", choices=sorted(qlmem.LESSON_KINDS), default="gotcha", help="Kind for an explicit --lesson (distillation derives the kind otherwise)")
    p_mcommit.add_argument("--scope", help="Override scope glob, e.g. 'src/payments/**'")
    p_mcommit.add_argument("--location", choices=["checked_in", "local"], default="checked_in")
    p_mcommit.set_defaults(func=qlmem.cmd_commit)

    p_mprune = sub.add_parser("memory-prune", help="Dedup + cap the lessons ledger")
    p_mprune.add_argument("--max", type=int, default=200)
    p_mprune.add_argument("--max-age-days", type=int, default=365)
    p_mprune.add_argument("--location", choices=["checked_in", "local"], default="checked_in")
    p_mprune.set_defaults(func=qlmem.cmd_prune)

    p_mstatus = sub.add_parser("memory-status", help="Show memory store location and lesson counts")
    p_mstatus.add_argument("--location", choices=["checked_in", "local"], default="checked_in")
    p_mstatus.add_argument("--config", help="Read memory backend selection from this quality-loop config file")
    p_mstatus.set_defaults(func=qlmem.cmd_status)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
