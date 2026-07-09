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
ARMS = ["baseline", "skill", "skill_hooks"]
ABLATION_ARMS = ["baseline", "v3-full", "v3-no-review", "v3-no-contract"]

# Per-arm process-tax instrumentation the runner treats as first-class.
# R3 (docs/critical-review-2026-07-09.md): the repo mandates recording cost per
# live sweep (README) but no results.json ever carried a cost/token field. Every
# run must carry these keys; live (non-fixture) runs must carry real values.
COST_FIELDS = ("cost_usd", "tokens_in", "tokens_out", "duration_sec")


def load_tasks(path: Path) -> list[dict[str, Any]]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(path.glob("*.json"))]


def fixture_run(task: dict[str, Any], arm: str, seed: int) -> dict[str, Any]:
    rng = random.Random(f"{task['id']}:{arm}:{seed}")
    if arm in ABLATION_ARMS:
        strength = {"baseline": 0.62, "v3-full": 0.82, "v3-no-review": 0.72, "v3-no-contract": 0.68}[arm]
        trap_resistance = {"baseline": 0.35, "v3-full": 0.82, "v3-no-review": 0.58, "v3-no-contract": 0.68}[arm]
        gate = arm in {"v3-full", "v3-no-contract"} or (arm == "v3-no-review" and rng.random() < 0.7)
    else:
        strength = {"baseline": 0.62, "skill": 0.72, "skill_hooks": 0.82}[arm]
        trap_resistance = {"baseline": 0.35, "skill": 0.58, "skill_hooks": 0.78}[arm]
        gate = arm == "skill_hooks" or (arm == "skill" and rng.random() < 0.7)
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
        "gate_compliant": gate,
        "diff_lines": int(rng.uniform(12, 180) * (0.8 if arm in ("v3-full", "skill_hooks") else 1.0)),
        "new_dependencies": int("dependency" in task.get("trap_flags", []) and bool(trap_flags)),
        # Fixture placeholders: zero, clearly exempt from live cost enforcement
        # because mode == "fixture". Live runs must overwrite these with real
        # values captured from the host CLI (see live-run-recipe.md).
        "cost_usd": 0.0,
        "tokens_in": 0,
        "tokens_out": 0,
        "duration_sec": 0.0,
    }


def validate_cost_fields(runs: list[dict[str, Any]]) -> list[str]:
    """Return ``MISSING-COST`` problems for the process-tax schema.

    Every run must carry all ``COST_FIELDS`` keys. Fixture runs may leave them at
    their zero placeholders. Live (non-fixture) runs must record real work: a run
    that consumed zero tokens or zero wall-time was not actually instrumented, so
    it fails loudly rather than passing silently.
    """
    problems: list[str] = []
    for run in runs:
        label = f"{run.get('task_id', '?')}:{run.get('arm', '?')}:seed{run.get('seed', '?')}"
        missing = [f for f in COST_FIELDS if run.get(f) is None]
        if missing:
            problems.append(f"MISSING-COST {label}: absent fields {missing}")
            continue
        bad_type = [
            f for f in COST_FIELDS
            if not isinstance(run.get(f), (int, float)) or isinstance(run.get(f), bool) or run.get(f) < 0
        ]
        if bad_type:
            problems.append(f"MISSING-COST {label}: non-numeric or negative fields {bad_type}")
            continue
        if run.get("mode") == "fixture":
            continue  # zero placeholders are expected for fixtures
        unrecorded = [f for f in ("tokens_in", "tokens_out", "duration_sec") if not run.get(f)]
        if unrecorded:
            problems.append(
                f"MISSING-COST {label}: live run reports zero {unrecorded} — cost/latency not recorded"
            )
    return problems


def load_runs(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data.get("runs", [])
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Coding Quality Loop benchmark")
    parser.add_argument("--tasks", default=str(ROOT / "tasks"))
    parser.add_argument("--out", default=str(ROOT / "results" / "fixture-smoke-2026-07-01.json"))
    parser.add_argument("--mode", choices=["fixture"], default="fixture")
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--arms", nargs="*", default=ARMS)
    parser.add_argument("--ablation", action="store_true", help="Use ablation arms (baseline, v3-full, v3-no-review, v3-no-contract)")
    parser.add_argument(
        "--validate",
        metavar="RESULTS.json",
        help="Validate an existing results file for per-arm cost fields "
        "(cost_usd/tokens_in/tokens_out/duration_sec) and exit non-zero on any "
        "live run that omits them or reports zero tokens/duration. Fixture runs "
        "are exempt; a run with no `mode` is treated as live (fail-closed).",
    )
    args = parser.parse_args()

    if args.validate:
        runs = load_runs(Path(args.validate))
        if not runs:
            # A results file with no runs key (or an empty list) must not read
            # as instrumented: "OK: 0 run(s)" would be a silent pass.
            print(f"FAIL: no runs found in {args.validate} (missing or empty 'runs').")
            return 1
        problems = validate_cost_fields(runs)
        if problems:
            print(f"FAIL: {len(problems)} run(s) missing required cost instrumentation:")
            for problem in problems:
                print(f"  {problem}")
            return 1
        print(
            f"OK: {len(runs)} run(s) carry required cost fields "
            f"{list(COST_FIELDS)} (fixture runs exempt)."
        )
        return 0

    if args.ablation:
        args.arms = ABLATION_ARMS

    tasks = load_tasks(Path(args.tasks))
    runs = [
        fixture_run(task, arm, seed)
        for task in tasks
        for arm in args.arms
        for seed in range(args.seeds)
    ]
    # The runner validates what it produces: fixtures must carry the placeholder
    # keys, and this guards against a future live mode emitting uninstrumented runs.
    problems = validate_cost_fields(runs)
    if problems:
        print("FAIL: generated runs missing required cost instrumentation:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    result = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": args.mode,
        "note": "Fixture smoke result validates harness plumbing only; not a live agent benchmark. Per-arm cost_usd/tokens_in/tokens_out/duration_sec are zero placeholders (fixture mode is exempt from live cost enforcement).",
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
