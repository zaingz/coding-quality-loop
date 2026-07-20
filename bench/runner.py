#!/usr/bin/env python3
"""Benchmark runner for the pre-registered arms in bench/PROTOCOL.md.

Arms are version-neutral: baseline / full / no-review / light.

Default `fixture` mode is deterministic and dependency-free; it validates the
harness and metric plumbing without making live model claims. Fixture strengths
are hard-coded synthetic constants — never quote fixture numbers as results.
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
# The four version-neutral arms pre-registered in bench/PROTOCOL.md §1.
ARMS = ["baseline", "full", "no-review", "light"]

# Per-arm process-tax instrumentation the runner treats as first-class
# (bench/PROTOCOL.md §5). Live (non-fixture) runs must carry real values for
# the required trio; cost_usd is optional but type-checked when present.
REQUIRED_COST_FIELDS = ("tokens_in", "tokens_out", "duration_sec")
COST_FIELDS = ("cost_usd",) + REQUIRED_COST_FIELDS

# Provenance every live (non-fixture) run row must record so a committed
# results file is attributable to an exact cell (bench/PROTOCOL.md §5):
# which host CLI + version, which model, which skill version, which prompt.
REQUIRED_LIVE_PROVENANCE = ("host", "model", "skill_version", "prompt_file")


def load_tasks(path: Path) -> list[dict[str, Any]]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(path.glob("*.json"))]


def fixture_run(task: dict[str, Any], arm: str, seed: int) -> dict[str, Any]:
    rng = random.Random(f"{task['id']}:{arm}:{seed}")
    # Hard-coded SYNTHETIC strengths (plumbing validation only — see
    # bench/PROTOCOL.md header). `full` and `light` keep the deterministic
    # gates, so they are always gate-compliant in fixture mode; `no-review`
    # loses the review phase and is only probabilistically compliant.
    strength = {"baseline": 0.62, "full": 0.82, "no-review": 0.72, "light": 0.75}[arm]
    trap_resistance = {"baseline": 0.35, "full": 0.82, "no-review": 0.58, "light": 0.68}[arm]
    gate = arm in {"full", "light"} or (arm == "no-review" and rng.random() < 0.7)
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
        "diff_lines": int(rng.uniform(12, 180) * (0.8 if arm in ("full", "light") else 1.0)),
        "new_dependencies": int("dependency" in task.get("trap_flags", []) and bool(trap_flags)),
        # Fixture placeholders: zero, clearly exempt from live cost enforcement
        # because mode == "fixture". Live runs must overwrite these with real
        # values captured from the host CLI (see bench/PROTOCOL.md §5).
        "cost_usd": 0.0,
        "tokens_in": 0,
        "tokens_out": 0,
        "duration_sec": 0.0,
    }


def validate_cost_fields(runs: list[dict[str, Any]]) -> list[str]:
    """Return ``MISSING-COST`` problems for the process-tax schema.

    Every run must carry the ``REQUIRED_COST_FIELDS`` keys
    (tokens_in/tokens_out/duration_sec); ``cost_usd`` is optional but must be
    numeric and non-negative when present (bench/PROTOCOL.md §5). Fixture runs
    may leave zero placeholders. Live (non-fixture) runs must record real work:
    a run that consumed zero tokens or zero wall-time was not actually
    instrumented, so it fails loudly rather than passing silently.
    """
    problems: list[str] = []
    for run in runs:
        label = f"{run.get('task_id', '?')}:{run.get('arm', '?')}:seed{run.get('seed', '?')}"
        missing = [f for f in REQUIRED_COST_FIELDS if run.get(f) is None]
        if missing:
            problems.append(f"MISSING-COST {label}: absent fields {missing}")
            continue
        bad_type = [
            f for f in COST_FIELDS
            if f in run and (
                not isinstance(run.get(f), (int, float)) or isinstance(run.get(f), bool) or run.get(f) < 0
            )
        ]
        if bad_type:
            problems.append(f"MISSING-COST {label}: non-numeric or negative fields {bad_type}")
            continue
        if run.get("mode") == "fixture":
            continue  # zero placeholders are expected for fixtures
        unrecorded = [f for f in REQUIRED_COST_FIELDS if not run.get(f)]
        if unrecorded:
            problems.append(
                f"MISSING-COST {label}: live run reports zero {unrecorded} — cost/latency not recorded"
            )
    return problems


def validate_results_doc(data: Any) -> tuple[int, list[str]]:
    """Validate a whole results document, not just its cost fields.

    Contract (bench/PROTOCOL.md §5): the document is a JSON object with a
    top-level ``mode`` and a non-empty ``runs`` list; every run's ``mode``
    must be consistent with the document's — a live results file cannot dodge
    cost enforcement by self-labeling rows ``fixture`` (the fixture exemption
    belongs to documents declared ``mode: "fixture"``, like the committed
    smoke file, whose rows are synthetic by construction). Live runs must
    additionally carry the ``REQUIRED_LIVE_PROVENANCE`` fields. Returns
    ``(run_count, problems)``; never raises on malformed shapes.
    """
    if not isinstance(data, dict):
        return 0, ["MALFORMED: results file must be a JSON object with top-level 'mode' and 'runs'"]
    problems: list[str] = []
    mode = data.get("mode")
    if not isinstance(mode, str) or not mode:
        problems.append("MALFORMED: missing top-level 'mode' ('fixture' for synthetic smoke files; e.g. 'live' otherwise)")
        mode = ""
    runs = data.get("runs")
    if not isinstance(runs, list) or not runs:
        problems.append("MALFORMED: missing or empty 'runs' — zero runs is not an instrumented result")
        return 0, problems
    doc_is_fixture = mode == "fixture"
    rows: list[dict[str, Any]] = []
    for i, run in enumerate(runs):
        if not isinstance(run, dict):
            problems.append(f"MALFORMED runs[{i}]: not an object")
            continue
        rows.append(run)
        label = f"{run.get('task_id', '?')}:{run.get('arm', '?')}:seed{run.get('seed', '?')}"
        row_mode = run.get("mode")
        if doc_is_fixture and row_mode != "fixture":
            problems.append(f"MODE-MISMATCH {label}: run mode {row_mode!r} inside a mode='fixture' document")
        elif not doc_is_fixture and row_mode == "fixture":
            problems.append(
                f"MODE-MISMATCH {label}: run self-labels 'fixture' inside a mode={mode or '?'!r} "
                "document — the fixture cost exemption applies only to documents declared mode='fixture'"
            )
        if not doc_is_fixture:
            missing = [
                f for f in REQUIRED_LIVE_PROVENANCE
                if not (isinstance(run.get(f), str) and run.get(f).strip())
            ]
            if missing:
                problems.append(
                    f"MISSING-PROVENANCE {label}: live run must record non-empty {missing} (bench/PROTOCOL.md §5)"
                )
    problems.extend(validate_cost_fields(rows))
    return len(runs), problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Coding Quality Loop benchmark")
    parser.add_argument("--tasks", default=str(ROOT / "tasks"))
    parser.add_argument("--out", default=str(ROOT / "results" / "fixture-smoke-2026-07-20.json"))
    parser.add_argument("--mode", choices=["fixture"], default="fixture")
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--arms", nargs="*", default=ARMS)
    parser.add_argument(
        "--validate",
        metavar="RESULTS.json",
        help="Validate an existing results document: top-level mode + non-empty "
        "runs required; run modes must be consistent with the document mode "
        "(no self-labeled fixture rows inside a live file); live runs must "
        "carry provenance (host/model/skill_version/prompt_file) and the cost "
        "trio (tokens_in/tokens_out/duration_sec; cost_usd optional), with "
        "zero tokens/duration rejected. Only mode='fixture' documents are "
        "exempt from live cost/provenance; a run with no `mode` in a live "
        "document is treated as live (fail-closed).",
    )
    args = parser.parse_args()

    if args.validate:
        path = Path(args.validate)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"FAIL: cannot read results file {path}: {exc}")
            return 1
        count, problems = validate_results_doc(data)
        if problems:
            print(f"FAIL: {len(problems)} problem(s) in {path}:")
            for problem in problems:
                print(f"  {problem}")
            return 1
        doc_is_fixture = data.get("mode") == "fixture"
        print(
            f"OK: {count} run(s), document mode {data.get('mode')!r}, run modes consistent, "
            f"cost fields {list(REQUIRED_COST_FIELDS)} present"
            + ("" if doc_is_fixture else f", live provenance {list(REQUIRED_LIVE_PROVENANCE)} present")
            + "."
        )
        return 0

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
        "note": "SYNTHETIC fixture data: generated from hard-coded per-arm strength constants to validate harness plumbing only (bench/PROTOCOL.md header); not a live agent benchmark and never quotable as evidence. Per-arm cost_usd/tokens_in/tokens_out/duration_sec are zero placeholders (fixture mode is exempt from live cost enforcement).",
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
