#!/usr/bin/env python3
"""Benchmark runner for baseline / skill / hooks / driven arms.

Default `fixture` mode is deterministic and dependency-free; it validates the
harness and metric plumbing without making live model claims.
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any

from metrics import summarize

ROOT = Path(__file__).resolve().parent
ARMS = ["baseline", "skill", "skill_hooks", "driven"]


def load_tasks(path: Path) -> list[dict[str, Any]]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(path.glob("*.json"))]


def fixture_run(task: dict[str, Any], arm: str, seed: int) -> dict[str, Any]:
    rng = random.Random(f"{task['id']}:{arm}:{seed}")
    strength = {"baseline": 0.62, "skill": 0.72, "skill_hooks": 0.82, "driven": 0.9}[arm]
    trap_resistance = {"baseline": 0.35, "skill": 0.58, "skill_hooks": 0.78, "driven": 0.86}[arm]
    trap_flags = [
        flag for flag in task.get("trap_flags", [])
        if rng.random() > trap_resistance
    ]
    hidden_passed = rng.random() < strength and not trap_flags
    return {
        "task_id": task["id"],
        "arm": arm,
        "seed": seed,
        "mode": "fixture",
        "hidden_tests_passed": hidden_passed,
        "regression_broken": rng.random() > strength,
        "trap_flags_triggered": trap_flags,
        "gate_compliant": arm in {"skill_hooks", "driven"} or (arm == "skill" and rng.random() < 0.7),
        "diff_lines": int(rng.uniform(12, 180) * (0.8 if arm == "driven" else 1.0)),
        "new_dependencies": int("dependency" in task.get("trap_flags", []) and bool(trap_flags)),
        "cost_usd": 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Coding Quality Loop benchmark")
    parser.add_argument("--tasks", default=str(ROOT / "tasks"))
    parser.add_argument("--out", default=str(ROOT / "results" / "fixture-smoke-2026-07-01.json"))
    parser.add_argument("--mode", choices=["fixture"], default="fixture")
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--arms", nargs="*", default=ARMS)
    args = parser.parse_args()

    tasks = load_tasks(Path(args.tasks))
    runs = [
        fixture_run(task, arm, seed)
        for task in tasks
        for arm in args.arms
        for seed in range(args.seeds)
    ]
    result = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": args.mode,
        "note": "Fixture smoke result validates harness plumbing only; not a live agent benchmark.",
        "task_count": len(tasks),
        "arms": args.arms,
        "seeds": args.seeds,
        "summary": summarize(runs),
        "runs": runs,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
