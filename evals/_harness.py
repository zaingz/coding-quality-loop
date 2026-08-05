#!/usr/bin/env python3
"""Shared skeleton for the suite runners in this directory.

The six runners (`run_evals`, `run_memory_evals`, `run_reality_evals`,
`run_routing_evals`, `run_hook_evals`, `run_control_evals`) copy-pasted the same
PASS/FAIL constants, the same `subprocess` CLI wrapper, and the same
case-loop/summary printer. They now import them from here, so a harness change
(failure output, env hermeticity, filtering) lands in one place instead of
drifting across six copies — it already had drifted: five `run_cli` signatures
and two spellings of the same tally loop.

Suite-specific fixtures and each suite's `CASES` list stay in its own runner.
Stdlib only; no behavior change versus the copies this replaces.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "quality_loop.py"

PASS = "PASS"
FAIL = "FAIL"

Case = tuple[str, Callable[[Path], tuple[bool, str]]]


def run_cli(
    *args: str,
    cwd: str | Path | None = None,
    stdin: str | None = None,
    env: Mapping[str, str] | None = None,
    scrub_env: Sequence[str] = (),
) -> tuple[int, str, str]:
    """Run `scripts/quality_loop.py` via subprocess. Never raises.

    Superset of the per-runner copies: `stdin` (reality suite) and `env` /
    `scrub_env` (reality's `QUALITY_LOOP_BASE` scrub, so a developer's ambient
    env cannot change what a case pins) default to no-ops, which is exactly the
    behavior the other suites had.
    """
    run_env: dict[str, str] | None = None
    if env or scrub_env:
        drop = set(scrub_env)
        run_env = {k: v for k, v in os.environ.items() if k not in drop}
        if env:
            run_env.update(env)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd) if cwd is not None else None,
        input=stdin,
        env=run_env,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def main_loop(
    cases: Sequence[Case],
    label: str,
    *,
    preserve_env: Sequence[str] = (),
    env_for_case: Callable[[Path], Mapping[str, str]] | None = None,
) -> int:
    """Run each case in a fresh tempdir, print `[PASS]`/`[FAIL]`, tally, exit code.

    `label` is the trailing text of the summary line ("eval cases passed",
    "hook eval cases passed", ...). `preserve_env` names environment variables
    saved before each case and restored after it; `env_for_case` returns
    per-case environment overrides derived from the tempdir (the control-plane
    suite points every host-side source inside the tempdir so the suite never
    reads a developer's real ~/.claude, ~/.codex or ~/.factory data). Both
    default to no-ops.
    """
    failures = 0
    for name, fn in cases:
        with tempfile.TemporaryDirectory() as td:
            saved = {key: os.environ.get(key) for key in preserve_env}
            if env_for_case is not None:
                os.environ.update(env_for_case(Path(td)))
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
