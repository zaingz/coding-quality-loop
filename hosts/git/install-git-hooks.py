#!/usr/bin/env python3
"""Install the dependency-free Quality Loop pre-commit hook."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HOOK = """#!/bin/sh
set -eu
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
python3 scripts/quality_loop.py diff-audit --staged
"""


def repo_root() -> Path:
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        print(proc.stderr.strip(), file=sys.stderr)
        raise SystemExit(proc.returncode)
    return Path(proc.stdout.strip())


def main() -> int:
    root = repo_root()
    path = root / ".git" / "hooks" / "pre-commit"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if existing == HOOK:
        print(f"pre-commit hook already installed: {path}")
        return 0
    if existing and "quality_loop.py diff-audit --staged" not in existing:
        backup = path.with_suffix(".pre-quality-loop-backup")
        backup.write_text(existing, encoding="utf-8")
        print(f"backed up existing pre-commit hook to {backup}")
    path.write_text(HOOK, encoding="utf-8")
    os.chmod(path, 0o755)
    print(f"installed Quality Loop pre-commit hook: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
