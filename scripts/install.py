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

# Suppress human-readable dry-run/backup prints when --json is active so the
# emitted JSON on stdout stays machine-parseable. Off by default.
_QUIET = False


def _say(msg: str) -> None:
    if not _QUIET:
        print(msg)


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any], dry_run: bool) -> bool:
    body = json.dumps(data, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == body:
        return False
    if dry_run:
        _say(f"would write {path}")
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_suffix(path.suffix + ".bak")
        if not backup.exists():
            shutil.copy2(path, backup)
            _say(f"backup: {backup}")
    path.write_text(body, encoding="utf-8")
    return True


def copy_file(src: Path, dest: Path, dry_run: bool) -> bool:
    if dest.exists() and dest.read_bytes() == src.read_bytes():
        return False
    if dry_run:
        _say(f"would copy {src} -> {dest}")
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        backup = dest.with_suffix(dest.suffix + ".bak")
        if not backup.exists():
            shutil.copy2(dest, backup)
            _say(f"backup: {backup}")
    shutil.copy2(src, dest)
    return True


def install_runtime(target: Path, dry_run: bool) -> list[str]:
    for src in (ROOT / "scripts").glob("quality_loop*.py"):
        copy_file(src, target / "scripts" / src.name, dry_run)
    for src in (ROOT / "hosts" / "claude-code").glob("*.py"):
        copy_file(src, target / "hosts" / "claude-code" / src.name, dry_run)
    # Model-routing setup and check-config both need the example config on disk.
    example_cfg = ROOT / "assets" / "quality-loop.config.example.json"
    if example_cfg.is_file():
        copy_file(example_cfg, target / "assets" / "quality-loop.config.example.json", dry_run)
    # Pre-validated routing variants (the intelligence<->cost knob) + dated menu.
    for src in sorted((ROOT / "assets" / "routing").glob("*")):
        if src.is_file():
            copy_file(src, target / "assets" / "routing" / src.name, dry_run)
    # Control-plane dashboard: control-serve looks for it next to scripts/.
    for src in sorted((ROOT / "assets" / "control-plane").glob("*")):
        if src.is_file():
            copy_file(src, target / "assets" / "control-plane" / src.name, dry_run)
    return ["Runtime: copied stdlib Quality Loop scripts, host hook shims, example config, routing variants, and the control-plane dashboard"]


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
    report = [
        "Claude Code: SKILL.md + references/ + assets/ copied to .claude/skills/coding-quality-loop/",
        "Claude Code: advisory project hooks merged into .claude/settings.json",
        "Claude Code: role subagents copied to .claude/agents/",
    ]
    install_skill_bundle(target / ".claude" / "skills" / "coding-quality-loop", dry_run)
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


def install_droid(target: Path, dry_run: bool) -> list[str]:
    report = ["Droid: role droids copied to .factory/droids/ (model: inherit; run setup-models to wire models)"]
    src_dir = ROOT / "examples" / "droid" / ".factory" / "droids"
    for src in src_dir.glob("*.md"):
        copy_file(src, target / ".factory" / "droids" / src.name, dry_run)
    return report


def _copy_tree(src: Path, dest: Path, dry_run: bool) -> None:
    if not src.is_dir():
        return
    for item in src.rglob("*"):
        if item.is_dir():
            continue
        # Skip Python bytecode caches so they never land in a user's project.
        parts = item.relative_to(src).parts
        if "__pycache__" in parts or item.suffix == ".pyc":
            continue
        rel = item.relative_to(src)
        copy_file(item, dest / rel, dry_run)


def install_skill_bundle(dest_skill_dir: Path, dry_run: bool) -> None:
    """Copy the portable skill bundle (SKILL.md + references + templates)
    into a host-specific skill directory such as .claude/skills/coding-quality-loop/
    or .pi/skills/coding-quality-loop/. This is what makes the host actually
    *discover* the skill, not just wire hooks."""
    # SKILL.md — the entry point every host loader reads.
    src_skill = ROOT / "SKILL.md"
    if src_skill.is_file():
        copy_file(src_skill, dest_skill_dir / "SKILL.md", dry_run)
    # references/ — progressive-disclosure deep dives (loaded on demand).
    _copy_tree(ROOT / "references", dest_skill_dir / "references", dry_run)
    # assets/ — templates the skill references (validation contract, plans, etc.).
    _copy_tree(ROOT / "assets", dest_skill_dir / "assets", dry_run)
    # scripts/ — the helper scripts SKILL.md tells the agent to invoke.
    _copy_tree(ROOT / "scripts", dest_skill_dir / "scripts", dry_run)


def install_cursor(target: Path, dry_run: bool) -> list[str]:
    report = ["Cursor: skill rules copied to .cursor/ (invoke with @coding-quality-loop in chat)"]
    _copy_tree(ROOT / "examples" / "cursor" / ".cursor", target / ".cursor", dry_run)
    return report


def install_pi(target: Path, dry_run: bool) -> list[str]:
    report = [
        "Pi: SKILL.md + references/ + assets/ copied to .pi/skills/coding-quality-loop/",
        "Pi: local settings copied to .pi/ (invoke with /skill:coding-quality-loop)",
    ]
    install_skill_bundle(target / ".pi" / "skills" / "coding-quality-loop", dry_run)
    _copy_tree(ROOT / "examples" / "pi" / ".pi", target / ".pi", dry_run)
    return report


def _resolve_python() -> str:
    """Return the first Python interpreter that works on this platform.
    Mirrors the Node-side resolver so Windows users with only `python` on PATH
    still install the git hook cleanly."""
    import sys
    # Prefer the interpreter running us — always correct if we got this far.
    if sys.executable:
        return sys.executable
    for candidate in ("python3", "python"):
        if shutil.which(candidate):
            return candidate
    return "python3"  # last-resort; subprocess will surface a clear error


def install_git(target: Path, dry_run: bool) -> list[str]:
    report = ["Git: pre-commit blocks staged diff-audit findings; --no-verify bypass remains explicit"]
    if dry_run:
        _say("would run hosts/git/install-git-hooks.py")
    else:
        # `target` may not exist yet on a fresh install; create it so `cwd=` does not raise.
        target.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [_resolve_python(), str(ROOT / "hosts" / "git" / "install-git-hooks.py")],
            cwd=target,
            check=False,
        )
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
    parser.add_argument(
        "--host",
        choices=["all", "claude-code", "codex", "cursor", "droid", "pi", "git", "github"],
        default="all",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true", help="emit the wiring report as JSON on stdout")
    args = parser.parse_args()

    global _QUIET
    _QUIET = args.json

    target = Path(args.target).resolve()
    installers = {
        "claude-code": install_claude,
        "codex": install_codex,
        "cursor": install_cursor,
        "droid": install_droid,
        "pi": install_pi,
        "git": install_git,
        "github": install_github,
    }
    selected = installers if args.host == "all" else {args.host: installers[args.host]}
    report: list[str] = []
    if {"claude-code", "codex", "droid", "git"} & set(selected):
        report.extend(install_runtime(target, args.dry_run))
    for installer in selected.values():
        report.extend(installer(target, args.dry_run))
    footer = [
        "Core gates remain scripts/quality_loop.py; host hooks are advisory unless your host config requires them.",
        "Next: copy assets/quality-loop.config.example.json to quality-loop.config.json, set model_routing, run: python3 scripts/quality_loop.py setup-models",
    ]
    if args.json:
        payload = {
            "host": args.host,
            "target": str(target),
            "dry_run": args.dry_run,
            "hosts_installed": sorted(selected.keys()),
            "report": report,
            "footer": footer,
        }
        print(json.dumps(payload, indent=2))
    else:
        print("Quality Loop wiring report:")
        for line in report:
            print(f"- {line}")
        for line in footer:
            print(f"- {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
