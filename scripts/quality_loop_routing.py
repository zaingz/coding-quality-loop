#!/usr/bin/env python3
"""Config-based model routing for the Coding Quality Loop.

Reads a ``model_routing`` section from the orchestration config and applies it
to host-native agent files (Claude Code ``.claude/agents/*.md``, Droid
``.factory/droids/*.md``) or prints the settings to apply (Codex ``config.toml``,
Pi ``/model`` commands).  Stdlib-only, no runtime dependencies.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import quality_loop_core as qlcore

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

# Reviewer heterogeneity is enforced on the model FAMILY, not the CLI (harness
# diversity does not guarantee model heterogeneity). Family is best-effort: an
# explicit "family" field on a host_models class block always wins; otherwise
# the model id is tokenized and matched against this table. A miss or an
# ambiguous match degrades to None and callers SKIP the check -- unknown ids
# (BYOK custom:<id>, proxies) must never false-positive.
WELL_KNOWN_FAMILIES = {
    "claude": "claude",
    "sonnet": "claude",
    "opus": "claude",
    "haiku": "claude",
    "fable": "claude",
    "gpt": "gpt",
    "codex": "gpt",
    "sol": "gpt",
    "terra": "gpt",
    "luna": "gpt",
    "glm": "glm",
    "gemini": "gemini",
    "grok": "grok",
}

PRINT_ONLY_BANNER = (
    "PRINT-ONLY -- settings not applied or verified by CQL; "
    "heterogeneity for this leg is config-declared, not observed"
)


def is_placeholder_model(model: Any) -> bool:
    """True for model identifiers that are not real concrete models.

    Used by reviewer-heterogeneity and family checks so an unfilled config
    (null / inherit / angle-bracket placeholders like ``<strong-reasoning-model>``)
    does not false-positive before the user supplies real model ids.
    """
    if not isinstance(model, str):
        return True  # null / None / unset
    s = model.strip()
    if not s or s == "inherit":
        return True
    if s.startswith("<") and s.endswith(">"):
        return True
    return False


def model_family(model: Any, declared: Any = None) -> str | None:
    """Best-effort model family for heterogeneity checks.

    An explicit declared family wins. Otherwise the id is lowercased, split on
    non-alphanumerics, and token-matched against WELL_KNOWN_FAMILIES so aliases
    (``sonnet``) and channel ids (``anthropic/claude-sonnet-5``) meet in the
    same family. Placeholder, unknown, or ambiguous (tokens matching more than
    one family) ids return None -- callers must skip, never fail.
    """
    if isinstance(declared, str) and declared.strip():
        return declared.strip().lower()
    if is_placeholder_model(model):
        return None
    tokens = re.split(r"[^a-z0-9]+", model.strip().lower())
    families = {WELL_KNOWN_FAMILIES[t] for t in tokens if t in WELL_KNOWN_FAMILIES}
    if len(families) == 1:
        return families.pop()
    return None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _agent_entry(value: Any) -> dict[str, Any] | None:
    """Normalize an agents-map value to ``{"host": str|None, "class": str}``.

    v4.1 shape (plain model_class string) and the multi-host object form
    (``{"host": ..., "class": ...}``) are both valid; anything else is None.
    """
    if isinstance(value, str):
        return {"host": None, "class": value}
    if isinstance(value, dict):
        cls = value.get("class")
        host = value.get("host")
        if not isinstance(cls, str):
            return None
        if host is not None and not isinstance(host, str):
            return None
        return {"host": host, "class": cls}
    return None


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
                qlcore.require_str_or_null(
                    errors, cblock.get("model"),
                    f"model_routing.host_models.{hname}.{cname}.model",
                )
                thinking = cblock.get("thinking")
                if thinking is not None and thinking not in THINKING_VALUES:
                    errors.append(
                        f"model_routing.host_models.{hname}.{cname}.thinking must be one of "
                        f"{list(THINKING_VALUES)} or null, got {thinking!r}"
                    )
                allow_overthink = cblock.get("allow_overthink")
                qlcore.require_bool_or_null(
                    errors, allow_overthink,
                    f"model_routing.host_models.{hname}.{cname}.allow_overthink",
                )
                qlcore.require_str_or_null(
                    errors, cblock.get("family"),
                    f"model_routing.host_models.{hname}.{cname}.family",
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
        for aname, aval in agents.items():
            entry = _agent_entry(aval)
            if entry is None:
                errors.append(
                    f"model_routing.agents.{aname} must be a model_class string or an "
                    f"object {{host, class}}, got {aval!r}"
                )
                continue
            if entry["class"] not in MODEL_CLASSES:
                errors.append(
                    f"model_routing.agents.{aname} references unknown model_class: "
                    f"{entry['class']!r}"
                )
            if entry["host"] is not None and entry["host"] not in SUPPORTED_HOSTS:
                errors.append(
                    f"model_routing.agents.{aname}.host must be one of "
                    f"{list(SUPPORTED_HOSTS)}, got {entry['host']!r}"
                )
    main_session = section.get("main_session")
    if main_session is not None:
        if not isinstance(main_session, dict):
            errors.append("model_routing.main_session must be an object")
        else:
            ms_host = main_session.get("host")
            if ms_host is not None and ms_host not in SUPPORTED_HOSTS:
                errors.append(
                    f"model_routing.main_session.host must be one of "
                    f"{list(SUPPORTED_HOSTS)}, got {ms_host!r}"
                )
            ms_class = main_session.get("class")
            if ms_class is not None and ms_class not in MODEL_CLASSES:
                errors.append(
                    f"model_routing.main_session.class must be one of "
                    f"{list(MODEL_CLASSES)}, got {ms_class!r}"
                )
            qlcore.require_str_or_null(
                errors, main_session.get("model"), "model_routing.main_session.model"
            )
            if main_session.get("host") is None and host is None:
                errors.append(
                    "model_routing.main_session needs a host: set main_session.host or "
                    "model_routing.host -- a hostless main_session cannot be resolved and "
                    "would silently skip the reviewer-heterogeneity check"
                )
    qlcore.require_bool_or_null(
        errors, section.get("allow_same_family"), "model_routing.allow_same_family"
    )
    if isinstance(host_models, dict) and isinstance(agents, dict):
        for aname, aval in agents.items():
            entry = _agent_entry(aval)
            if entry is None:
                continue
            if entry["host"] is not None and entry["host"] not in host_models:
                # An explicit pin to a host with no host_models block is a config
                # mistake, not an unfilled default: the role would resolve to
                # nothing and heterogeneity would silently skip.
                errors.append(
                    f"model_routing.agents.{aname} is pinned to host {entry['host']!r} "
                    f"but host_models.{entry['host']} is not defined"
                )
                continue
            ahost = entry["host"] or host
            if ahost is None or ahost not in host_models:
                continue
            if isinstance(host_models[ahost], dict) and entry["class"] not in host_models[ahost]:
                errors.append(
                    f"model_routing.agents.{aname} -> {entry['class']!r} is not defined "
                    f"in host_models.{ahost}"
                )
    return errors


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def resolve_routing(
    config: dict[str, Any], host_override: str | None = None
) -> dict[str, Any]:
    """Resolve the model_routing section into a topology.

    Returns a dict with:
      - ``default_host``: ``host_override`` or ``model_routing.host`` (may be None).
      - ``host_models``: the full per-host class-settings map.
      - ``agents``: agent name -> ``{"host": resolved_host, "class": model_class}``.
        v4.1 string entries resolve to the default host, so ``--host X`` keeps its
        historical meaning (retarget the default) while object entries stay pinned.
      - ``main_session``: ``{"host", "class", "model"}`` or None -- a declaration of
        where the implementer runs; nothing is ever rewritten for it.
      - ``allow_same_family``: bool escape hatch for the family heterogeneity check.
      - ``hosts_in_use``: hosts (SUPPORTED_HOSTS order) with at least one resolved
        agent or the main session.
    """
    empty = {
        "default_host": None,
        "host_models": {},
        "agents": {},
        "main_session": None,
        "allow_same_family": False,
        "hosts_in_use": [],
    }
    section = config.get("model_routing", {})
    if not isinstance(section, dict):
        return empty
    # --host semantics split by config shape: a v4.1 single-host config keeps the
    # historical meaning (retarget the default host, so the same config can be
    # applied to another host); a multi-host topology (object agents or a
    # main_session) treats --host as a pure FILTER -- overriding the default
    # there would silently drag default-host roles onto the selected host.
    raw_agents_probe = section.get("agents")
    uses_topology = isinstance(section.get("main_session"), dict) or (
        isinstance(raw_agents_probe, dict)
        and any(isinstance(v, dict) for v in raw_agents_probe.values())
    )
    if uses_topology:
        default_host = section.get("host")
    else:
        default_host = host_override or section.get("host")
    host_models = section.get("host_models", {})
    if not isinstance(host_models, dict):
        host_models = {}
    raw_agents = section.get("agents", DEFAULT_AGENTS)
    if not isinstance(raw_agents, dict):
        raw_agents = dict(DEFAULT_AGENTS)
    agents: dict[str, dict[str, Any]] = {}
    for aname, aval in raw_agents.items():
        entry = _agent_entry(aval)
        if entry is None:
            continue
        agents[aname] = {"host": entry["host"] or default_host, "class": entry["class"]}
    main_session = section.get("main_session")
    if isinstance(main_session, dict):
        main_session = {
            "host": main_session.get("host") or default_host,
            "class": main_session.get("class"),
            "model": main_session.get("model"),
        }
        if main_session["host"] is None:
            main_session = None
    else:
        main_session = None
    used = {e["host"] for e in agents.values() if e["host"]}
    if main_session:
        used.add(main_session["host"])
    if default_host:
        # A configured default host is in use even with zero resolved agents
        # (v4.1 allowed agents: {}): setup-models reports "nothing to rewrite"
        # and brief shows its classes instead of claiming "not configured".
        used.add(default_host)
    return {
        "default_host": default_host,
        "host_models": host_models,
        "agents": agents,
        "main_session": main_session,
        "allow_same_family": section.get("allow_same_family") is True,
        "hosts_in_use": [h for h in SUPPORTED_HOSTS if h in used],
    }


def class_block(
    host_models: dict[str, Any], host: str | None, cname: str | None
) -> dict[str, Any]:
    """The ``host_models[host][cname]`` block, or ``{}`` when unresolvable."""
    if not host or not cname or not isinstance(host_models, dict):
        return {}
    hblock = host_models.get(host)
    if not isinstance(hblock, dict):
        return {}
    cblock = hblock.get(cname)
    return cblock if isinstance(cblock, dict) else {}


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


# The atomic write lives in quality_loop_core (one implementation for the
# package); this preserves the module-local name for existing call sites.
_atomic_write = qlcore.atomic_write_text


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
    main_session: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    spec = HOSTS[host]
    agent_dir = target / spec["agent_dir"]
    thinking_key = spec["thinking_key"]
    warnings = _thinking_warnings(host, class_settings)
    if not agents:
        note = f"no agent files assigned to {host}; nothing to rewrite"
        if main_session and main_session.get("host") == host:
            cls = main_session.get("class") or "code_specialized"
            cblock = class_settings.get(cls, {})
            if not isinstance(cblock, dict):
                cblock = {}
            model = main_session.get("model") or cblock.get("model") or f"<{cls}-model>"
            note += (
                f"; main session (implementer) declared here: model={model} -- "
                f"apply it in the {host} session (see docs/cross-cli-recipe.md)"
            )
        if not json_out:
            print(f"setup-models for {host} (target: {target})")
            print(f"  {note}")
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)
        return (1 if warnings else 0), {
            "host": host, "changed": 0, "results": [], "note": note, "warnings": warnings,
        }
    if not agent_dir.is_dir():
        print(f"error: agent directory not found: {agent_dir}", file=sys.stderr)
        if host == "droid":
            print(
                "hint: run `python3 scripts/install.py --host droid` to copy the example droids first",
                file=sys.stderr,
            )
        return 2, {"host": host, "error": f"agent directory not found: {agent_dir}"}
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
    payload = {"host": host, "changed": changed_count, "results": results, "warnings": warnings}
    if not json_out:
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
    return (1 if warnings else 0), payload


def _render_codex(
    class_settings: dict[str, dict[str, Any]],
    agents: dict[str, str],
    main: dict[str, Any],
) -> str:
    supported = HOSTS["codex"]["supported_thinking"]
    lines = [
        "# Codex model routing -- add to ~/.codex/config.toml",
        "# (or a trusted project .codex/config.toml).",
    ]
    if main.get("elsewhere"):
        lines.append(
            f"# Main session (implementer) runs on host {main['elsewhere']!r} -- "
            f"see that host's section."
        )
    else:
        main_model = main.get("model") or "<code-specialized-model>"
        main_thinking = main.get("thinking")
        lines.append("# Main session (implementer):")
        lines.append(f'model = "{main_model}"')
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
    class_settings: dict[str, dict[str, Any]],
    agents: dict[str, str],
    main: dict[str, Any],
) -> str:
    supported = HOSTS["pi"]["supported_thinking"]
    lines = [
        "# Pi model routing -- apply in your Pi session before each role.",
        "# The implementer is the main session; reviewers run in a fresh session.",
        "",
    ]
    if main.get("elsewhere"):
        lines.append(
            f"# Main session (implementer) runs on host {main['elsewhere']!r} -- "
            f"see that host's section."
        )
    else:
        main_model = main.get("model") or "<code-specialized-model>"
        lines.append("# Main session (implementer):")
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
    main_session: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    warnings = _thinking_warnings(host, class_settings)
    if main_session and main_session.get("host") == host:
        cls = main_session.get("class") or "code_specialized"
        cblock = class_settings.get(cls, {})
        if not isinstance(cblock, dict):
            cblock = {}
        main = {
            "model": main_session.get("model") or cblock.get("model") or f"<{cls}-model>",
            "thinking": cblock.get("thinking"),
        }
    elif main_session:
        main = {"elsewhere": main_session.get("host")}
    else:
        cblock = class_settings.get("code_specialized", {})
        if not isinstance(cblock, dict):
            cblock = {}
        main = {"model": cblock.get("model"), "thinking": cblock.get("thinking")}
    render = _render_codex if host == "codex" else _render_pi
    text = f"# {host}: {PRINT_ONLY_BANNER}\n" + render(class_settings, agents, main)
    payload = {"host": host, "output": text, "warnings": warnings}
    if not json_out:
        if dry_run:
            print("[dry-run] setup-models for {} (print-only host, no files written)".format(host))
        print(text)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    return (1 if warnings else 0), payload


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
    host_filter = getattr(args, "host", None)
    topo = resolve_routing(config, host_filter)
    hosts = list(topo["hosts_in_use"])
    if host_filter:
        if host_filter not in HOSTS:
            print(f"error: unsupported host {host_filter!r}", file=sys.stderr)
            return 2
        hosts = [host_filter]
    if not hosts:
        print(
            "error: no host selected. Set model_routing.host, give agents a host, "
            "or pass --host.",
            file=sys.stderr,
        )
        return 2
    for h in hosts:
        if h not in HOSTS:
            print(f"error: unsupported host {h!r}", file=sys.stderr)
            return 2
    overall = 0
    payloads: list[dict[str, Any]] = []
    host_models = topo["host_models"]
    for idx, h in enumerate(hosts):
        if idx and not args.json:
            print()
        agents_for_host = {
            name: entry["class"]
            for name, entry in topo["agents"].items()
            if entry["host"] == h
        }
        class_settings = host_models.get(h, {})
        if not isinstance(class_settings, dict):
            class_settings = {}
        if HOSTS[h]["kind"] == "files":
            rc, payload = _setup_files_host(
                h, class_settings, agents_for_host, target, args.dry_run, args.json,
                main_session=topo["main_session"],
            )
        else:
            rc, payload = _setup_print_host(
                h, class_settings, agents_for_host, target, args.dry_run, args.json,
                main_session=topo["main_session"],
            )
        overall = max(overall, rc)
        payloads.append(payload)
    if args.json:
        out = payloads[0] if len(payloads) == 1 else {"hosts": payloads}
        print(json.dumps(out, indent=2))
    return overall


# ---------------------------------------------------------------------------
# Brief integration
# ---------------------------------------------------------------------------

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
    topo = resolve_routing(config, None)
    hosts = list(topo["hosts_in_use"])
    default_host = topo["default_host"]
    if not hosts:
        return {
            "configured": False,
            "host": None,
            "lines": [
                "Model routing: host not set in config",
                "  Set model_routing.host and run: python3 scripts/quality_loop.py setup-models",
            ],
        }
    host_models = topo["host_models"]
    multi = len(hosts) > 1
    if multi:
        parts = [h + " (default)" if h == default_host else h for h in hosts]
        lines = ["Model routing: hosts=" + ", ".join(parts)]
    else:
        lines = [f"Model routing: host={hosts[0]}"]
    classes: dict[str, Any] = {}
    for h in hosts:
        class_settings = host_models.get(h, {})
        if not isinstance(class_settings, dict):
            class_settings = {}
        if multi:
            used = {e["class"] for e in topo["agents"].values() if e["host"] == h}
            ms = topo["main_session"]
            if ms and ms.get("host") == h and ms.get("class"):
                used.add(ms["class"])
            shown = [c for c in MODEL_CLASSES if c in used] or list(MODEL_CLASSES)
            suffix = "" if HOSTS.get(h, {}).get("kind") == "files" else " (print-only: declared, not verified)"
            lines.append(f"  {h}:{suffix}")
            indent = "    "
        else:
            shown = list(MODEL_CLASSES)
            indent = "  "
        for cname in shown:
            cblock = class_settings.get(cname, {})
            if not isinstance(cblock, dict):
                cblock = {}
            model = cblock.get("model") or "(not set)"
            thinking = cblock.get("thinking")
            t = f" thinking={thinking}" if thinking else ""
            lines.append(f"{indent}{cname}: model={model}{t}")
            if h == (default_host or hosts[0]):
                classes[cname] = {"model": model, "thinking": thinking}
    ms = topo["main_session"]
    if ms:
        cblock = host_models.get(ms.get("host"), {})
        cblock = cblock.get(ms.get("class"), {}) if isinstance(cblock, dict) else {}
        if not isinstance(cblock, dict):
            cblock = {}
        model = ms.get("model") or cblock.get("model") or "(not set)"
        lines.append(f"  main session (implementer): host={ms.get('host')} model={model}")
    drift: list[str] = []
    for h in hosts:
        spec = HOSTS.get(h, {})
        if spec.get("kind") != "files":
            continue
        class_settings = host_models.get(h, {})
        if not isinstance(class_settings, dict):
            continue
        agent_dir = cwd / spec["agent_dir"]
        for aname, entry in topo["agents"].items():
            if entry["host"] != h:
                continue
            cblock = class_settings.get(entry["class"], {})
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
        "host": default_host or hosts[0],
        "hosts": hosts,
        "classes": classes,
        "drift": drift,
        "lines": lines,
    }
