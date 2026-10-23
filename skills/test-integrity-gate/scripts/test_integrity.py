#!/usr/bin/env python3
"""Check a focused test's selected base failure and current pass."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

def is_test_path(path: str) -> bool:
    parts = path.replace("\\", "/").lower().split("/")
    return any(
        {token for token in re.split(r"[._-]+", part) if token}
        .intersection({"test", "tests", "spec", "specs", "testdata"})
        for part in parts
    )


def git(repo: Path, *args: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def changed_tests(repo: Path, base: str) -> list[str]:
    code, tracked, error = git(repo, "diff", "--name-only", base)
    if code != 0:
        raise RuntimeError(error.strip() or f"could not diff {base}")
    _, untracked, _ = git(repo, "ls-files", "--others", "--exclude-standard")
    paths: list[str] = []
    for path in [*tracked.splitlines(), *untracked.splitlines()]:
        path = path.strip().replace("\\", "/")
        if (
            path
            and not path.startswith(".quality-loop/")
            and path not in paths
            and is_test_path(path)
        ):
            paths.append(path)
    return paths


def overlay_tests(repo: Path, worktree: Path, paths: list[str]) -> None:
    for rel in paths:
        source = repo / rel
        destination = worktree / rel
        cursor = repo
        for part in Path(rel).parts:
            cursor /= part
            if cursor.is_symlink():
                raise RuntimeError(
                    f"refusing to follow test path through a symlink: {rel!r}"
                )
        if source.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        elif source.exists():
            raise RuntimeError(f"test path {rel!r} is not a regular file")
        else:
            destination.unlink(missing_ok=True)


def run(command: str, cwd: Path, timeout: int) -> dict[str, object]:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            text=True,
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return {
            "state": "pass" if proc.returncode == 0 else "fail",
            "exit_code": proc.returncode,
            "stdout_tail": proc.stdout[-2000:],
            "stderr_tail": proc.stderr[-2000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "state": "timeout",
            "exit_code": None,
            "stdout_tail": (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else "",
        }


def report(
    status: str,
    *,
    reason: str = "",
    old: dict[str, object] | None = None,
    current: dict[str, object] | None = None,
    test_paths: list[str] | None = None,
) -> int:
    print(json.dumps({
        "status": status,
        "reason": reason,
        "old_code_with_proposed_tests": old,
        "current_code": current,
        "test_files_overlaid": test_paths or [],
    }, indent=2))
    return 0 if status == "pass" else 1


def known_runner_failure(old: dict[str, object]) -> bool:
    """Exclude recognizable infrastructure failures from a claimed RED.

    This small guard cannot establish that a different failure is relevant;
    inspect the captured old output even when the selected marker matches.
    """
    if old.get("exit_code") in (126, 127):
        return True
    output = str(old.get("stdout_tail", "")) + "\n" + str(old.get("stderr_tail", ""))
    patterns = (
        r"\b(?:ModuleNotFoundError|ImportError):",
        r"\b(?:Cannot find module|ERR_MODULE_NOT_FOUND)\b",
        r"(?im)^(?:[^\n]*?:\s*)?can't open file\b",
        r"(?im)^ERROR: file or directory not found:",
        r"(?im)^\s*(?:no tests ran|Ran 0 tests)\b",
        r"(?im)^(?:/[^:\n]+/)?(?:sh|bash|dash|zsh):[^\n]*(?:command not found|:\s*not found)(?::[^\n]*)?$",
    )
    return any(re.search(pattern, output) for pattern in patterns)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a focused test against base source plus proposed tests, then current source."
    )
    parser.add_argument("--base", required=True, help="Task-start commit or merge-base")
    parser.add_argument("--command", required=True, help="Focused test command")
    parser.add_argument(
        "--expected-red",
        help="Literal output substring selected before replay that identifies the intended base failure",
    )
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    repo = Path.cwd().resolve()
    code, top, error = git(repo, "rev-parse", "--show-toplevel")
    if code != 0:
        return report("not_proven", reason=error.strip())
    repo = Path(top.strip()).resolve()

    try:
        test_paths = changed_tests(repo, args.base)
    except RuntimeError as exc:
        return report("not_proven", reason=str(exc))
    if not test_paths:
        return report(
            "not_proven",
            reason="no changed test files found relative to the base",
        )

    worktree_dir = Path(tempfile.mkdtemp(prefix="test-integrity-"))
    code, _, error = git(repo, "worktree", "add", "--detach", str(worktree_dir), args.base)
    if code != 0:
        try:
            os.rmdir(worktree_dir)
        except OSError:
            pass
        return report(
            "not_proven",
            reason=error.strip(),
            test_paths=test_paths,
        )

    try:
        overlay_tests(repo, worktree_dir, test_paths)
        old = run(args.command, worktree_dir, args.timeout)
        current = run(args.command, repo, args.timeout)
    except (OSError, RuntimeError) as exc:
        return report(
            "not_proven",
            reason=str(exc),
            test_paths=test_paths,
        )
    finally:
        git(repo, "worktree", "remove", "--force", str(worktree_dir))

    expected_red = args.expected_red or ""
    if old["state"] == "timeout":
        status, reason = "not_proven", "command timed out against old source"
    elif old["state"] != "fail":
        status, reason = "fail", "command did not fail against old source with proposed tests"
    elif known_runner_failure(old):
        status, reason = "not_proven", "base output indicates a runner, import, or test-discovery failure"
    elif not expected_red.strip():
        status, reason = "not_proven", "expected-red output substring was not supplied before replay"
    elif expected_red not in old["stdout_tail"] and expected_red not in old["stderr_tail"]:
        status, reason = "not_proven", "expected-red output substring was not found in captured base output"
    elif current["state"] != "pass":
        status, reason = "fail", "command did not pass against current source"
    else:
        status, reason = "pass", ""
    return report(
        status,
        reason=reason,
        old=old,
        current=current,
        test_paths=test_paths,
    )


if __name__ == "__main__":
    raise SystemExit(main())
