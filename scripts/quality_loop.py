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
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[A-Z0-9]{16}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
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
        "verification_plan": [],
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

    warnings: list[str] = []
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
    record = load_json(Path(args.record))
    risk = record.get("risk_tier")
    status = record.get("status")
    commands = record.get("commands_run", [])
    command_classes = {cmd.get("class") for cmd in commands if cmd.get("result") == "pass"}
    blocked = [cmd for cmd in commands if cmd.get("result") == "blocked"]
    failed = [cmd for cmd in commands if cmd.get("result") == "fail"]
    missing_class = [cmd for cmd in commands if not cmd.get("class")]
    findings: list[str] = []

    if failed:
        findings.append(f"{len(failed)} verification command(s) failed")
    if missing_class:
        findings.append(f"{len(missing_class)} command(s) missing class field")

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

    if findings:
        for finding in findings:
            print(f"warning: {finding}")
        return 1

    print("verification gates look sufficient for recorded risk tier")
    return 0


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

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
