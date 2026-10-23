#!/usr/bin/env python3
"""Idempotent installer for Coding Quality Loop host integrations."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import re
import shlex
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

MANIFEST_REL = ".quality-loop/install-manifest.json"
REQUIRED_RUNTIME_MODULES = (
    "quality_loop.py",
    "quality_loop_core.py",
    "quality_loop_memory.py",
    "quality_loop_reality.py",
    "quality_loop_routing.py",
)

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
_MANIFEST_BACKUPS: dict[str, dict[str, str]] = {}

# Paths created or replaced by a previous install. Inventory alone does not
# confer ownership: a byte-identical file can have predated the first install.
# Its original bytes need a backup if a later release replaces it.
_TARGET: Path | None = None
_OWNED: set[str] = set()
_PREVIOUS_BACKUPS: dict[str, dict[str, str]] = {}

# Host installs that failed (reported honestly; makes main() exit nonzero).
_FAILURES: list[str] = []


def _say(msg: str) -> None:
    if not _QUIET:
        print(msg)


def _record_file(dest: Path) -> None:
    _assert_safe_destination(dest)
    _assert_no_unowned_backup(dest)
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
        _write_managed_bytes(backup, path.read_bytes(), stat.S_IMODE(path.stat().st_mode),
                             create_only=True)
        if _TARGET is not None:
            _MANIFEST_BACKUPS[path.relative_to(_TARGET).as_posix()] = {
                "path": backup.relative_to(_TARGET).as_posix(),
                "sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
            }
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


def _write_managed_bytes(path: Path, body: bytes, mode: int | None = None,
                         *, create_only: bool = False) -> None:
    """Commit a managed file relative to an opened target directory.

    Opening each parent with O_NOFOLLOW prevents a directory changed to a
    symlink after preflight from redirecting this write outside the target.
    This does not make an actively renamed target tree transactional; callers
    must not mutate the target concurrently with install/uninstall.
    """
    _assert_safe_destination(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _assert_safe_destination(path)
    if (_TARGET is None or os.name != "posix" or not hasattr(os, "O_NOFOLLOW")
            or not hasattr(os, "O_DIRECTORY")):
        if create_only:
            with path.open("xb") as out:
                out.write(body)
        else:
            path.write_bytes(body)
        if mode is not None:
            path.chmod(mode)
        return

    rel = path.relative_to(_TARGET)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory_fd = os.open(_TARGET, flags)
    temp_name: str | None = None
    try:
        for part in rel.parts[:-1]:
            child_fd = os.open(part, flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = child_fd
        name = rel.name
        try:
            old = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            old = None
        if old is not None and stat.S_ISLNK(old.st_mode):
            raise ValueError(f"{rel.as_posix()}: unsafe symlink at destination")
        if create_only and old is not None:
            raise FileExistsError(f"{rel.as_posix()}: backup appeared during install")
        temp_name = f".quality-loop-install-{os.urandom(8).hex()}"
        temp_fd = os.open(temp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                          0o666, dir_fd=directory_fd)
        with os.fdopen(temp_fd, "wb") as out:
            out.write(body)
            final_mode = mode if mode is not None else (stat.S_IMODE(old.st_mode) if old else None)
            if final_mode is not None:
                os.fchmod(out.fileno(), final_mode)
        # If the opened directory was replaced with a symlink during staging,
        # do not commit into the old directory through its still-live fd.
        opened = os.fstat(directory_fd)
        named = os.stat(path.parent, follow_symlinks=False)
        if (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino):
            raise ValueError(f"{rel.as_posix()}: managed directory changed during install")
        if create_only:
            # link() fails atomically if another process created this backup;
            # rename/replace would silently overwrite that unrelated file.
            os.link(temp_name, name, src_dir_fd=directory_fd,
                    dst_dir_fd=directory_fd, follow_symlinks=False)
            os.unlink(temp_name, dir_fd=directory_fd)
        else:
            os.replace(temp_name, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        temp_name = None
    finally:
        if temp_name is not None:
            try:
                os.unlink(temp_name, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
        os.close(directory_fd)


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
    _write_managed_bytes(path, body.encode("utf-8"))
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
    _write_managed_bytes(dest, src.read_bytes(), stat.S_IMODE(src.stat().st_mode))
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
    _write_managed_bytes(dest, body.encode("utf-8"))
    return True


def _write_text(path: Path, body: str, dry_run: bool) -> None:
    """Write text with the same backup discipline as copy_file/write_json."""
    _assert_safe_destination(path)
    _assert_no_unowned_backup(path)
    if dry_run:
        _say(f"would write {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    _backup_before_overwrite(path)
    _write_managed_bytes(path, body.encode("utf-8"))


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
            # Replace older copies of this managed shim instead of appending a
            # second invocation when a release changes its timeout or message.
            markers = set(re.findall(r"hosts/[\w.-]+/[\w.-]+\.py", json.dumps(group)))
            if markers:
                positions = [i for i, item in enumerate(current)
                             if any(marker in json.dumps(item) for marker in markers)]
                if positions:
                    first = positions[0]
                    matched = set(positions)
                    kept = []
                    for i, item in enumerate(current):
                        if i not in matched or not isinstance(item, dict) or not isinstance(item.get("hooks"), list):
                            kept.append(item)
                            continue
                        # A user may have placed another command in the same
                        # hook group. Keep it with the original matcher and
                        # replace only the entries that invoke our shim.
                        other_hooks = [hook for hook in item["hooks"]
                                       if not any(marker in json.dumps(hook) for marker in markers)]
                        if other_hooks:
                            kept.append({**item, "hooks": other_hooks})
                    current = kept
                    current.insert(first, group)
                    continue
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
    _assert_safe_destination(dest)
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
    _assert_safe_destination(dest)
    if not src.is_file():
        return "Codex: assets/AGENTS.template.md not found in this distribution; AGENTS.md not written"
    body = src.read_text(encoding="utf-8").rstrip("\n")
    if not dest.exists():
        copy_file(src, dest, dry_run)
        return "Codex: AGENTS.md created from assets/AGENTS.template.md"
    existing = dest.read_text(encoding="utf-8")
    if existing.rstrip("\n") == body:
        _record_file(dest)
        _note_preexisting(dest)
        return "Codex: AGENTS.md already matches the template; left as-is"
    section = f"{AGENTS_BEGIN}\n{body}\n{AGENTS_END}"
    if AGENTS_BEGIN in existing and AGENTS_END in existing:
        _record_hook_group("AGENTS.md", AGENTS_SECTION_KEY)
        head, _, rest = existing.partition(AGENTS_BEGIN)
        _, _, tail = rest.partition(AGENTS_END)
        updated = head + section + tail
        if updated == existing:
            _record_file(dest)
            _note_preexisting(dest)
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
    _assert_safe_destination(dest)
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
        hook = target / ".git" / "hooks" / "pre-commit"
        hook_before = hook.read_bytes() if hook.is_file() else None
        backup = hook.with_suffix(".pre-quality-loop-backup")
        backup_before = backup.exists() or backup.is_symlink()
        proc = subprocess.run(
            [_resolve_python(), str(ROOT / "hosts" / "git" / "install-git-hooks.py")],
            cwd=target,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc.returncode == 0:
            rel = hook.relative_to(target).as_posix()
            if backup.is_file() and not backup_before and rel not in _PREVIOUS_BACKUPS:
                _MANIFEST_BACKUPS[rel] = {
                    "path": backup.relative_to(target).as_posix(),
                    "sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
                }
            _record_file(hook)
            if hook_before is not None and hook.read_bytes() == hook_before:
                _note_preexisting(hook)
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
    _assert_safe_destination(path)
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
    previous_hashes = previous.get("file_hashes")
    previous_hashes = previous_hashes if isinstance(previous_hashes, dict) else {}
    previous_backups = previous.get("backups")
    previous_backups = previous_backups if isinstance(previous_backups, dict) else {}
    backups = dict(previous_backups)
    backups.update(_MANIFEST_BACKUPS)
    current_paths = {p.relative_to(target).as_posix() for p in _MANIFEST_FILES}
    current_paths.update(g["file"] for g in _MANIFEST_HOOK_GROUPS)
    tracked_paths = files | {g["file"] for g in groups if isinstance(g, dict) and isinstance(g.get("file"), str)}
    file_hashes: dict[str, str] = {}
    for rel in sorted(tracked_paths):
        if not _rel_inside_target(rel) or not _resolves_inside_target(target, rel):
            continue
        path_on_disk = target / rel
        if rel in current_paths and path_on_disk.is_file():
            file_hashes[rel] = hashlib.sha256(path_on_disk.read_bytes()).hexdigest()
        elif isinstance(previous_hashes.get(rel), str):
            file_hashes[rel] = previous_hashes[rel]
    manifest = {
        "version": 2,
        "host": ",".join(sorted(hosts)),
        "files": sorted(files),
        "preexisting": sorted(preexisting),
        "hook_groups": groups,
        "file_hashes": file_hashes,
        # Presence of this key, even when empty, separates an installer-owned
        # backup from an unrelated adjacent file created by the user later.
        "backups": backups,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_managed_bytes(path, (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))


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


def _path_safety_issue(target: Path, rel: str) -> str | None:
    """Reject managed paths that could write through a symlink or leave target.

    A symlink into the target is also unsafe for ownership: the manifest would
    name one path while writes affect another. Check backup names too, since
    uninstall can move those files into managed destinations.
    """
    if not _rel_inside_target(rel) or not Path(rel).parts:
        return "unsafe relative path"
    for candidate in (rel, str(Path(rel).with_suffix(Path(rel).suffix + ".bak")),
                      str(Path(rel).with_suffix(".pre-quality-loop-backup"))):
        path = target
        try:
            for part in Path(candidate).parts:
                path = path / part
                if path.is_symlink():
                    return f"unsafe symlink at {path.relative_to(target).as_posix()}"
        except OSError:
            return f"unsafe unreadable path {candidate}"
        if not _resolves_inside_target(target, candidate):
            return f"unsafe path outside install target: {candidate}"
    return None


def _assert_safe_destination(dest: Path) -> None:
    if _TARGET is None:
        return
    try:
        rel = dest.relative_to(_TARGET).as_posix()
    except ValueError as exc:
        raise ValueError(f"unsafe destination outside install target: {dest}") from exc
    issue = _path_safety_issue(_TARGET, rel)
    if issue:
        raise ValueError(f"{rel}: {issue}")


def _assert_no_unowned_backup(dest: Path) -> None:
    """Do not take over an adjacent backup on a newly managed path, or use an
    unrelated backup when upgrading a previously identical user file."""
    if _TARGET is None:
        return
    rel = dest.relative_to(_TARGET).as_posix()
    if rel in _MANIFEST_BACKUPS or rel in _PREVIOUS_BACKUPS:
        return
    # Inventory or owned runtime bytes do not imply ownership of a late
    # adjacent backup. Refuse on reinstall before another managed path changes.
    for backup in (dest.with_suffix(dest.suffix + ".bak"),
                   dest.with_suffix(".pre-quality-loop-backup")):
        if backup.exists() or backup.is_symlink():
            raise ValueError(
                f"{rel}: unowned backup collision at {backup.relative_to(_TARGET).as_posix()}; "
                "preserve and reconcile it before installation"
            )


def _backup_candidates(path: Path) -> tuple[Path, Path]:
    return (path.with_suffix(path.suffix + ".bak"),
            path.with_suffix(".pre-quality-loop-backup"))


def _proven_backup(target: Path, rel: str, manifest: dict[str, Any]) -> Path | None:
    """Use only a backup explicitly claimed by a v2 manifest. The conflict
    preflight checks its path and digest before this function is used."""
    backups = manifest.get("backups")
    entry = backups.get(rel) if isinstance(backups, dict) else None
    if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
        return None
    return target / entry["path"]


def _backup_conflicts(target: Path, manifest: dict[str, Any], paths: set[str]) -> list[str]:
    """Legacy v2 did not identify its backups. Never restore an adjacent file
    merely because its name matches; old ambiguous restores need manual review."""
    backups = manifest.get("backups")
    if backups is not None and not isinstance(backups, dict):
        return ["manifest backups field is malformed; preserve and reconcile backups manually"]
    conflicts: list[str] = []
    if isinstance(backups, dict):
        for rel in backups:
            if rel not in paths:
                conflicts.append(f"{rel} (backup provenance names an untracked path)")
    for rel in sorted(paths):
        if not _rel_inside_target(rel):
            continue
        path = target / rel
        entry = backups.get(rel) if isinstance(backups, dict) else None
        if entry is None:
            if backups is None and any(p.exists() or p.is_symlink() for p in _backup_candidates(path)):
                conflicts.append(f"{rel} (legacy v2 backup ownership is ambiguous; preserve and reconcile it manually)")
            continue
        candidates = {p.relative_to(target).as_posix() for p in _backup_candidates(path)}
        backup_rel = entry.get("path") if isinstance(entry, dict) else None
        digest = entry.get("sha256") if isinstance(entry, dict) else None
        if (not isinstance(backup_rel, str) or backup_rel not in candidates
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            conflicts.append(f"{rel} (invalid backup provenance; preserve and reconcile it manually)")
            continue
        issue = _path_safety_issue(target, backup_rel)
        if issue:
            conflicts.append(f"{rel} (unsafe recorded backup: {issue})")
            continue
        backup = target / backup_rel
        if not backup.is_file():
            conflicts.append(f"{rel} (recorded backup is missing; preserve and reconcile it manually)")
        elif hashlib.sha256(backup.read_bytes()).hexdigest() != digest:
            conflicts.append(f"{rel} (recorded backup changed; preserve and reconcile it manually)")
    return conflicts


def _legacy_migration_message() -> str:
    return (
        "Legacy v1 install manifests have no file checksums, so this installer cannot "
        "distinguish a pristine install from later edits or prove backup ownership. "
        "No files changed; automatic migration stopped. Preserve "
        ".quality-loop/install-manifest.json, managed files, hooks, and adjacent backups. "
        "Follow the npm README's legacy reconciliation guidance on a separate project "
        "copy, or use a separate clean target. Do not rename or delete the manifest or "
        "backups, overwrite managed files, or rerun cql init/remove to bypass this refusal. "
        "If ownership is uncertain, stop."
    )


def _managed_file_conflicts(target: Path, manifest: dict[str, Any], *, uninstalling: bool) -> list[str]:
    """Refuse to overwrite or remove files whose post-install bytes changed.

    A changed hook file may contain edits inside a managed group. Without a
    per-group baseline, block the whole uninstall and leave every edit intact.
    """
    hashes = manifest.get("file_hashes")
    hashes = hashes if isinstance(hashes, dict) else {}
    groups = {g["file"] for g in (manifest.get("hook_groups") or [])
              if isinstance(g, dict) and isinstance(g.get("file"), str)}
    preexisting = {f for f in (manifest.get("preexisting") or []) if isinstance(f, str)}
    paths = ({f for f in (manifest.get("files") or []) if isinstance(f, str)}
             | preexisting | groups)
    conflicts = _backup_conflicts(target, manifest, paths)
    for rel in sorted(paths):
        issue = _path_safety_issue(target, rel)
        if issue:
            conflicts.append(f"{rel} ({issue})")
            continue
        path_on_disk = target / rel
        if not path_on_disk.is_file():
            if uninstalling and rel in preexisting and _proven_backup(target, rel, manifest):
                conflicts.append(f"{rel} (managed file missing; preserve its original backup)")
            continue
        if uninstalling:
            if rel in preexisting and rel not in groups and _proven_backup(target, rel, manifest) is None:
                continue
        expected = hashes.get(rel)
        if not isinstance(expected, str) or len(expected) != 64:
            conflicts.append(f"{rel} (legacy manifest has no installed checksum; preserve and compare this file before migration)")
        elif hashlib.sha256(path_on_disk.read_bytes()).hexdigest() != expected:
            detail = "; reconcile even unrelated hook edits before uninstall" if uninstalling and rel in groups else ""
            conflicts.append(f"{rel} (changed since install{detail})")
    return conflicts


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


def _remove_agents_section(path: Path, rel: str, dry_run: bool, backup: Path | None) -> list[str]:
    """Strip the marked managed section from a user AGENTS.md, preferring the
    pre-install backup when one exists."""
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
            "to remove. No files changed. Preserve the current files and any backups, "
            "then reconcile the install inventory and hook wiring manually before removal; "
            "reinstalling cannot recover the original file ownership."
        )
        return 1, report
    try:
        manifest = load_json(manifest_path)
    except (json.JSONDecodeError, OSError) as exc:
        report.append(
            f"Could not parse {MANIFEST_REL} ({exc}). No files changed. Preserve the "
            "manifest and reconcile it manually with the installed files and any backups."
        )
        return 1, report
    if not isinstance(manifest, dict):
        return 1, [f"Could not use {MANIFEST_REL}: expected a JSON object; no files changed."]
    if manifest.get("version") == 1:
        return 1, [_legacy_migration_message()]
    if manifest.get("version") != 2:
        return 1, [f"Unsupported install manifest version {manifest.get('version')!r}; no files changed."]

    conflicts = _managed_file_conflicts(target, manifest, uninstalling=True)
    if conflicts:
        report.append("Uninstall stopped before changing files: managed paths are unsafe or installed files have changed. "
                      "Keep those edits and resolve these conflicts manually:")
        report.extend(conflicts)
        return 1, report

    preexisting = {
        f for f in (manifest.get("preexisting") or []) if isinstance(f, str)
    }
    listed = sorted({
        f for f in (manifest.get("files") or [])
        if isinstance(f, str) and _rel_inside_target(f)
        and (f not in preexisting or _proven_backup(target, f, manifest) is not None)
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
        backup = _proven_backup(target, rel, manifest)
        if rel in preexisting and backup is None:
            report.append(f"left {rel} alone (preexisting file with no installer-owned backup)")
            continue
        if AGENTS_SECTION_KEY in keys:
            report.extend(_remove_agents_section(path, rel, dry_run, backup))
            continue
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
        backup = _proven_backup(target, rel, manifest)
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
    manifest_issue = _path_safety_issue(target, MANIFEST_REL)
    if manifest_issue:
        failure = f"Install stopped before changing files: {MANIFEST_REL}: {manifest_issue}"
        if args.json:
            print(json.dumps({"failures": [failure], "report": [failure]}, indent=2))
        else:
            print(failure)
        return 1
    try:
        raw_manifest = load_json(target / MANIFEST_REL)
        if isinstance(raw_manifest, dict) and raw_manifest.get("version") == 2:
            prior_backups = raw_manifest.get("backups")
            if isinstance(prior_backups, dict):
                _PREVIOUS_BACKUPS.update(prior_backups)
        preexisting = {f for f in (raw_manifest.get("preexisting") or [])
                       if isinstance(f, str)} if isinstance(raw_manifest, dict) else set()
        for f in (raw_manifest.get("files") or []) if isinstance(raw_manifest, dict) else []:
            if isinstance(f, str) and f not in preexisting:
                _OWNED.add(f)
        for group in (raw_manifest.get("hook_groups") or []) if isinstance(raw_manifest, dict) else []:
            if isinstance(group, dict) and isinstance(group.get("file"), str) and group["file"] not in preexisting:
                _OWNED.add(group["file"])
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
    if "git" in selected and (target / ".git").is_file():
        failure = (
            "Git: linked worktrees use a .git file and share hook storage with the main checkout; "
            "this installer cannot safely own or uninstall that shared hook. "
            "No files were installed. Wire a worktree-specific hook manually if needed."
        )
        _FAILURES.append(failure)
    if (target / MANIFEST_REL).is_file():
        try:
            previous_manifest = load_json(target / MANIFEST_REL)
        except (json.JSONDecodeError, OSError) as exc:
            _FAILURES.append(
                f"Install stopped before changing files: cannot read {MANIFEST_REL} ({exc}). "
                "Preserve the existing install and reconcile its manifest manually."
            )
        else:
            if not isinstance(previous_manifest, dict):
                _FAILURES.append(f"Install stopped before changing files: {MANIFEST_REL} must be a JSON object.")
            else:
                if previous_manifest.get("version") == 1:
                    _FAILURES.append(_legacy_migration_message())
                elif previous_manifest.get("version") != 2:
                    _FAILURES.append(
                        f"Install stopped before changing files: unsupported manifest version "
                        f"{previous_manifest.get('version')!r}."
                    )
                if not _FAILURES:
                    conflicts = _managed_file_conflicts(target, previous_manifest, uninstalling=False)
                    if conflicts:
                        _FAILURES.append(
                            "Install stopped before changing files: installed files differ from their "
                            "recorded or bundled baseline. Preserve and reconcile these edits first: "
                            + ", ".join(conflicts)
                        )
    if {"claude-code", "codex", "droid", "pi", "git"} & set(selected):
        missing = [name for name in REQUIRED_RUNTIME_MODULES
                   if not (ROOT / "scripts" / name).is_file()]
        if missing:
            _FAILURES.append(
                "Install stopped before changing files: source runtime is incomplete; "
                "missing scripts/" + ", scripts/".join(missing)
            )
    if _FAILURES:
        if args.json:
            print(json.dumps({"host": args.host, "target": str(target), "dry_run": args.dry_run,
                              "hosts_installed": [], "report": list(_FAILURES),
                              "failures": list(_FAILURES), "manifest": None, "footer": []}, indent=2))
        else:
            for failure in _FAILURES:
                print(failure)
        return 1
    # Run the same host selection in dry-run mode before any writes. This
    # catches unsafe paths already present at preflight; a concurrent target
    # mutation is still outside the supported install/uninstall contract.
    quiet_before = _QUIET
    _QUIET = True
    try:
        if "git" in selected:
            _assert_safe_destination(target / ".git" / "hooks" / "pre-commit")
            _assert_no_unowned_backup(target / ".git" / "hooks" / "pre-commit")
        if {"claude-code", "codex", "droid", "pi", "git"} & set(selected):
            install_runtime(target, True)
        for installer in selected.values():
            installer(target, True)
    except (ValueError, OSError) as exc:
        _FAILURES.append(f"Install stopped before changing files: {exc}")
    finally:
        _QUIET = quiet_before
    if _FAILURES:
        if args.json:
            print(json.dumps({"host": args.host, "target": str(target), "dry_run": args.dry_run,
                              "hosts_installed": [], "report": list(_FAILURES),
                              "failures": list(_FAILURES), "manifest": None, "footer": []}, indent=2))
        else:
            for failure in _FAILURES:
                print(failure)
        return 1
    if args.with_control_plane and not control_plane_available:
        report.append(
            "Control plane: --with-control-plane was requested but quality_loop_control.py is "
            "not in this distribution (the npm tarball excludes it) — clone "
            "https://github.com/zaingz/coding-quality-loop and run scripts/install.py from the repo"
        )
    try:
        if {"claude-code", "codex", "droid", "pi", "git"} & set(selected):
            report.extend(install_runtime(target, args.dry_run))
        for installer in selected.values():
            report.extend(installer(target, args.dry_run))
        write_manifest(target, sorted(selected.keys()), args.dry_run)
    except (ValueError, OSError) as exc:
        failure = (f"Install stopped during file writes: {exc}. The target may have changed "
                   "concurrently; inspect any partial files and the unchanged manifest before retrying.")
        if args.json:
            print(json.dumps({"host": args.host, "target": str(target), "dry_run": args.dry_run,
                              "hosts_installed": [], "report": [failure], "failures": [failure],
                              "manifest": None, "footer": []}, indent=2))
        else:
            print(failure)
        return 1
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
