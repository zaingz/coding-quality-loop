#!/usr/bin/env python3
"""Idempotent installer for Coding Quality Loop host integrations."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import re
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

MANIFEST_REL = ".quality-loop/install-manifest.json"

AGENTS_BEGIN = "<!-- BEGIN coding-quality-loop managed section -->"
AGENTS_END = "<!-- END coding-quality-loop managed section -->"
AGENTS_SECTION_KEY = "managed-section"

# Suppress human-readable dry-run/backup prints when --json is active so the
# emitted JSON on stdout stays machine-parseable. Off by default.
_QUIET = False

# Opt-in for the control plane (quality_loop_control.py, the control_plane.py
# hook shim, the dashboard, and routing variants). Off by default since v6.
_WITH_CONTROL_PLANE = False

# Manifest bookkeeping: every path written and every hook group merged, so
# `cql check` can verify the install and --uninstall can reverse it.
_MANIFEST_FILES: list[Path] = []
_MANIFEST_HOOK_GROUPS: list[dict[str, str]] = []
# Files that already existed (and were not ours from a prior install) when we
# first touched them — byte-identical coincidences we must NOT delete on
# uninstall. Overwritten user files are handled separately via .bak restore.
_MANIFEST_PREEXISTING: set[Path] = set()

# Paths a previous install manifest already records as ours. Overwriting our
# own files (idempotent re-install, upgrade) must NOT create .bak backups —
# a .bak always means "the user's pre-install file", which uninstall restores.
_TARGET: Path | None = None
_OWNED: set[str] = set()

# Host installs that failed (reported honestly; makes main() exit nonzero).
_FAILURES: list[str] = []


def _say(msg: str) -> None:
    if not _QUIET:
        print(msg)


def _record_file(dest: Path) -> None:
    if dest not in _MANIFEST_FILES:
        _MANIFEST_FILES.append(dest)


def _record_hook_group(rel_file: str, key: str) -> None:
    entry = {"file": rel_file, "key": key}
    if entry not in _MANIFEST_HOOK_GROUPS:
        _MANIFEST_HOOK_GROUPS.append(entry)


def _is_owned(dest: Path) -> bool:
    if _TARGET is None:
        return False
    try:
        return dest.relative_to(_TARGET).as_posix() in _OWNED
    except ValueError:
        return False


def _backup_before_overwrite(path: Path) -> None:
    """Back up a user's pre-install file before we overwrite it. Files a prior
    manifest records as ours are overwritten in place — no backup."""
    if not path.exists() or _is_owned(path):
        return
    backup = path.with_suffix(path.suffix + ".bak")
    if not backup.exists():
        shutil.copy2(path, backup)
        _say(f"backup: {backup}")


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _note_preexisting(path: Path) -> None:
    """A file that exists, isn't already ours, is a coincidental match — record
    it so uninstall never deletes a user file it did not create."""
    if path.exists() and not _is_owned(path):
        _MANIFEST_PREEXISTING.add(path)


def write_json(path: Path, data: dict[str, Any], dry_run: bool) -> bool:
    _record_file(path)
    body = json.dumps(data, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == body:
        _note_preexisting(path)
        return False
    if dry_run:
        _say(f"would write {path}")
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    _backup_before_overwrite(path)
    path.write_text(body, encoding="utf-8")
    return True


def copy_file(src: Path, dest: Path, dry_run: bool) -> bool:
    _record_file(dest)
    if dest.exists() and dest.read_bytes() == src.read_bytes():
        _note_preexisting(dest)
        return False
    if dry_run:
        _say(f"would copy {src} -> {dest}")
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    _backup_before_overwrite(dest)
    shutil.copy2(src, dest)
    return True


_AGENT_MODEL_LINE = re.compile(r"^model:.*$", flags=re.MULTILINE)
_AGENT_THINKING_LINE = re.compile(r"^(?:effort|reasoningEffort):.*\n", flags=re.MULTILINE)


def copy_agent_neutral(src: Path, dest: Path, dry_run: bool) -> bool:
    """Copy a role-subagent file with any routing pins neutralized.

    The source repo's agent files may carry an operator's activated routing
    (``model:`` / ``effort:`` frontmatter written by ``setup-models``), but
    shipped templates stay host-neutral at rest — consumers wire models via
    their own ``model_routing`` + ``setup-models``. Only the leading
    frontmatter block is touched: ``model:`` resets to ``inherit`` and the
    thinking key is dropped.
    """
    body = src.read_text(encoding="utf-8")
    if body.startswith("---\n"):
        end = body.find("\n---", 4)
        if end != -1:
            head = _AGENT_MODEL_LINE.sub("model: inherit", body[: end + 4])
            head = _AGENT_THINKING_LINE.sub("", head)
            body = head + body[end + 4:]
    _record_file(dest)
    if dest.exists() and dest.read_text(encoding="utf-8") == body:
        _note_preexisting(dest)
        return False
    if dry_run:
        _say(f"would copy (model-neutral) {src} -> {dest}")
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    _backup_before_overwrite(dest)
    dest.write_text(body, encoding="utf-8")
    return True


def _write_text(path: Path, body: str, dry_run: bool) -> None:
    """Write text with the same backup discipline as copy_file/write_json."""
    if dry_run:
        _say(f"would write {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    _backup_before_overwrite(path)
    path.write_text(body, encoding="utf-8")


def install_runtime(target: Path, dry_run: bool) -> list[str]:
    for src in (ROOT / "scripts").glob("quality_loop*.py"):
        if src.name == "quality_loop_control.py" and not _WITH_CONTROL_PLANE:
            continue
        copy_file(src, target / "scripts" / src.name, dry_run)
    for src in (ROOT / "hosts" / "claude-code").glob("*.py"):
        if src.name == "control_plane.py" and not _WITH_CONTROL_PLANE:
            continue
        copy_file(src, target / "hosts" / "claude-code" / src.name, dry_run)
    # Model-routing setup and check-config both need the example config on disk.
    example_cfg = ROOT / "assets" / "quality-loop.config.example.json"
    if example_cfg.is_file():
        copy_file(example_cfg, target / "assets" / "quality-loop.config.example.json", dry_run)
    # render-prompt resolves assets/prompts/<role>.md as a sibling of scripts/;
    # ship the prompt cards with every runtime install so it works end to end.
    for src in sorted((ROOT / "assets" / "prompts").glob("*.md")):
        copy_file(src, target / "assets" / "prompts" / src.name, dry_run)
    # Pre-validated routing variants (the intelligence<->cost knob) + dated menu.
    # Core routing, NOT part of the control-plane opt-in: SKILL.md and
    # setup-models reference assets/routing/ on a default install.
    for src in sorted((ROOT / "assets" / "routing").glob("*")):
        if src.is_file():
            copy_file(src, target / "assets" / "routing" / src.name, dry_run)
    report = [
        "Runtime: copied stdlib Quality Loop scripts, host hook shims, the example config, "
        "render-prompt cards (assets/prompts/), and routing variants (assets/routing/)"
    ]
    if _WITH_CONTROL_PLANE:
        # Control-plane dashboard: control-serve looks for it next to scripts/.
        for src in sorted((ROOT / "assets" / "control-plane").glob("*")):
            if src.is_file():
                copy_file(src, target / "assets" / "control-plane" / src.name, dry_run)
        report.append(
            "Control plane: opted in — copied quality_loop_control.py, the control_plane.py "
            "hook shim, and the dashboard"
        )
    return report


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


def _strip_control_plane_hooks(incoming: dict[str, Any]) -> dict[str, Any]:
    """Drop hook groups that invoke the control plane unless --with-control-plane
    opted in — wiring hooks to a script the install does not copy would make
    every session print a missing-file error."""
    if _WITH_CONTROL_PLANE:
        return incoming
    hooks: dict[str, Any] = {}
    for event, groups in (incoming.get("hooks") or {}).items():
        kept = [g for g in groups if "control_plane.py" not in json.dumps(g)]
        if kept:
            hooks[event] = kept
    out = dict(incoming)
    out["hooks"] = hooks
    return out


def install_claude(target: Path, dry_run: bool) -> list[str]:
    report = [
        "Claude Code: SKILL.md + references/ + assets/ copied to .claude/skills/coding-quality-loop/",
        "Claude Code: advisory project hooks merged into .claude/settings.json",
        "Claude Code: role subagents copied to .claude/agents/",
    ]
    install_skill_bundle(target / ".claude" / "skills" / "coding-quality-loop", dry_run)
    incoming = _strip_control_plane_hooks(load_json(ROOT / "hosts" / "claude-code" / "settings.json"))
    # Hosts without `python3` on PATH (Windows, minimal images) get the resolved
    # absolute interpreter written into the hook JSON so the gates still fire —
    # the fix must land at this launcher layer, not just the shims. When
    # `python3` IS on PATH the portable literal is kept: settings.json is often
    # committed and shared, and a machine-specific absolute path would silently
    # disable the gates for every other clone (re-run install per machine if
    # your interpreter setup differs).
    launcher = _launcher_interpreter()
    if launcher:
        _rewrite_python_launcher(incoming, launcher)
    dest = target / ".claude" / "settings.json"
    write_json(dest, merge_hooks(load_json(dest), incoming), dry_run)
    for event in (incoming.get("hooks") or {}):
        _record_hook_group(".claude/settings.json", event)
    for src in (ROOT / ".claude" / "agents").glob("*.md"):
        copy_agent_neutral(src, target / ".claude" / "agents" / src.name, dry_run)
    return report


def install_agents_md(target: Path, dry_run: bool) -> str:
    """Ship Codex's AGENTS.md: copy the template when absent; otherwise append
    (or refresh) a clearly-marked managed section so user content is preserved."""
    src = ROOT / "assets" / "AGENTS.template.md"
    dest = target / "AGENTS.md"
    if not src.is_file():
        return "Codex: assets/AGENTS.template.md not found in this distribution; AGENTS.md not written"
    body = src.read_text(encoding="utf-8").rstrip("\n")
    if not dest.exists():
        copy_file(src, dest, dry_run)
        return "Codex: AGENTS.md created from assets/AGENTS.template.md"
    existing = dest.read_text(encoding="utf-8")
    if existing.rstrip("\n") == body:
        _record_file(dest)
        return "Codex: AGENTS.md already matches the template; left as-is"
    section = f"{AGENTS_BEGIN}\n{body}\n{AGENTS_END}"
    if AGENTS_BEGIN in existing and AGENTS_END in existing:
        _record_hook_group("AGENTS.md", AGENTS_SECTION_KEY)
        head, _, rest = existing.partition(AGENTS_BEGIN)
        _, _, tail = rest.partition(AGENTS_END)
        updated = head + section + tail
        if updated == existing:
            return "Codex: AGENTS.md managed section already up to date"
        _write_text(dest, updated, dry_run)
        return "Codex: refreshed the managed Quality Loop section in AGENTS.md"
    if body in existing:
        return "Codex: AGENTS.md already contains the template content; left as-is"
    _record_hook_group("AGENTS.md", AGENTS_SECTION_KEY)
    _write_text(dest, existing.rstrip("\n") + "\n\n" + section + "\n", dry_run)
    return "Codex: appended a managed Quality Loop section to your existing AGENTS.md"


def install_codex(target: Path, dry_run: bool) -> list[str]:
    report = ["Codex: advisory project hooks in .codex/hooks.json; user must trust via /hooks"]
    incoming = _strip_control_plane_hooks(load_json(ROOT / "hosts" / "codex" / "hooks.json"))
    # Same policy as the Claude hooks: keep the portable `python3` literal when
    # it is on PATH; swap in the resolved interpreter only where python3 is
    # absent. The POSIX $(git rev-parse ...) part is inherent to the Codex
    # format and is left as-is (see the non-POSIX warning).
    launcher = _launcher_interpreter()
    if launcher:
        _rewrite_python_launcher(incoming, launcher)
    dest = target / ".codex" / "hooks.json"
    write_json(dest, merge_hooks(load_json(dest), incoming), dry_run)
    for event in (incoming.get("hooks") or {}):
        _record_hook_group(".codex/hooks.json", event)
    if os.name != "posix":
        report.append(
            "Codex: WARNING — the Codex hooks resolve the repo root via a POSIX "
            "$(git rev-parse --show-toplevel) substitution; on this non-POSIX platform they may "
            "not fire. Run Codex from a POSIX shell (WSL/Git Bash) or wire the hooks by hand."
        )
    if not _is_git_repo(target):
        report.append(
            "Codex: WARNING — the target is not a git repository, so every wired hook's "
            "$(git rev-parse --show-toplevel) will fail at runtime. Run `git init` in the target "
            "before relying on the Codex hooks."
        )
    report.append(install_agents_md(target, dry_run))
    return report


def install_droid(target: Path, dry_run: bool) -> list[str]:
    report = ["Droid: role droids copied to .factory/droids/ (model: inherit; run setup-models to wire models)"]
    src_dir = ROOT / "examples" / "droid" / ".factory" / "droids"
    for src in src_dir.glob("*.md"):
        copy_file(src, target / ".factory" / "droids" / src.name, dry_run)
    return report


def _copy_tree(src: Path, dest: Path, dry_run: bool, skip_dirs: tuple[str, ...] = ()) -> None:
    if not src.is_dir():
        return
    for item in src.rglob("*"):
        if item.is_dir():
            continue
        # Skip Python bytecode caches so they never land in a user's project.
        parts = item.relative_to(src).parts
        if "__pycache__" in parts or item.suffix == ".pyc":
            continue
        if parts and parts[0] in skip_dirs:
            continue
        rel = item.relative_to(src)
        copy_file(item, dest / rel, dry_run)


def install_skill_bundle(dest_skill_dir: Path, dry_run: bool) -> None:
    """Copy the portable skill bundle (SKILL.md + references + templates)
    into a host-specific skill directory such as .claude/skills/coding-quality-loop/
    or .pi/skills/coding-quality-loop/. This is what makes the host actually
    *discover* the skill, not just wire hooks. The runtime scripts are NOT
    duplicated here: the single runtime copy lives at <target>/scripts/ (see
    install_runtime), which is the path SKILL.md and the host hooks reference."""
    # SKILL.md — the entry point every host loader reads.
    src_skill = ROOT / "SKILL.md"
    if src_skill.is_file():
        copy_file(src_skill, dest_skill_dir / "SKILL.md", dry_run)
    # references/ — progressive-disclosure deep dives (loaded on demand).
    _copy_tree(ROOT / "references", dest_skill_dir / "references", dry_run)
    # assets/ — templates the skill references (validation contract, plans,
    # routing variants, etc.). Only the control-plane dashboard is opt-in;
    # routing is core (SKILL.md references assets/routing/ on every install).
    skip = () if _WITH_CONTROL_PLANE else ("control-plane",)
    _copy_tree(ROOT / "assets", dest_skill_dir / "assets", dry_run, skip_dirs=skip)


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


def _launcher_interpreter() -> str | None:
    """Interpreter to write into hook JSON, or None to keep the portable
    ``python3`` literal. Only substitute when ``python3`` is genuinely absent
    from PATH (the Windows/minimal-image case): hook settings are often
    committed and shared, and a machine-specific absolute path in a shared
    file silently disables the gates on every other machine."""
    if shutil.which("python3"):
        return None
    return _resolve_python()


def _rewrite_python_launcher(obj: Any, interpreter: str) -> None:
    """In-place: replace the literal ``python3`` launcher in hook commands with
    the resolved interpreter so hosts where ``python3`` is absent from PATH
    (Windows, minimal images) still fire the gates. Two hook shapes are handled:

      - Claude Code: ``{"command": "python3", "args": [...]}`` — the command is
        exec'd directly, so the interpreter path is dropped in verbatim.
      - Codex: ``{"command": "python3 \"$(git rev-parse ...)/x.py\" ..."}`` — the
        whole invocation is a single shell string; only the leading ``python3``
        token is swapped (quoted), leaving the POSIX ``$(...)`` substitution the
        Codex format inherently requires intact.
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "command" and isinstance(value, str):
                if value == "python3":
                    obj[key] = interpreter
                elif value.startswith("python3 "):
                    obj[key] = shlex.quote(interpreter) + value[len("python3"):]
            else:
                _rewrite_python_launcher(value, interpreter)
    elif isinstance(obj, list):
        for item in obj:
            _rewrite_python_launcher(item, interpreter)


