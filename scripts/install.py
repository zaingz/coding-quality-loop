#!/usr/bin/env python3
"""Idempotent installer for Coding Quality Loop host integrations."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any], dry_run: bool) -> bool:
    body = json.dumps(data, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == body:
        return False
    if dry_run:
        print(f"would write {path}")
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_suffix(path.suffix + ".bak")
        if not backup.exists():
            shutil.copy2(path, backup)
            print(f"backup: {backup}")
    path.write_text(body, encoding="utf-8")
    return True


def copy_file(src: Path, dest: Path, dry_run: bool) -> bool:
    if dest.exists() and dest.read_bytes() == src.read_bytes():
        return False
    if dry_run:
        print(f"would copy {src} -> {dest}")
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        backup = dest.with_suffix(dest.suffix + ".bak")
        if not backup.exists():
            shutil.copy2(dest, backup)
            print(f"backup: {backup}")
    shutil.copy2(src, dest)
    return True


def install_runtime(target: Path, dry_run: bool) -> list[str]:
    for src in (ROOT / "scripts").glob("quality_loop*.py"):
        copy_file(src, target / "scripts" / src.name, dry_run)
    for src in (ROOT / "hosts" / "claude-code").glob("*.py"):
        copy_file(src, target / "hosts" / "claude-code" / src.name, dry_run)
    return ["Runtime: copied stdlib Quality Loop scripts and host hook shims"]


def merge_hooks(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    out = dict(existing)
    hooks = dict(out.get("hooks") or {})
    for event, groups in (incoming.get("hooks") or {}).items():
        current = list(hooks.get(event) or [])
        for group in groups:
            if group not in current:
                current.append(group)
        hooks[event] = current
    out["hooks"] = hooks
    return out


def install_claude(target: Path, dry_run: bool) -> list[str]:
    report = ["Claude Code: advisory project hooks in .claude/settings.json"]
    incoming = load_json(ROOT / "hosts" / "claude-code" / "settings.json")
    dest = target / ".claude" / "settings.json"
    write_json(dest, merge_hooks(load_json(dest), incoming), dry_run)
    for src in (ROOT / ".claude" / "agents").glob("*.md"):
        copy_file(src, target / ".claude" / "agents" / src.name, dry_run)
    return report


def install_codex(target: Path, dry_run: bool) -> list[str]:
    report = ["Codex: advisory project hooks in .codex/hooks.json; user must trust via /hooks"]
    incoming = load_json(ROOT / "hosts" / "codex" / "hooks.json")
    dest = target / ".codex" / "hooks.json"
    write_json(dest, merge_hooks(load_json(dest), incoming), dry_run)
    return report


def install_git(target: Path, dry_run: bool) -> list[str]:
    report = ["Git: pre-commit blocks staged diff-audit findings; --no-verify bypass remains explicit"]
    if dry_run:
        print("would run hosts/git/install-git-hooks.py")
    else:
        subprocess.run(["python3", str(ROOT / "hosts" / "git" / "install-git-hooks.py")], cwd=target, check=False)
    copy_file(ROOT / "hosts" / "git" / ".pre-commit-config.yaml", target / ".pre-commit-config.yaml", dry_run)
    return report


def install_github(target: Path, dry_run: bool) -> list[str]:
    report = ["GitHub: composite action available; example workflow copied under .github/workflows"]
    copy_file(
        ROOT / "hosts" / "github" / "quality-loop-example.yml",
        target / ".github" / "workflows" / "quality-loop.yml",
        dry_run,
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Install Coding Quality Loop host wiring")
    parser.add_argument("--target", default=".", help="Project root to install into")
    parser.add_argument("--host", choices=["all", "claude-code", "codex", "git", "github"], default="all")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    target = Path(args.target).resolve()
    installers = {
        "claude-code": install_claude,
        "codex": install_codex,
        "git": install_git,
        "github": install_github,
    }
    selected = installers if args.host == "all" else {args.host: installers[args.host]}
    report: list[str] = []
    if {"claude-code", "codex", "git"} & set(selected):
        report.extend(install_runtime(target, args.dry_run))
    for installer in selected.values():
        report.extend(installer(target, args.dry_run))
    print("Quality Loop wiring report:")
    for line in report:
        print(f"- {line}")
    print("- Core gates remain scripts/quality_loop.py; host hooks are advisory unless your host config requires them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
