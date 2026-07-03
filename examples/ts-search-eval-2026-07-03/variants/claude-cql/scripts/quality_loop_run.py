#!/usr/bin/env python3
"""Driven-mode orchestrator for Coding Quality Loop v2.0."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import quality_loop as ql
import quality_loop_hosts as hosts

ROOT = Path(__file__).resolve().parent.parent
EXIT_SHIPPED = 0
EXIT_GATES = 1
EXIT_USAGE = 2
EXIT_ESCALATED = 3


@dataclass(frozen=True)
class Step:
    name: str
    role: str
    tool_policy: str


FULL_STEPS = [
    Step("INTAKE", "planner", "read"),
    Step("EXPLORE", "planner", "read"),
    Step("MINIMALITY_GATE", "minimality", "read"),
    Step("PLAN", "planner", "read"),
    Step("IMPLEMENT_SLICE", "implementer", "write"),
    Step("VERIFY", "orchestrator", "local"),
    Step("REVIEW", "reviewer", "read"),
    Step("PACKAGE", "orchestrator", "local"),
]
TINY_STEPS = [
    Step("INTAKE", "planner", "read"),
    Step("IMPLEMENT_SLICE", "implementer", "write"),
    Step("VERIFY", "orchestrator", "local"),
    Step("PACKAGE", "orchestrator", "local"),
]


def step_plan(record: dict[str, Any]) -> list[Step]:
    if record.get("task_class") == "tiny" and record.get("risk_tier") == "low":
        return TINY_STEPS
    steps = list(FULL_STEPS)
    if record.get("risk_tier") == "high" or record.get("security_sensitive"):
        steps.insert(-1, Step("SECURITY_REVIEW", "security_reviewer", "read"))
    return steps


def validate_step_order(completed: list[str], next_step: str, record: dict[str, Any]) -> bool:
    names = [s.name for s in step_plan(record)]
    if next_step not in names:
        return False
    return names.index(next_step) == len(completed)


def load_template(name: str) -> str:
    return (ROOT / "assets" / "prompts" / name).read_text(encoding="utf-8")


def redact_text(text: str) -> str:
    return ql.redact(text)[:120_000]


def journal(run_dir: Path, event: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    clean = json.loads(json.dumps(event, default=str))
    if "prompt" in clean:
        clean["prompt"] = redact_text(str(clean["prompt"]))
    with (run_dir / "journal.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(clean, sort_keys=True) + "\n")


def base_record(goal: str, risk: str, task_class: str) -> dict[str, Any]:
    return {
        "task_id": str(uuid.uuid4()),
        "goal": goal,
        "task_class": task_class,
        "risk_tier": risk,
        "acceptance_criteria": ["complete the stated goal"],
        "constraints": [],
        "non_goals": [],
        "assumptions": [],
        "verification_plan": [],
        "minimality_decision": {"rung": "minimal_new_code", "reason": "driven mode default until planner narrows it"},
        "plan": [],
        "commands_run": [],
        "open_risks": [],
        "review_findings": [],
        "repo_map": {"entry_points": [], "likely_files": [], "callers_checked": [], "tests": [], "patterns_to_follow": []},
        "implementer": "quality-loop-run",
        "validation_contract": {"goal": goal, "acceptance_criteria": ["complete the stated goal"], "evidence": ["orchestrator verification"]},
        "independent_review": None,
        "security_review": None,
        "completion_record": None,
        "security_sensitive": risk == "high",
        "repair_attempts": 0,
        "repeated_failure": False,
        "harness_update": None,
        "status": "intake",
    }


def recall_memory(goal: str, files: list[str], risk: str, cwd: Path) -> str:
    proc = subprocess.run(
        ["python3", str(ROOT / "scripts" / "quality_loop.py"), "memory-recall", "--goal", goal, "--files", ",".join(files), "--risk", risk, "--no-bump"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd),
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else "No prior lessons matched."


def git_diff(cwd: Path) -> str:
    proc = subprocess.run(["git", "diff", "HEAD"], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=str(cwd), check=False)
    return proc.stdout if proc.returncode == 0 else ""


def command_evidence(cmd: str, cwd: Path, timeout: int) -> dict[str, Any]:
    started = time.time()
    proc = subprocess.run(cmd, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(cwd), timeout=timeout, check=False)
    combined = (proc.stdout + proc.stderr)[-4000:]
    return {
        "cmd": cmd,
        "exit_code": proc.returncode,
        "duration_ms": int((time.time() - started) * 1000),
        "output_sha256": hashlib.sha256(combined.encode("utf-8")).hexdigest(),
        "output_tail": ql.redact(combined),
    }


def run_verify(record: dict[str, Any], cwd: Path, timeout: int) -> bool:
    commands = [str(c).strip() for c in record.get("verification_plan", []) if str(c).strip()]
    if not commands:
        commands = ["python3 -m py_compile scripts/*.py"]
    all_passed = True
    for cmd in commands:
        evidence = command_evidence(cmd, cwd, timeout)
        all_passed = all_passed and evidence["exit_code"] == 0
        record.setdefault("commands_run", []).append({
            "cmd": cmd,
            "class": "unit",
            "result": "pass" if evidence["exit_code"] == 0 else "fail",
            "evidence": evidence,
        })
    if not all_passed:
        record["repair_attempts"] = int(record.get("repair_attempts") or 0) + 1
        if record["repair_attempts"] >= 2:
            record["repeated_failure"] = True
    return all_passed


def build_review_prompt(record: dict[str, Any], cwd: Path) -> str:
    evidence = json.dumps(record.get("commands_run", []), indent=2)
    return load_template("reviewer.md").format(
        contract=json.dumps(record.get("validation_contract"), indent=2),
        diff=git_diff(cwd),
        evidence=evidence,
    )


def apply_review(record: dict[str, Any], result: hosts.HostResult) -> None:
    review = {
        "reviewer": result.data.get("reviewer", "quality-loop-reviewer"),
        "verdict": result.data.get("verdict", "approve"),
        "fresh_context": True,
        "patched": False,
        "findings": result.data.get("findings", []),
    }
    record["independent_review"] = review
    record["review_findings"] = review["findings"] or ["fresh-context review: approved"]


def package_record(record: dict[str, Any]) -> None:
    record["completion_record"] = {
        "goal": record.get("goal"),
        "acceptance_criteria": record.get("acceptance_criteria", []),
        "evidence": record.get("commands_run", []),
        "files_changed": record.get("files_changed", []),
    }
    record["status"] = "done"


def verify_final(record_path: Path, cwd: Path) -> int:
    proc = subprocess.run(
        ["python3", str(ROOT / "scripts" / "quality_loop.py"), "verify-gates", str(record_path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd),
        check=False,
    )
    return proc.returncode


def run(args: argparse.Namespace) -> int:
    cwd = Path(args.cwd).resolve()
    fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8")) if args.fixture else {}
    adapter = hosts.load_adapter(args.host, fixture)
    review_adapter = hosts.load_adapter(args.review_host or args.host, fixture)
    if not adapter.available():
        print(f"host unavailable: {args.host}", file=sys.stderr)
        return EXIT_USAGE

    record_path = Path(args.record)
    if not record_path.is_absolute():
        record_path = cwd / record_path
    record = ql.load_json(record_path) if record_path.is_file() else base_record(args.goal, args.risk, args.task_class)
    run_dir = cwd / ".quality-loop" / "runs" / str(record["task_id"])
    memory = recall_memory(record["goal"], record.get("repo_map", {}).get("likely_files", []), record["risk_tier"], cwd)
    planner_prompt = load_template("planner.md").format(goal=record["goal"], risk_tier=record["risk_tier"], memory=memory)
    steps = step_plan(record)
    if args.dry_run:
        print(json.dumps({"steps": [s.name for s in steps], "planner_prompt": planner_prompt}, indent=2))
        return EXIT_SHIPPED
    if record.get("risk_tier") == "high":
        record["status"] = "escalated"
        ql.write_json(record_path, record)
        journal(run_dir, {"step": "ESCALATE", "reason": "high tier stops for human before PACKAGE"})
        return EXIT_ESCALATED

    completed: list[str] = []
    for step in steps:
        if not validate_step_order(completed, step.name, record):
            journal(run_dir, {"step": step.name, "blocked": "out_of_order"})
            return EXIT_GATES
        if step.name == "VERIFY":
            record["status"] = "verify"
            if not run_verify(record, cwd, args.timeout):
                ql.write_json(record_path, record)
                journal(run_dir, {"step": "VERIFY", "passed": False})
                return EXIT_GATES
        elif step.name == "REVIEW":
            record["status"] = "review"
            prompt = build_review_prompt(record, cwd)
            result = review_adapter.spawn(prompt, "read", cwd)
            apply_review(record, result)
            journal(run_dir, {"step": "REVIEW", "prompt": prompt, "result": result.data})
        elif step.name == "PACKAGE":
            package_record(record)
            ql.write_json(record_path, record)
            code = verify_final(record_path, cwd)
            journal(run_dir, {"step": "PACKAGE", "verify_gates_exit": code})
            if code != 0:
                return EXIT_GATES
            subprocess.run(["python3", str(ROOT / "scripts" / "quality_loop.py"), "memory-commit", str(record_path), "--location", "local"], cwd=str(cwd), check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            result = adapter.spawn(planner_prompt, step.tool_policy, cwd)
            if isinstance(result.data, dict):
                record.update(result.data)
            journal(run_dir, {"step": step.name, "result": result.data})
        completed.append(step.name)
    ql.write_json(record_path, record)
    return EXIT_SHIPPED


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Coding Quality Loop driven mode")
    parser.add_argument("--goal", default="Run Quality Loop driven mode")
    parser.add_argument("--record", default="agent-record.json")
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--host", choices=["fake", "manual", "claude", "codex"], default="fake")
    parser.add_argument("--review-host", choices=["fake", "manual", "claude", "codex"])
    parser.add_argument("--fixture")
    parser.add_argument("--risk", choices=sorted(ql.RISK_TIERS), default="medium")
    parser.add_argument("--task-class", choices=["tiny", "small", "medium", "mission"], default="medium")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true")
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
