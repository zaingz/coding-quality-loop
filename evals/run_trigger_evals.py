#!/usr/bin/env python3
"""Opt-in trigger evals for SKILL.md activation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def heuristic(description: str, prompt: str) -> bool:
    coding = {"implement", "refactor", "fix", "ship", "migrate", "add", "pr", "test"}
    quiet = {"what time", "summarize this article", "already merged", "nothing to do", "typo", "readme heading"}
    low = prompt.lower()
    return any(w in low for w in coding) and not any(q in low for q in quiet)


def judge(command: str, description: str, prompt: str) -> bool:
    proc = subprocess.run(
        command,
        input=json.dumps({"description": description, "prompt": prompt}),
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return proc.returncode == 0 and proc.stdout.strip().lower() in {"true", "trigger", "yes", "1"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run trigger evals")
    parser.add_argument("--cases", default="evals/triggers/cases.json")
    parser.add_argument("--judge-command", help="Optional command reading JSON stdin and printing true/false")
    args = parser.parse_args()

    data = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    desc = data["description_under_test"]
    failures = 0
    for label, expected in (("should_trigger", True), ("should_not_trigger", False)):
        for prompt in data[label]:
            actual = judge(args.judge_command, desc, prompt) if args.judge_command else heuristic(desc, prompt)
            ok = actual is expected
            failures += 0 if ok else 1
            print(f"[{'PASS' if ok else 'FAIL'}] {label}: {prompt} -> {actual}")
    total = len(data["should_trigger"]) + len(data["should_not_trigger"])
    print(f"\n{total - failures}/{total} trigger eval cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
