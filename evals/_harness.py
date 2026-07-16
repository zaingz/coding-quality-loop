#!/usr/bin/env python3
"""Shared skeleton for the suite runners in this directory.

Six runners (run_evals, run_control_evals, run_routing_evals, run_reality_evals,
run_memory_evals, run_hook_evals) previously copy-pasted the same PASS/FAIL
constants, subprocess CLI wrapper, and case-loop/summary printer. They now import
them from here so a harness change (failure output, timing, filtering) lands in
one place instead of drifting across six copies. Suite-specific fixtures and the
CASES list stay in each runner. Stdlib-only; no behavior change vs. the copies.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "quality_loop.py"

PASS = "PASS"
FAIL = "FAIL"

Case = tuple[str, Callable[[Path], tuple[bool, str]]]


def run_cli(*args: str, cwd: str | None = None, stdin: str | None = None) -> tuple[int, str, str]:
    """Run the quality_loop.py CLI via subprocess. Non-raising.

    Superset of the per-runner copies: the optional ``stdin`` (used only by the
    reality suite) defaults to None, which is the same as passing no input.
    """
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        input=stdin,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def main_loop(cases: Sequence[Case], label: str, *, preserve_env: Sequence[str] = ()) -> int:
    """Run each case in a fresh tempdir, print [PASS]/[FAIL], and tally.

    ``label`` is the trailing text of the summary line ("eval cases passed",
    "hook eval cases passed", ...). ``preserve_env`` names environment variables
    saved before each case and restored after (the control suite mutates
    CLAUDE_CONFIG_DIR); empty by default, a no-op for the other suites.
    """
    failures = 0
    for name, fn in cases:
        with tempfile.TemporaryDirectory() as td:
            saved = {key: os.environ.get(key) for key in preserve_env}
            try:
                ok, detail = fn(Path(td))
            except Exception as exc:  # noqa: BLE001 - eval harness surfaces any error
                ok, detail = False, f"exception: {exc!r}"
            finally:
                for key, value in saved.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
        print(f"[{PASS if ok else FAIL}] {name}\n        {detail}")
        failures += 0 if ok else 1
    total = len(cases)
    print(f"\n{total - failures}/{total} {label}")
    return 1 if failures else 0
