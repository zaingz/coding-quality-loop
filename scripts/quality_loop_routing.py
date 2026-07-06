#!/usr/bin/env python3
"""Config-based model routing for the Coding Quality Loop.

Reads a ``model_routing`` section from the orchestration config and applies it
to host-native agent files (Claude Code ``.claude/agents/*.md``, Droid
``.factory/droids/*.md``) or prints the settings to apply (Codex ``config.toml``,
Pi ``/model`` commands).  Stdlib-only, no runtime dependencies.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

SUPPORTED_HOSTS = ("claude-code", "droid", "codex", "pi")
MODEL_CLASSES = ("cheap_fast", "strong_reasoning", "code_specialized")
THINKING_VALUES = ("minimal", "low", "medium", "high", "xhigh", "max")

# Reasoning effort is per-step, not per-task endurance. xhigh/max don't let a model
# work longer -- they make it overthink and overspend on every single step, and they
# make reviews noisier. `high` is the ceiling for routine routing; reserve xhigh/max
# for a genuinely ambiguous, architecture-sensitive one-off by setting
# "allow_overthink": true on that specific model_class block.
ROUTINE_EFFORT_CEILING = "high"
OVERTHINK_LEVELS = ("xhigh", "max")

HOSTS: dict[str, dict[str, Any]] = {
    "claude-code": {
        "kind": "files",
        "agent_dir": ".claude/agents",
        "thinking_key": "effort",
        "supported_thinking": {"low", "medium", "high", "xhigh", "max"},
    },
    "droid": {
        "kind": "files",
        "agent_dir": ".factory/droids",
        "thinking_key": "reasoningEffort",
        "supported_thinking": {"low", "medium", "high"},
    },
    "codex": {
        "kind": "print",
        "agent_dir": None,
        "thinking_key": None,
        "supported_thinking": {"minimal", "low", "medium", "high", "xhigh"},
    },
    "pi": {
        "kind": "print",
        "agent_dir": None,
        "thinking_key": None,
        "supported_thinking": {"minimal", "low", "medium", "high", "xhigh"},
    },
}

DEFAULT_AGENTS = {
    "quality-loop-context-mapper": "cheap_fast",
    "quality-loop-planner": "strong_reasoning",
    "quality-loop-reviewer": "strong_reasoning",
    "quality-loop-security-reviewer": "strong_reasoning",
}

AGENT_ROLE_NOTES = {
    "quality-loop-context-mapper": "EXPLORE context mapper",
    "quality-loop-planner": "MINIMALITY_GATE + PLAN",
    "quality-loop-reviewer": "REVIEW (fresh session)",
    "quality-loop-security-reviewer": "Security review at risk boundaries (fresh session)",
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_model_routing(section: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(section, dict):
        return ["model_routing must be an object"]
    host = section.get("host")
    if host is not None and host not in SUPPORTED_HOSTS:
        errors.append(
            f"model_routing.host must be one of {list(SUPPORTED_HOSTS)} or null, got {host!r}"
        )
    host_models = section.get("host_models", {})
    if not isinstance(host_models, dict):
        errors.append("model_routing.host_models must be an object")
    else:
        for hname, hblock in host_models.items():
            if hname not in SUPPORTED_HOSTS:
                errors.append(f"model_routing.host_models has unknown host: {hname!r}")
                continue
            if not isinstance(hblock, dict):
                errors.append(f"model_routing.host_models.{hname} must be an object")
                continue
            for cname, cblock in hblock.items():
                if cname not in MODEL_CLASSES:
                    errors.append(
                        f"model_routing.host_models.{hname} has unknown model_class: {cname!r}"
                    )
                    continue
                if not isinstance(cblock, dict):
                    errors.append(
                        f"model_routing.host_models.{hname}.{cname} must be an object"
                    )
                    continue
                model = cblock.get("model")
                if model is not None and not isinstance(model, str):
                    errors.append(
                        f"model_routing.host_models.{hname}.{cname}.model must be a string or null"
                    )
                thinking = cblock.get("thinking")
                if thinking is not None and thinking not in THINKING_VALUES:
                    errors.append(
                        f"model_routing.host_models.{hname}.{cname}.thinking must be one of "
                        f"{list(THINKING_VALUES)} or null, got {thinking!r}"
                    )
                allow_overthink = cblock.get("allow_overthink")
                if allow_overthink is not None and not isinstance(allow_overthink, bool):
                    errors.append(
                        f"model_routing.host_models.{hname}.{cname}.allow_overthink must be a boolean"
                    )
                if thinking in OVERTHINK_LEVELS and allow_overthink is not True:
                    errors.append(
                        f"model_routing.host_models.{hname}.{cname}.thinking={thinking!r} exceeds the "
                        f"'{ROUTINE_EFFORT_CEILING}' effort ceiling. Reasoning effort is per-step, not "
                        f"per-task endurance: xhigh/max overthink and overspend on every step and make "
                        f"reviews noisier without solving harder problems. Route at '{ROUTINE_EFFORT_CEILING}', "
                        f"or set \"allow_overthink\": true on this block for a genuinely ambiguous, "
                        f"architecture-sensitive case."
                    )
    agents = section.get("agents", {})
    if not isinstance(agents, dict):
        errors.append("model_routing.agents must be an object")
    else:
        for aname, aclass in agents.items():
            if aclass not in MODEL_CLASSES:
                errors.append(
                    f"model_routing.agents.{aname} references unknown model_class: {aclass!r}"
                )
    if (
        host is not None
        and isinstance(host_models, dict)
        and host in host_models
        and isinstance(agents, dict)
    ):
        for aname, aclass in agents.items():
            if isinstance(host_models[host], dict) and aclass not in host_models[host]:
                errors.append(
                    f"model_routing.agents.{aname} -> {aclass!r} is not defined in host_models.{host}"
                )
    return errors


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def resolve_routing(
    config: dict[str, Any], host_override: str | None = None
) -> tuple[str | None, dict[str, dict[str, Any]], dict[str, str]]:
    section = config.get("model_routing", {})
    if not isinstance(section, dict):
        return None, {}, {}
    host = host_override or section.get("host")
    if host is None:
        return None, {}, {}
    host_models = section.get("host_models", {})
    class_settings = host_models.get(host, {}) if isinstance(host_models, dict) else {}
    agents = section.get("agents", DEFAULT_AGENTS)
    if not isinstance(agents, dict):
        agents = dict(DEFAULT_AGENTS)
    return host, dict(class_settings), dict(agents)


def _find_config(cwd: Path) -> Path | None:
    candidate = cwd / "quality-loop.config.json"
    return candidate if candidate.is_file() else None


# ---------------------------------------------------------------------------
# Frontmatter editing (line-based, no YAML dependency)
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> tuple[int, int] | None:
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return (1, i)
    return None


def frontmatter_field(text: str, key: str) -> str | None:
    bounds = _parse_frontmatter(text)
    if bounds is None:
        return None
    start, end = bounds
    for line in text.split("\n")[start:end]:
        s = line.strip()
        if ":" in s:
            k = s.split(":", 1)[0].strip()
            if k == key:
                return s.split(":", 1)[1].strip()
    return None


def rewrite_frontmatter(
    text: str, model: str, thinking: str | None, thinking_key: str | None
) -> str:
    bounds = _parse_frontmatter(text)
    if bounds is None:
        return text
    start, end = bounds
    lines = text.split("\n")
    fm = lines[start:end]
    model_idx = None
    think_idx = None
    for i, line in enumerate(fm):
        s = line.strip()
        if ":" in s:
            k = s.split(":", 1)[0].strip()
            if k == "model":
                model_idx = i
            elif thinking_key and k == thinking_key:
                think_idx = i
    if model_idx is not None:
        fm[model_idx] = f"model: {model}"
    else:
        fm.append(f"model: {model}")
    if thinking and thinking_key:
        new_line = f"{thinking_key}: {thinking}"
        if think_idx is not None:
            fm[think_idx] = new_line
        else:
            fm.append(new_line)
    elif think_idx is not None:
        del fm[think_idx]
    new_lines = lines[:start] + fm + lines[end:]
    return "\n".join(new_lines)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", delete=False, dir=path.parent, encoding="utf-8"
    ) as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


# ---------------------------------------------------------------------------
# Setup command
# ---------------------------------------------------------------------------

def _thinking_warnings(host: str, class_settings: dict[str, dict[str, Any]]) -> list[str]:
    supported = HOSTS[host]["supported_thinking"]
    warnings: list[str] = []
    for cname, cblock in class_settings.items():
        thinking = cblock.get("thinking") if isinstance(cblock, dict) else None
        allow_overthink = cblock.get("allow_overthink") if isinstance(cblock, dict) else None
        if thinking and thinking not in supported:
            warnings.append(
                f"thinking {thinking!r} for {cname} is not supported by {host} "
                f"(supports: {sorted(supported)}); omitting it"
            )
        if thinking in OVERTHINK_LEVELS and allow_overthink is not True:
            warnings.append(
                f"thinking {thinking!r} for {cname} exceeds the '{ROUTINE_EFFORT_CEILING}' ceiling; "
                f"xhigh/max overthink and overspend per step. Route at '{ROUTINE_EFFORT_CEILING}' or set "
                f"\"allow_overthink\": true on this block. (run check-config to enforce)"
            )
    return warnings


def _setup_files_host(
    host: str,
    class_settings: dict[str, dict[str, Any]],
    agents: dict[str, str],
    target: Path,
    dry_run: bool,
    json_out: bool,
) -> int:
    spec = HOSTS[host]
    agent_dir = target / spec["agent_dir"]
    thinking_key = spec["thinking_key"]
    warnings = _thinking_warnings(host, class_settings)
    if not agent_dir.is_dir():
        print(f"error: agent directory not found: {agent_dir}", file=sys.stderr)
        if host == "droid":
            print(
                "hint: run `python3 scripts/install.py --host droid` to copy the example droids first",
                file=sys.stderr,
            )
        return 2
    results: list[dict[str, Any]] = []
    changed_count = 0
    for aname, aclass in agents.items():
        cblock = class_settings.get(aclass)
        if not isinstance(cblock, dict):
            results.append(
                {"agent": aname, "status": "skipped", "reason": f"class {aclass!r} not in host_models"}
            )
            continue
        model = cblock.get("model")
        thinking = cblock.get("thinking")
        if thinking and thinking not in spec["supported_thinking"]:
            thinking = None
        if not model or not isinstance(model, str):
            results.append(
                {"agent": aname, "status": "skipped", "reason": "model is null/empty -- fill in host_models"}
            )
            continue
        path = agent_dir / f"{aname}.md"
        if not path.is_file():
            results.append({"agent": aname, "status": "missing", "path": str(path)})
            continue
        old = path.read_text(encoding="utf-8")
        old_model = frontmatter_field(old, "model")
        new = rewrite_frontmatter(old, model, thinking, thinking_key)
        changed = new != old
        if changed and not dry_run:
            _atomic_write(path, new)
        if changed:
            changed_count += 1
        results.append(
            {
                "agent": aname,
                "status": "changed" if changed else "unchanged",
                "model": model,
                "old_model": old_model,
                "thinking": thinking,
            }
        )
    if json_out:
        print(
            json.dumps(
                {"host": host, "changed": changed_count, "results": results, "warnings": warnings},
                indent=2,
            )
        )
    else:
        prefix = "[dry-run] " if dry_run else ""
        print(f"{prefix}setup-models for {host} (target: {target})")
        for r in results:
            if r["status"] == "changed":
                extra = f"  thinking={r['thinking']}" if r.get("thinking") else ""
                print(f"  {r['agent']}: model {r.get('old_model', '?')} -> {r['model']}{extra}")
            elif r["status"] == "unchanged":
                print(f"  {r['agent']}: unchanged (model={r['model']})")
            elif r["status"] == "skipped":
                print(f"  {r['agent']}: skipped ({r['reason']})")
            elif r["status"] == "missing":
                print(f"  {r['agent']}: MISSING ({r['path']})")
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)
        verb = "would change" if dry_run else "updated"
        unchanged = len([r for r in results if r["status"] == "unchanged"])
        print(f"\n{changed_count} agent file(s) {verb}; {unchanged} unchanged")
    return 1 if warnings else 0


def _render_codex(
    class_settings: dict[str, dict[str, Any]], agents: dict[str, str]
) -> str:
    supported = HOSTS["codex"]["supported_thinking"]
    main = class_settings.get("code_specialized", {})
    main_model = main.get("model") or "<code-specialized-model>"
    main_thinking = main.get("thinking")
    lines = [
        "# Codex model routing -- add to ~/.codex/config.toml",
        "# (or a trusted project .codex/config.toml).",
        "# Main session (implementer) uses the code_specialized model:",
        f'model = "{main_model}"',
    ]
    if main_thinking and main_thinking in supported:
        lines.append(f'model_reasoning_effort = "{main_thinking}"')
    lines.append("")
    lines.append("# Per-role subagent routing:")
    layers: list[tuple[str, str, str | None]] = []
    for aname, aclass in agents.items():
        cblock = class_settings.get(aclass, {})
        if not isinstance(cblock, dict):
            cblock = {}
        model = cblock.get("model") or f"<{aclass}-model>"
        thinking = cblock.get("thinking")
        if thinking and thinking not in supported:
            thinking = None
        note = AGENT_ROLE_NOTES.get(aname, aclass)
        layer_path = f".codex/{aname}.toml"
        lines.append(f"[agents.{aname}]")
        lines.append(f'description = "{note} ({aclass})"')
        lines.append(f'config_file = "{layer_path}"')
        lines.append("")
        layers.append((layer_path, model, thinking))
    lines.append("# --- Per-role config_file layer contents (create each file) ---")
    for layer_path, model, thinking in layers:
        lines.append("")
        lines.append(f"# === {layer_path} ===")
        lines.append(f'model = "{model}"')
        if thinking:
            lines.append(f'model_reasoning_effort = "{thinking}"')
    return "\n".join(lines)


def _render_pi(
    class_settings: dict[str, dict[str, Any]], agents: dict[str, str]
) -> str:
    supported = HOSTS["pi"]["supported_thinking"]
    lines = [
        "# Pi model routing -- apply in your Pi session before each role.",
        "# The implementer is the main session; reviewers run in a fresh session.",
        "",
    ]
    main = class_settings.get("code_specialized", {})
    main_model = main.get("model") or "<code-specialized-model>"
    lines.append("# Main session (implementer, code_specialized):")
    lines.append(f"/model {main_model}")
    if main.get("thinking") and main.get("thinking") in supported:
        lines.append(f"# thinking: {main['thinking']}")
    lines.append("")
    for aname, aclass in agents.items():
        cblock = class_settings.get(aclass, {})
        if not isinstance(cblock, dict):
            cblock = {}
        model = cblock.get("model") or f"<{aclass}-model>"
        thinking = cblock.get("thinking")
        if thinking and thinking not in supported:
            thinking = None
        note = AGENT_ROLE_NOTES.get(aname, aclass)
        lines.append(f"# {aname} -- {note} ({aclass})")
        lines.append(f"/model {model}")
        if thinking:
            lines.append(f"# thinking: {thinking}")
        if "fresh session" in note.lower():
            lines.append(
                "# Start a new Pi session for this role (no shared context with the implementer)."
            )
        lines.append("")
    return "\n".join(lines)


def _setup_print_host(
    host: str,
    class_settings: dict[str, dict[str, Any]],
    agents: dict[str, str],
    target: Path,
    dry_run: bool,
    json_out: bool,
) -> int:
    warnings = _thinking_warnings(host, class_settings)
    text = _render_codex(class_settings, agents) if host == "codex" else _render_pi(class_settings, agents)
    if json_out:
        print(json.dumps({"host": host, "output": text, "warnings": warnings}, indent=2))
    else:
        if dry_run:
            print("[dry-run] setup-models for {} (print-only host, no files written)".format(host))
        print(text)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    return 1 if warnings else 0


def cmd_setup_models(args: Any) -> int:
    target = Path(getattr(args, "target", ".")).resolve()
    config_path = Path(args.config) if getattr(args, "config", None) else _find_config(target)
    if config_path is None or not config_path.is_file():
        print(
            "error: config not found. Copy assets/quality-loop.config.example.json to "
            "quality-loop.config.json at your repo root and fill model_routing.",
            file=sys.stderr,
        )
        return 2
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"error: could not read config {config_path}: {exc}", file=sys.stderr)
        return 2
    host, class_settings, agents = resolve_routing(config, getattr(args, "host", None))
    if host is None:
        print(
            "error: no host selected. Set model_routing.host in the config or pass --host.",
            file=sys.stderr,
        )
        return 2
    if host not in HOSTS:
        print(f"error: unsupported host {host!r}", file=sys.stderr)
        return 2
    if HOSTS[host]["kind"] == "files":
        return _setup_files_host(
            host, class_settings, agents, target, args.dry_run, args.json
        )
    return _setup_print_host(
        host, class_settings, agents, target, args.dry_run, args.json
    )


# ---------------------------------------------------------------------------
# Brief integration
# ---------------------------------------------------------------------------

def brief_routing_lines(cwd: Path, config_path: Path | None = None) -> list[str]:
    info = brief_routing_info(cwd, config_path)
    return info["lines"]


def brief_routing_info(cwd: Path, config_path: Path | None = None) -> dict[str, Any]:
    if config_path is None:
        config_path = _find_config(cwd)
    if config_path is None or not config_path.is_file():
        return {
            "configured": False,
            "lines": [
                "Model routing: not configured",
                "  Copy assets/quality-loop.config.example.json to quality-loop.config.json,",
                "  set model_routing, and run: python3 scripts/quality_loop.py setup-models",
            ],
        }
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {
            "configured": False,
            "lines": ["Model routing: config unreadable (" + str(config_path) + ")"],
        }
    host, class_settings, agents = resolve_routing(config, None)
    if not host:
        return {
            "configured": False,
            "host": None,
            "lines": [
                "Model routing: host not set in config",
                "  Set model_routing.host and run: python3 scripts/quality_loop.py setup-models",
            ],
        }
    lines = [f"Model routing: host={host}"]
    classes: dict[str, Any] = {}
    for cname in MODEL_CLASSES:
        cblock = class_settings.get(cname, {})
        if not isinstance(cblock, dict):
            cblock = {}
        model = cblock.get("model") or "(not set)"
        thinking = cblock.get("thinking")
        t = f" thinking={thinking}" if thinking else ""
        lines.append(f"  {cname}: model={model}{t}")
        classes[cname] = {"model": model, "thinking": thinking}
    drift: list[str] = []
    spec = HOSTS.get(host, {})
    if spec.get("kind") == "files":
        agent_dir = cwd / spec["agent_dir"]
        for aname, aclass in agents.items():
            cblock = class_settings.get(aclass, {})
            if not isinstance(cblock, dict):
                continue
            expected = cblock.get("model")
            if not expected or not isinstance(expected, str):
                continue
            path = agent_dir / f"{aname}.md"
            if not path.is_file():
                continue
            actual = frontmatter_field(path.read_text(encoding="utf-8"), "model")
            if actual is not None and actual != expected:
                drift.append(
                    f"drift: {aname} model={actual}, config says {expected} (run setup-models)"
                )
    if drift:
        lines.append("  " + "\n  ".join(drift))
    return {
        "configured": True,
        "host": host,
        "classes": classes,
        "drift": drift,
        "lines": lines,
    }
