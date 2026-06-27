#!/usr/bin/env python3
"""Behavioral + function-level eval harness for the memory subsystem.

Mirrors evals/run_evals.py: drives the real CLI via subprocess in a tempdir
and asserts on stdlib module functions. Dependency-free; CI-friendly.

Run: python evals/run_memory_evals.py   (exits non-zero if any case fails)
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "quality_loop.py"

sys.path.insert(0, str(ROOT / "scripts"))
import quality_loop_memory as mem  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"


def run_cli(*args: str, cwd: str | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def case_slugify_and_resolve(tmp: Path) -> tuple[bool, str]:
    slug = mem.slugify("/Users/x/workspace/coding-quality-loop")
    checked = mem.resolve_memory_dir("checked_in", cwd=tmp, home=tmp / "home")
    local = mem.resolve_memory_dir("local", cwd=tmp, home=tmp / "home")
    ok = (
        slug == "Users-x-workspace-coding-quality-loop"
        and checked == tmp / ".quality-loop" / "memory"
        and local == (tmp / "home" / ".quality-loop" / mem.slugify(str(tmp.resolve())))
    )
    return ok, f"slug={slug!r}; checked={checked}; local={local}"


def case_lesson_io_roundtrip(tmp: Path) -> tuple[bool, str]:
    mem_dir = tmp / ".quality-loop" / "memory"
    raw = {"lesson": "Retry on 429 is idempotent here", "kind": "convention", "risk_tier": "medium"}
    row = mem.normalize_lesson(raw, "2026-06-27")
    mem.append_lesson(mem_dir, row)
    # a blank line and a malformed line must be skipped, not crash
    with (mem_dir / "lessons.jsonl").open("a", encoding="utf-8") as fh:
        fh.write("\n")
        fh.write("{not json}\n")
    loaded = mem.load_lessons(mem_dir)
    ok = (
        len(loaded) == 1
        and loaded[0]["lesson"] == raw["lesson"]
        and loaded[0]["id"] == mem.lesson_id(raw["lesson"])
        and loaded[0]["kind"] == "convention"
        and loaded[0]["hits"] == 0
    )
    return ok, f"loaded={loaded}"


def case_schema_and_seed_valid(tmp: Path) -> tuple[bool, str]:
    schema = json.loads((ROOT / "assets" / "lesson.schema.json").read_text())
    seed = mem.load_lessons(ROOT / ".quality-loop" / "memory")
    ok = schema.get("type") == "object" and "lesson" in schema.get("properties", {}) and seed == []
    return ok, f"schema_type={schema.get('type')}; seed_count={len(seed)}"


def _seed(mem_dir: Path) -> None:
    rows = [
        {"lesson": "Payment retries must be idempotent", "kind": "failure_mode",
         "risk_tier": "high", "scope_globs": ["src/payments/**"], "keywords": ["retry", "idempotent"]},
        {"lesson": "No new dependencies in this repo without justification", "kind": "convention",
         "risk_tier": "medium", "scope_globs": ["**"], "keywords": ["dependency"]},
        {"lesson": "The CSS build step is flaky on CI", "kind": "gotcha",
         "risk_tier": "low", "scope_globs": ["web/**"], "keywords": ["css", "build"]},
    ]
    for r in rows:
        mem.append_lesson(mem_dir, mem.normalize_lesson(r, "2026-06-01"))


def case_recall_ranks_and_is_deterministic(tmp: Path) -> tuple[bool, str]:
    mem_dir = tmp / ".quality-loop" / "memory"
    _seed(mem_dir)
    lessons = mem.load_lessons(mem_dir)
    out1 = mem.recall(lessons, "fix payment retry bug", ["src/payments/charge.py"], "high", 1500)
    out2 = mem.recall(lessons, "fix payment retry bug", ["src/payments/charge.py"], "high", 1500)
    top_is_payment = out1 and out1[0]["lesson"].startswith("Payment retries")
    deterministic = [l["id"] for l in out1] == [l["id"] for l in out2]
    # an unrelated query returns nothing (only positive scores survive)
    none_out = mem.recall(lessons, "translate the homepage to French", ["i18n/fr.po"], "low", 1500)
    ok = bool(top_is_payment) and deterministic and none_out == []
    return ok, f"top={out1[0]['lesson'] if out1 else None!r}; det={deterministic}; none={none_out}"


def case_recall_respects_budget(tmp: Path) -> tuple[bool, str]:
    mem_dir = tmp / ".quality-loop" / "memory"
    _seed(mem_dir)
    lessons = mem.load_lessons(mem_dir)
    # tiny budget: at most one line of digest, hard-capped
    selected = mem.recall(lessons, "dependency retry css", ["src/payments/x.py", "web/y.css"], "medium", 40)
    digest = mem.format_digest(selected, 40)
    ok = len(digest) <= 40 and len(selected) >= 1
    return ok, f"digest_len={len(digest)}; selected={len(selected)}; digest={digest!r}"


CASES = [
    ("slugify + resolve_memory_dir compute correct paths", case_slugify_and_resolve),
    ("lesson append/load round-trips and skips malformed lines", case_lesson_io_roundtrip),
    ("lesson.schema.json is valid and the seed store loads empty", case_schema_and_seed_valid),
    ("recall ranks by relevance, is deterministic, drops non-matches", case_recall_ranks_and_is_deterministic),
    ("recall + digest respect the hard char budget", case_recall_respects_budget),
]


def main() -> int:
    failures = 0
    for name, fn in CASES:
        with tempfile.TemporaryDirectory() as td:
            try:
                ok, detail = fn(Path(td))
            except Exception as exc:  # noqa: BLE001
                ok, detail = False, f"exception: {exc!r}"
        status = PASS if ok else FAIL
        if not ok:
            failures += 1
        print(f"[{status}] {name}\n        {detail}")
    total = len(CASES)
    print(f"\n{total - failures}/{total} memory eval cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