def _is_git_repo(target: Path) -> bool:
    """True when ``target`` is inside a git work tree. Used to warn before wiring
    Codex hooks, whose $(git rev-parse --show-toplevel) dies at runtime outside
    a repo."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def install_git(target: Path, dry_run: bool) -> list[str]:
    report: list[str] = []
    if dry_run:
        _say("would run hosts/git/install-git-hooks.py")
        report.append("Git: pre-commit blocks staged diff-audit findings; --no-verify bypass remains explicit")
    else:
        # `target` may not exist yet on a fresh install; create it so `cwd=` does not raise.
        target.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            [_resolve_python(), str(ROOT / "hosts" / "git" / "install-git-hooks.py")],
            cwd=target,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc.returncode == 0:
            _record_file(target / ".git" / "hooks" / "pre-commit")
            report.append("Git: pre-commit blocks staged diff-audit findings; --no-verify bypass remains explicit")
        else:
            detail = (proc.stderr or proc.stdout or "").strip().splitlines()
            reason = detail[-1] if detail else f"exit code {proc.returncode}"
            failure = (
                f"Git: pre-commit hook install FAILED ({reason}) — "
                "run this inside a git repository (git init first), or run "
                "python3 hosts/git/install-git-hooks.py there to see the full error"
            )
            report.append(failure)
            _FAILURES.append(failure)
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


def write_manifest(target: Path, hosts_installed: list[str], dry_run: bool) -> None:
    """Record every path written and every hook group merged so `cql check` can
    verify the install and --uninstall can reverse it. Re-installs merge with an
    existing manifest so multi-host installs accumulate instead of clobbering."""
    if dry_run:
        return
    path = target / MANIFEST_REL
    hosts = set(hosts_installed)
    files = {p.relative_to(target).as_posix() for p in _MANIFEST_FILES}
    groups = list(_MANIFEST_HOOK_GROUPS)
    try:
        previous = load_json(path)
    except (json.JSONDecodeError, OSError):
        previous = {}
        _say(f"warning: existing manifest at {path} was unreadable; rewriting it from this install only")
    preexisting = {p.relative_to(target).as_posix() for p in _MANIFEST_PREEXISTING}
    hosts.update(h for h in str(previous.get("host") or "").split(",") if h)
    files.update(f for f in previous.get("files") or [] if isinstance(f, str))
    preexisting.update(f for f in previous.get("preexisting") or [] if isinstance(f, str))
    # A path recorded as pre-existing must not also be claimed as ours to delete.
    preexisting &= files
    for group in previous.get("hook_groups") or []:
        if isinstance(group, dict) and group not in groups:
            groups.append(group)
    manifest = {
        "version": 1,
        "host": ",".join(sorted(hosts)),
        "files": sorted(files),
        "preexisting": sorted(preexisting),
        "hook_groups": groups,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------

def _rel_inside_target(rel: str) -> bool:
    p = Path(rel)
    return not p.is_absolute() and ".." not in p.parts


def _resolves_inside_target(target: Path, rel: str) -> bool:
    """True only when target/rel, after resolving symlinks in EVERY component,
    still lands inside the target root. A lexically-safe manifest entry like
    'linkdir/file.txt' escapes when 'linkdir' is a symlink to '../victim';
    uninstall must never unlink/move/write through such a path."""
    try:
        return (target / rel).resolve().is_relative_to(target.resolve())
    except OSError:
        return False


def _existing_backup(path: Path) -> Path | None:
    """Return the backup this installer (or install-git-hooks.py) would have
    written for ``path``, if it exists on disk."""
    for backup in (
        path.with_suffix(path.suffix + ".bak"),
        path.with_suffix(".pre-quality-loop-backup"),
    ):
        if backup != path and backup.is_file():
            return backup
    return None


def _quality_loop_hook_markers() -> set[str]:
    """The stable identity of our hook groups: the ``hosts/<host>/<shim>.py``
    script paths the shipped host configs reference. Uninstall matches groups
    by these markers rather than by dict equality, so a group written with an
    interpreter that has since moved (python upgrade, different machine) is
    still recognised as ours and removed instead of orphaned."""
    markers: set[str] = set()
    for rel in (("hosts", "claude-code", "settings.json"), ("hosts", "codex", "hooks.json")):
        try:
            raw = json.dumps(load_json(ROOT.joinpath(*rel)))
        except (json.JSONDecodeError, OSError):
            continue
        markers.update(re.findall(r"hosts/[\w.-]+/[\w.-]+\.py", raw))
    # control_plane.py groups are stripped at install time for non-control
    # installs, but a --with-control-plane install writes them — always ours.
    markers.add("hosts/claude-code/control_plane.py")
    return markers


def _is_quality_loop_group(group: dict[str, Any], markers: set[str]) -> bool:
    """A hook group is ours iff it invokes one of our shipped shim scripts,
    whatever interpreter token or absolute path prefix it was written with."""
    text = json.dumps(group)
    return any(marker in text for marker in markers)


def _remove_agents_section(path: Path, rel: str, dry_run: bool) -> list[str]:
    """Strip the marked managed section from a user AGENTS.md, preferring the
    pre-install backup when one exists."""
    backup = _existing_backup(path)
    if backup is not None:
        if dry_run:
            return [f"would restore {rel} from {backup.name}"]
        shutil.move(str(backup), str(path))
        return [f"restored {rel} from {backup.name}"]
    body = path.read_text(encoding="utf-8")
    if AGENTS_BEGIN not in body or AGENTS_END not in body:
        return [f"left {rel} alone (no managed Quality Loop section found)"]
    if dry_run:
        return [f"would remove the managed Quality Loop section from {rel}"]
    head, _, rest = body.partition(AGENTS_BEGIN)
    _, _, tail = rest.partition(AGENTS_END)
    updated = head.rstrip("\n") + "\n" + tail.lstrip("\n") if tail.strip() else head.rstrip("\n") + "\n"
    path.write_text(updated, encoding="utf-8")
    return [f"removed the managed Quality Loop section from {rel}"]


def _prune_empty_dirs(target: Path, path: Path) -> None:
    parent = path.parent
    while parent != target and target in parent.parents:
        try:
            parent.rmdir()
        except OSError:
            return
        parent = parent.parent


def uninstall(target: Path, dry_run: bool) -> tuple[int, list[str]]:
    """Reverse a manifest-recorded install: remove listed files, reverse merged
    hook groups group-by-group, restore backups, and leave user files alone."""
    manifest_path = target / MANIFEST_REL
    report: list[str] = []
    if not manifest_path.is_file():
        report.append(
            f"No install manifest found at {MANIFEST_REL}, so there is nothing recorded "
            "to remove. Installs before v6.0.0 wrote no manifest — re-run the installer "
            "once (npx cql init or python3 scripts/install.py) to record one, then uninstall."
        )
        return 1, report
    try:
        manifest = load_json(manifest_path)
    except (json.JSONDecodeError, OSError) as exc:
        report.append(
            f"Could not parse {MANIFEST_REL} ({exc}). Delete it and re-run the installer "
            "to regenerate the manifest, then uninstall."
        )
        return 1, report

    preexisting = {
        f for f in (manifest.get("preexisting") or []) if isinstance(f, str)
    }
    listed = sorted({
        f for f in (manifest.get("files") or [])
        if isinstance(f, str) and _rel_inside_target(f) and f not in preexisting
    })
    files = [f for f in listed if _resolves_inside_target(target, f)]
    lexical_groups = [
        g for g in (manifest.get("hook_groups") or [])
        if isinstance(g, dict) and isinstance(g.get("file"), str)
        and isinstance(g.get("key"), str) and _rel_inside_target(g["file"])
    ]
    groups = [g for g in lexical_groups if _resolves_inside_target(target, g["file"])]
    for rel in sorted(set(
        [f for f in listed if f not in files]
        + [g["file"] for g in lexical_groups if g not in groups]
    )):
        report.append(
            f"skipped {rel} (resolves outside the install target through a symlink; not touched)"
        )
    handled: set[str] = set()
    removed_paths: list[Path] = []
    hook_markers = _quality_loop_hook_markers()

    # 1) Reverse merged hook groups (or restore the pre-install backup wholesale).
    by_file: dict[str, list[str]] = {}
    for g in groups:
        by_file.setdefault(g["file"], []).append(g["key"])
    for rel, keys in sorted(by_file.items()):
        path = target / rel
        handled.add(rel)
        if not path.is_file():
            continue
        if AGENTS_SECTION_KEY in keys:
            report.extend(_remove_agents_section(path, rel, dry_run))
            continue
        backup = _existing_backup(path)
        if backup is not None:
            if dry_run:
                report.append(f"would restore {rel} from {backup.name}")
            else:
                shutil.move(str(backup), str(path))
                report.append(f"restored {rel} from {backup.name}")
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            report.append(
                f"{rel} is not valid JSON; left untouched — remove the Quality Loop "
                f"hook groups ({', '.join(keys)}) by hand."
            )
            continue
        hooks = data.get("hooks") if isinstance(data.get("hooks"), dict) else {}
        changed = False
        for key in keys:
            current = hooks.get(key)
            if not isinstance(current, list):
                continue
            remaining = [
                g for g in current
                if not (isinstance(g, dict) and _is_quality_loop_group(g, hook_markers))
            ]
            if remaining != current:
                changed = True
                if remaining:
                    hooks[key] = remaining
                else:
                    del hooks[key]
        if not hooks and set(data.keys()) <= {"hooks"} and rel in files:
            if dry_run:
                report.append(f"would remove {rel} (only Quality Loop hooks remained)")
            else:
                path.unlink()
                removed_paths.append(path)
                report.append(f"removed {rel} (only Quality Loop hooks remained)")
        elif changed:
            data["hooks"] = hooks
            if dry_run:
                report.append(f"would remove Quality Loop hook groups ({', '.join(keys)}) from {rel}")
            else:
                path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
                report.append(f"removed Quality Loop hook groups ({', '.join(keys)}) from {rel}")

    # 2) Remove manifest-listed files, restoring backups where present.
    for rel in files:
        if rel in handled:
            continue
        path = target / rel
        if not path.is_file():
            continue
        if rel == ".git/hooks/pre-commit" and "quality_loop.py diff-audit" not in path.read_text(
            encoding="utf-8", errors="replace"
        ):
            report.append(f"left {rel} alone (it no longer runs the Quality Loop diff-audit)")
            continue
        backup = _existing_backup(path)
        if dry_run:
            report.append(f"would {'restore' if backup else 'remove'} {rel}")
            continue
        if backup is not None:
            shutil.move(str(backup), str(path))
            report.append(f"restored {rel} from {backup.name}")
        else:
            path.unlink()
            removed_paths.append(path)
            report.append(f"removed {rel}")

    # 3) Drop the manifest itself and prune now-empty directories.
    if dry_run:
        report.append(f"would remove {MANIFEST_REL}")
    elif not _resolves_inside_target(target, MANIFEST_REL):
        report.append(
            f"skipped {MANIFEST_REL} (resolves outside the install target through a symlink; not touched)"
        )
        for path in removed_paths:
            _prune_empty_dirs(target, path)
    else:
        manifest_path.unlink()
        removed_paths.append(manifest_path)
        for path in removed_paths:
            _prune_empty_dirs(target, path)
        report.append(f"removed {MANIFEST_REL}")
    return 0, report


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
    parser.add_argument(
        "--with-control-plane",
        action="store_true",
        help="also install the optional control plane (quality_loop_control.py, hook shim, dashboard, routing variants)",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="remove the files recorded in .quality-loop/install-manifest.json and reverse merged hook groups",
    )
    args = parser.parse_args()

    global _QUIET, _WITH_CONTROL_PLANE, _TARGET
    _QUIET = args.json
    # The npm tarball excludes the control-plane module; opting in only works
    # from a repo checkout, so the flag degrades to off with an honest report.
    control_plane_available = (ROOT / "scripts" / "quality_loop_control.py").is_file()
    _WITH_CONTROL_PLANE = args.with_control_plane and control_plane_available

    target = Path(args.target).resolve()
    _TARGET = target
    try:
        for f in load_json(target / MANIFEST_REL).get("files") or []:
            if isinstance(f, str):
                _OWNED.add(f)
    except (json.JSONDecodeError, OSError):
        pass  # unreadable manifest: treat everything as user files (safe default)

    if args.uninstall:
        code, report = uninstall(target, args.dry_run)
        if args.json:
            payload = {
                "action": "uninstall",
                "target": str(target),
                "dry_run": args.dry_run,
                "report": report,
            }
            print(json.dumps(payload, indent=2))
        else:
            print("Quality Loop uninstall report:")
            for line in report:
                print(f"- {line}")
        return code

    installers = {
        "claude-code": install_claude,
        "codex": install_codex,
        "cursor": install_cursor,
        "droid": install_droid,
        "pi": install_pi,
        "git": install_git,
        "github": install_github,
    }
    # cursor/pi are demoted to advisory rules recipes (see README): an explicit
    # --host cursor/pi still copies them, but "all" wires only runtime hosts.
    if args.host == "all":
        selected = {h: fn for h, fn in installers.items() if h not in ("cursor", "pi")}
    else:
        selected = {args.host: installers[args.host]}
    report: list[str] = []
    if args.with_control_plane and not control_plane_available:
        report.append(
            "Control plane: --with-control-plane was requested but quality_loop_control.py is "
            "not in this distribution (the npm tarball excludes it) — clone "
            "https://github.com/zaingz/coding-quality-loop and run scripts/install.py from the repo"
        )
    if {"claude-code", "codex", "droid", "pi", "git"} & set(selected):
        report.extend(install_runtime(target, args.dry_run))
    for installer in selected.values():
        report.extend(installer(target, args.dry_run))
    write_manifest(target, sorted(selected.keys()), args.dry_run)
    if (target / ".quality-loop" / "config.json").is_file():
        report.append(
            "Config: legacy .quality-loop/config.json found — the canonical config is "
            "quality-loop.config.json at the project root; move your keys there "
            "(only the PreToolUse guard still reads the legacy file, as a one-release "
            "fallback with a warning; routing and the gates already read only the root config)"
        )
    # Host to point model_routing.host at (matches the npm CLI's modelRoutedHost:
    # a single-host default of claude-code when the install spanned every host).
    # git/github are hook/CI targets, not model-routing hosts — for those the
    # config/setup-models step is suppressed (mirrors the npm CLI's
    # showSetupModels gating) instead of recommending an unsupported host.
    routing_hosts = {"claude-code", "codex", "droid", "pi"}
    show_setup_models = args.host == "all" or args.host in routing_hosts
    host_hint = args.host if args.host in routing_hosts else "claude-code"
    footer = [
        "Core gates remain scripts/quality_loop.py; host hooks are advisory unless your host config requires them.",
        'Step 0 — commit the install so it stays out of your task diff: git add -A && git commit -m "chore: install coding-quality-loop"',
    ]
    if show_setup_models:
        if (target / "quality-loop.config.json").is_file():
            footer.append(
                "Next: review quality-loop.config.json (make sure model_routing.host is set), then run: "
                "python3 scripts/quality_loop.py setup-models"
            )
        else:
            footer.append(
                "Next: copy assets/quality-loop.config.example.json to quality-loop.config.json and set "
                f'model_routing.host to "{host_hint}" (the host you just installed) so cross-family '
                "review enforcement activates, then run: python3 scripts/quality_loop.py setup-models"
            )
    footer.append(
        "Then wire the CI anchor: add the GitHub Action (action.yml / "
        "hosts/github/quality-loop-example.yml) — merge-base anti-evasion and helper integrity are "
        "enforced in CI, so a local install alone does not activate them"
    )
    if args.json:
        payload = {
            "host": args.host,
            "target": str(target),
            "dry_run": args.dry_run,
            "hosts_installed": sorted(selected.keys()),
            "report": report,
            "failures": list(_FAILURES),
            "manifest": None if args.dry_run else MANIFEST_REL,
            "footer": footer,
        }
        print(json.dumps(payload, indent=2))
    else:
        print("Quality Loop wiring report:")
        for line in report:
            print(f"- {line}")
        for line in footer:
            print(f"- {line}")
    return 1 if _FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
