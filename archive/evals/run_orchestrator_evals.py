#!/usr/bin/env python3
"""Offline fake-host evals for driven mode."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import quality_loop_run as qlr  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"


def run_cli(*args: str, cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd),
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def make_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    repo.mkdir()
    shutil.copytree(ROOT / "scripts", repo / "scripts")
    shutil.copytree(ROOT / "assets", repo / "assets")
    (repo / "src").mkdir()
    (repo / "src" / "x.py").write_text("VALUE = 1\n")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_x.py").write_text("def test_x(): assert True\n")
    subprocess.run(["git", "-C", str(repo), "init"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "eval@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "eval"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "base"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return repo


def fixture(path: Path, verify_cmd: str) -> Path:
    data = {
        "record_updates": {
            "task_class": "medium",
            "risk_tier": "medium",
            "repo_map": {
                "entry_points": ["src/x.py"],
                "likely_files": ["src/x.py"],
                "callers_checked": ["src/x.py"],
                "tests": ["tests/test_x.py"],
                "patterns_to_follow": [],
            },
            "verification_plan": [verify_cmd],
            "validation_contract": {
                "goal": "verify driven mode",
                "acceptance_criteria": ["command passes"],
                "evidence": ["orchestrator-native VERIFY"],
            },
            "plan": ["run verifier without changing product code"],
            "files_changed": ["src/x.py", "tests/test_x.py"],
            "reviewer": "fake-reviewer",
            "verdict": "approve",
            "findings": [],
        }
    }
    path.write_text(json.dumps(data))
    return path


def case_step_order_blocks_out_of_order(tmp: Path) -> tuple[bool, str]:
    record = qlr.base_record("goal", "medium", "medium")
    ok = not qlr.validate_step_order(["INTAKE"], "REVIEW", record)
    return ok, f"review_after_intake_allowed={not ok}"


def case_review_prompt_excludes_implementer_transcript(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    record = qlr.base_record("goal", "medium", "medium")
    record["implementer_transcript"] = "IMPLEMENTER_TRANSCRIPT_SHOULD_NOT_APPEAR"
    record["commands_run"] = [{"cmd": "x", "result": "pass", "class": "unit", "evidence": {"output_tail": "verified output"}}]
    prompt = qlr.build_review_prompt(record, repo)
    ok = "IMPLEMENTER_TRANSCRIPT" not in prompt and "Evidence" in prompt
    return ok, f"contains_transcript={'IMPLEMENTER_TRANSCRIPT' in prompt}; prompt_len={len(prompt)}"


def case_failed_verify_blocks_review(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    fx = fixture(tmp / "fixture.json", f"{sys.executable} -c 'import sys; sys.exit(1)'")
    code, out, err = run_cli(str(ROOT / "scripts" / "quality_loop_run.py"), "--cwd", str(repo), "--record", "agent-record.json", "--host", "fake", "--fixture", str(fx), cwd=ROOT)
    journal = next((repo / ".quality-loop" / "runs").glob("*/journal.jsonl"))
    text = journal.read_text()
    review_marker = '"step": "REVIEW"'
    review_in_journal = review_marker in text
    ok = code == qlr.EXIT_GATES and not review_in_journal
    return ok, f"exit={code}; review_in_journal={review_in_journal}; err={err.strip()[:120]!r}"


def case_tiny_bypasses_review(tmp: Path) -> tuple[bool, str]:
    record = qlr.base_record("tiny docs", "low", "tiny")
    steps = [s.name for s in qlr.step_plan(record)]
    ok = "REVIEW" not in steps and steps == ["INTAKE", "IMPLEMENT_SLICE", "VERIFY", "PACKAGE"]
    return ok, f"steps={steps}"


def case_machine_record_passes_v1_gates(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    fx = fixture(tmp / "fixture.json", f"{sys.executable} -c 'print(1)'")
    code, out, err = run_cli(str(ROOT / "scripts" / "quality_loop_run.py"), "--cwd", str(repo), "--record", "agent-record.json", "--host", "fake", "--fixture", str(fx), cwd=ROOT)
    gate_code, gate_out, gate_err = run_cli(str(ROOT / "scripts" / "quality_loop.py"), "verify-gates", str(repo / "agent-record.json"), cwd=ROOT)
    ok = code == qlr.EXIT_SHIPPED and gate_code == 0
    return ok, f"run_exit={code}; gate_exit={gate_code}; gate={(gate_out + gate_err).strip()[:160]!r}; err={err.strip()[:120]!r}"


CASES = [
    ("step order blocks out-of-order REVIEW", case_step_order_blocks_out_of_order),
    ("review prompt excludes implementer transcript", case_review_prompt_excludes_implementer_transcript),
    ("failed VERIFY blocks REVIEW", case_failed_verify_blocks_review),
    ("tiny low-risk topology bypasses REVIEW", case_tiny_bypasses_review),
    ("machine-written record passes v1 gates", case_machine_record_passes_v1_gates),
]


def main() -> int:
    failures = 0
    for name, fn in CASES:
        with tempfile.TemporaryDirectory() as td:
            try:
                ok, detail = fn(Path(td))
            except Exception as exc:  # noqa: BLE001
                ok, detail = False, f"exception: {exc!r}"
        print(f"[{PASS if ok else FAIL}] {name}\n        {detail}")
        failures += 0 if ok else 1
    print(f"\n{len(CASES) - failures}/{len(CASES)} orchestrator eval cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
