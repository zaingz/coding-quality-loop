#!/usr/bin/env python3
"""Metrics for Coding Quality Loop benchmark result files."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_arm: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_arm.setdefault(str(row.get("arm")), []).append(row)
    out: dict[str, Any] = {}
    for arm, arm_rows in sorted(by_arm.items()):
        n = len(arm_rows)
        hidden = sum(1 for r in arm_rows if r.get("hidden_tests_passed"))
        regressions = sum(1 for r in arm_rows if r.get("regression_broken"))
        traps = sum(len(r.get("trap_flags_triggered", [])) for r in arm_rows)
        gates = sum(1 for r in arm_rows if r.get("gate_compliant"))
        diff = sum(int(r.get("diff_lines", 0)) for r in arm_rows)
        cost = sum(float(r.get("cost_usd", 0.0)) for r in arm_rows)
        tokens_in = sum(int(r.get("tokens_in", 0)) for r in arm_rows)
        tokens_out = sum(int(r.get("tokens_out", 0)) for r in arm_rows)
        duration = sum(float(r.get("duration_sec", 0.0)) for r in arm_rows)
        out[arm] = {
            "runs": n,
            "hidden_test_pass_rate": round(hidden / n, 3) if n else 0,
            "regression_breakage_rate": round(regressions / n, 3) if n else 0,
            "trap_flags_per_run": round(traps / n, 3) if n else 0,
            "gate_compliance_rate": round(gates / n, 3) if n else 0,
            "avg_diff_lines": round(diff / n, 1) if n else 0,
            "cost_usd": round(cost, 4),
            "avg_cost_usd": round(cost / n, 4) if n else 0,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "duration_sec": round(duration, 1),
            "avg_duration_sec": round(duration / n, 1) if n else 0,
        }
    return out


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: metrics.py RESULTS.json", file=sys.stderr)
        return 2
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    rows = data.get("runs", data)
    print(json.dumps(summarize(rows), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
