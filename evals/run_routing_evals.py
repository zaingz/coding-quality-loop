#!/usr/bin/env python3
"""Offline eval harness for config-based model routing (setup-models).

Exercises the full CLI path (setup-models, check-config, brief) against temp
dirs with constructed agent files and configs. No models, no network.

Run: python evals/run_routing_evals.py   (exits non-zero if any case fails)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "quality_loop.py"
EXAMPLE_CONFIG = ROOT / "assets" / "quality-loop.config.example.json"
SCHEMA_CONFIG = ROOT / "assets" / "quality-loop.config.schema.json"

sys.path.insert(0, str(ROOT / "scripts"))
import quality_loop_routing as qlroute  # noqa: E402

from _harness import FAIL, PASS, main_loop, run_cli  # noqa: E402

DEFAULT_AGENTS = dict(qlroute.DEFAULT_AGENTS)
AGENT_NAMES = list(DEFAULT_AGENTS.keys())


def load_example() -> dict:
    return json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))


def make_agent_md(name: str, model: str = "inherit") -> str:
    return (
        f"---\n"
        f"name: {name}\n"
        f"description: test agent\n"
        f"model: {model}\n"
        f"---\n\n"
        f"You are a test agent.\n"
    )


def write_routing_config(
    path: Path, host: str, host_models: dict, agents: dict | None = None
) -> Path:
    cfg = {
        "model_routing": {
            "host": host,
            "host_models": {host: host_models},
            "agents": agents or dict(DEFAULT_AGENTS),
        }
    }
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return path


def make_claude_target(tmp: Path) -> Path:
    target = tmp / "project"
    agents_dir = target / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    for name in AGENT_NAMES:
        (agents_dir / f"{name}.md").write_text(make_agent_md(name), encoding="utf-8")
    return target


def make_droid_target(tmp: Path) -> Path:
    target = tmp / "project"
    droids_dir = target / ".factory" / "droids"
    droids_dir.mkdir(parents=True)
    for name in AGENT_NAMES:
        (droids_dir / f"{name}.md").write_text(make_agent_md(name), encoding="utf-8")
    return target


# --- Cases -----------------------------------------------------------------

def case_claude_code_rewrite(tmp: Path) -> tuple[bool, str]:
    target = make_claude_target(tmp)
    cfg = write_routing_config(tmp / "config.json", "claude-code", {
        "cheap_fast": {"model": "haiku"},
        "strong_reasoning": {"model": "sonnet"},
        "code_specialized": {"model": "inherit"},
    })
    code, out, err = run_cli(
        "setup-models", "--config", str(cfg), "--host", "claude-code", "--target", str(target)
    )
    mapper = (target / ".claude/agents/quality-loop-context-mapper.md").read_text()
    planner = (target / ".claude/agents/quality-loop-planner.md").read_text()
    ok = code == 0 and "model: haiku" in mapper and "model: sonnet" in planner
    return ok, f"exit={code}; mapper_haiku={'model: haiku' in mapper}; planner_sonnet={'model: sonnet' in planner}"


def case_idempotency(tmp: Path) -> tuple[bool, str]:
    target = make_claude_target(tmp)
    cfg = write_routing_config(tmp / "config.json", "claude-code", {
        "cheap_fast": {"model": "haiku"},
        "strong_reasoning": {"model": "sonnet"},
        "code_specialized": {"model": "inherit"},
    })
    run_cli("setup-models", "--config", str(cfg), "--host", "claude-code", "--target", str(target))
    snap1 = (target / ".claude/agents/quality-loop-planner.md").read_text()
    code2, out2, _ = run_cli(
        "setup-models", "--config", str(cfg), "--host", "claude-code", "--target", str(target)
    )
    snap2 = (target / ".claude/agents/quality-loop-planner.md").read_text()
    ok = code2 == 0 and "unchanged" in out2 and snap1 == snap2
    return ok, f"exit2={code2}; unchanged_in_out={'unchanged' in out2}; identical={snap1 == snap2}"


def case_thinking_write_remove(tmp: Path) -> tuple[bool, str]:
    target = make_claude_target(tmp)
    cfg = write_routing_config(tmp / "config.json", "claude-code", {
        "cheap_fast": {"model": "haiku"},
        "strong_reasoning": {"model": "sonnet", "thinking": "high"},
        "code_specialized": {"model": "inherit"},
    })
    run_cli("setup-models", "--config", str(cfg), "--host", "claude-code", "--target", str(target))
    planner = (target / ".claude/agents/quality-loop-planner.md").read_text()
    has_effort = "effort: high" in planner
    cfg2 = write_routing_config(tmp / "config2.json", "claude-code", {
        "cheap_fast": {"model": "haiku"},
        "strong_reasoning": {"model": "sonnet"},
        "code_specialized": {"model": "inherit"},
    })
    run_cli("setup-models", "--config", str(cfg2), "--host", "claude-code", "--target", str(target))
    planner2 = (target / ".claude/agents/quality-loop-planner.md").read_text()
    no_effort = "effort:" not in planner2
    ok = has_effort and no_effort
    return ok, f"has_effort={has_effort}; no_effort_after_remove={no_effort}"


def case_droid_rewrite(tmp: Path) -> tuple[bool, str]:
    target = make_droid_target(tmp)
    droids_dir = target / ".factory" / "droids"
    cfg = write_routing_config(tmp / "config.json", "droid", {
        "cheap_fast": {"model": "claude-haiku-4-5-20251001", "thinking": "low"},
        "strong_reasoning": {"model": "claude-sonnet-4-5-20250929", "thinking": "high"},
        "code_specialized": {"model": "inherit"},
    })
    code, out, err = run_cli(
        "setup-models", "--config", str(cfg), "--host", "droid", "--target", str(target)
    )
    mapper = (droids_dir / "quality-loop-context-mapper.md").read_text()
    planner = (droids_dir / "quality-loop-planner.md").read_text()
    ok = (
        code == 0
        and "model: claude-haiku-4-5-20251001" in mapper
        and "reasoningEffort: low" in mapper
        and "model: claude-sonnet-4-5-20250929" in planner
        and "reasoningEffort: high" in planner
    )
    return ok, f"exit={code}; mapper_ok={('claude-haiku' in mapper and 'reasoningEffort: low' in mapper)}; planner_ok={('claude-sonnet' in planner and 'reasoningEffort: high' in planner)}"


def case_droid_missing_dir(tmp: Path) -> tuple[bool, str]:
    target = tmp / "project"
    target.mkdir()
    cfg = write_routing_config(tmp / "config.json", "droid", {
        "cheap_fast": {"model": "inherit"},
        "strong_reasoning": {"model": "inherit"},
        "code_specialized": {"model": "inherit"},
    })
    code, out, err = run_cli(
        "setup-models", "--config", str(cfg), "--host", "droid", "--target", str(target)
    )
    ok = code != 0 and "install.py --host droid" in err
    return ok, f"exit={code}; hint_in_err={'install.py --host droid' in err}"


def case_codex_print(tmp: Path) -> tuple[bool, str]:
    target = tmp / "project"
    target.mkdir()
    cfg = write_routing_config(tmp / "config.json", "codex", {
        "cheap_fast": {"model": "gpt-5.5", "thinking": "low"},
        "strong_reasoning": {"model": "gpt-5.5", "thinking": "medium"},
        "code_specialized": {"model": "gpt-5.5", "thinking": "medium"},
    })
    code, out, err = run_cli(
        "setup-models", "--config", str(cfg), "--host", "codex", "--target", str(target)
    )
    has_model = 'model = "gpt-5.5"' in out
    has_low = 'model_reasoning_effort = "low"' in out
    has_medium = 'model_reasoning_effort = "medium"' in out
    no_files = not (target / ".codex").exists()
    ok = code == 0 and has_model and has_low and has_medium and no_files
    return ok, f"exit={code}; model={has_model}; low={has_low}; medium={has_medium}; no_files={no_files}"


def case_pi_print(tmp: Path) -> tuple[bool, str]:
    target = tmp / "project"
    target.mkdir()
    cfg = write_routing_config(tmp / "config.json", "pi", {
        "cheap_fast": {"model": "gpt-5.5", "thinking": "low"},
        "strong_reasoning": {"model": "o3-pro", "thinking": "high"},
        "code_specialized": {"model": "gpt-5.5"},
    })
    code, out, err = run_cli(
        "setup-models", "--config", str(cfg), "--host", "pi", "--target", str(target)
    )
    has_model = "/model gpt-5.5" in out
    has_thinking = "thinking: low" in out
    has_fresh = "fresh session" in out.lower()
    no_files = not (target / ".pi").exists() and not (target / ".codex").exists()
    ok = code == 0 and has_model and has_thinking and has_fresh and no_files
    return ok, f"exit={code}; model={has_model}; thinking={has_thinking}; fresh={has_fresh}; no_files={no_files}"


def case_unsupported_thinking(tmp: Path) -> tuple[bool, str]:
    target = tmp / "project"
    target.mkdir()
    cfg = write_routing_config(tmp / "config.json", "codex", {
        "cheap_fast": {"model": "gpt-5.5", "thinking": "max"},
        "strong_reasoning": {"model": "gpt-5.5", "thinking": "medium"},
        "code_specialized": {"model": "gpt-5.5"},
    })
    code, out, err = run_cli(
        "setup-models", "--config", str(cfg), "--host", "codex", "--target", str(target)
    )
    ok = code == 1 and "max" in err and "not supported" in err
    return ok, f"exit={code}; max_in_err={'max' in err}; not_supported={'not supported' in err}"


def case_check_config(tmp: Path) -> tuple[bool, str]:
    code1, _, _ = run_cli("check-config", str(EXAMPLE_CONFIG))
    example_ok = code1 == 0

    cfg_no_section = load_example()
    cfg_no_section.pop("model_routing", None)
    p2 = tmp / "no-section.json"
    p2.write_text(json.dumps(cfg_no_section, indent=2), encoding="utf-8")
    code2, _, _ = run_cli("check-config", str(p2))
    no_section_ok = code2 == 0

    cfg_bad_host = load_example()
    cfg_bad_host["model_routing"]["host"] = "turbo"
    p3 = tmp / "bad-host.json"
    p3.write_text(json.dumps(cfg_bad_host, indent=2), encoding="utf-8")
    code3, _, err3 = run_cli("check-config", str(p3))
    bad_host_ok = code3 == 1 and "turbo" in err3

    cfg_bad_class = load_example()
    cfg_bad_class["model_routing"]["host_models"]["codex"]["turbo_class"] = {"model": "x"}
    p4 = tmp / "bad-class.json"
    p4.write_text(json.dumps(cfg_bad_class, indent=2), encoding="utf-8")
    code4, _, err4 = run_cli("check-config", str(p4))
    bad_class_ok = code4 == 1 and "turbo_class" in err4

    cfg_bad_think = load_example()
    cfg_bad_think["model_routing"]["host_models"]["codex"]["cheap_fast"]["thinking"] = "turbo"
    p5 = tmp / "bad-think.json"
    p5.write_text(json.dumps(cfg_bad_think, indent=2), encoding="utf-8")
    code5, _, err5 = run_cli("check-config", str(p5))
    bad_think_ok = code5 == 1 and "thinking" in err5

    ok = example_ok and no_section_ok and bad_host_ok and bad_class_ok and bad_think_ok
    return ok, f"example={example_ok}; no_section={no_section_ok}; bad_host={bad_host_ok}; bad_class={bad_class_ok}; bad_think={bad_think_ok}"


def case_check_config_same_model_class(tmp: Path) -> tuple[bool, str]:
    """Reviewer heterogeneity must fail when IMPLEMENT_SLICE and REVIEW use the
    same model_class on medium+ routing (with a concrete resolved model), and
    must NOT false-positive when the resolved model is a placeholder (inherit).
    """
    # Same model_class + concrete model -> fail.
    cfg_bad = load_example()
    cfg_bad["model_routing"]["host"] = "claude-code"
    cfg_bad["model_routing"]["host_models"]["claude-code"]["code_specialized"]["model"] = "claude-sonnet-4-5"
    for step in cfg_bad["steps"]:
        if step.get("step") == "REVIEW":
            step["model_class"] = "code_specialized"  # same as IMPLEMENT_SLICE
    p1 = tmp / "same-class.json"
    p1.write_text(json.dumps(cfg_bad, indent=2), encoding="utf-8")
    code1, _, err1 = run_cli("check-config", str(p1))
    same_class_fails = code1 == 1 and "reviewer heterogeneity" in err1 and "model_class" in err1

    # Same model_class + placeholder resolved model (inherit) -> no false positive.
    cfg_ph = load_example()
    cfg_ph["model_routing"]["host"] = "claude-code"
    # code_specialized stays "inherit" (placeholder) in the example
    for step in cfg_ph["steps"]:
        if step.get("step") == "REVIEW":
            step["model_class"] = "code_specialized"
    p2 = tmp / "same-class-placeholder.json"
    p2.write_text(json.dumps(cfg_ph, indent=2), encoding="utf-8")
    code2, _, err2 = run_cli("check-config", str(p2))
    placeholder_ok = code2 == 0 and "reviewer heterogeneity" not in err2

    ok = same_class_fails and placeholder_ok
    return ok, f"same_class(exit={code1},flagged={same_class_fails}); placeholder(exit={code2},clean={placeholder_ok})"


def case_check_config_planner_strong_reasoning(tmp: Path) -> tuple[bool, str]:
    """P3.18: the planner/orchestrator step must route to strong_reasoning.
    Downgrading PLAN to a cheaper class fails check-config; the example config
    (PLAN -> strong_reasoning) passes."""
    good = load_example()
    p_good = tmp / "good.json"
    p_good.write_text(json.dumps(good, indent=2), encoding="utf-8")
    code_good, _, _ = run_cli("check-config", str(p_good))

    bad = load_example()
    for step in bad["steps"]:
        if step.get("step") == "PLAN":
            step["model_class"] = "cheap_fast"
    p_bad = tmp / "bad.json"
    p_bad.write_text(json.dumps(bad, indent=2), encoding="utf-8")
    code_bad, _, err_bad = run_cli("check-config", str(p_bad))
    bad_flagged = code_bad == 1 and "strong_reasoning" in err_bad and "PLAN" in err_bad

    ok = code_good == 0 and bad_flagged
    return ok, f"good(exit={code_good}); bad(exit={code_bad},flagged={bad_flagged})"


def case_example_config_schema_valid(tmp: Path) -> tuple[bool, str]:
    """P2.13: the shipped example config must be valid against its own tightened
    schema AND pass check-config (schema-valid == checker-valid). With root
    additionalProperties:false, every top-level key (including the IDE `$schema`
    pointer) must be declared in the schema. Uses a real jsonschema validator
    when available; otherwise a stdlib top-level-shape check pins the same
    regression ($schema whitelisted, no undeclared keys, required present)."""
    config = json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_CONFIG.read_text(encoding="utf-8"))

    validator_used = "stdlib"
    schema_ok = True
    detail = ""
    try:
        import jsonschema  # type: ignore

        validator_used = "jsonschema"
        try:
            jsonschema.validate(config, schema)
        except jsonschema.ValidationError as exc:  # noqa: PERF203
            schema_ok = False
            detail = str(exc).splitlines()[0]
    except ImportError:
        # Stdlib fallback: root additionalProperties:false means the config's
        # top-level keys must be a subset of declared properties, and every
        # required key must be present.
        declared = set(schema.get("properties", {}))
        if schema.get("additionalProperties") is False:
            undeclared = set(config) - declared
            if undeclared:
                schema_ok = False
                detail = f"undeclared top-level keys: {sorted(undeclared)}"
        missing = [k for k in schema.get("required", []) if k not in config]
        if missing:
            schema_ok = False
            detail = (detail + "; " if detail else "") + f"missing required: {missing}"

    code, _, err = run_cli("check-config", str(EXAMPLE_CONFIG))
    checker_ok = code == 0

    ok = schema_ok and checker_ok
    return ok, (
        f"validator={validator_used}; schema_valid={schema_ok}; "
        f"checker_valid={checker_ok}(exit={code})"
        + (f"; {detail}" if detail else "")
        + (f"; {err.strip()}" if not checker_ok and err.strip() else "")
    )


def case_effort_ceiling(tmp: Path) -> tuple[bool, str]:
    """xhigh/max exceed the 'high' ceiling: check-config rejects them unless the
    block sets allow_overthink; setup-models surfaces an advisory warning."""
    # xhigh without allow_overthink -> check-config fails with a ceiling message.
    cfg_over = load_example()
    cfg_over["model_routing"]["host_models"]["codex"]["strong_reasoning"]["thinking"] = "xhigh"
    p1 = tmp / "over.json"
    p1.write_text(json.dumps(cfg_over, indent=2), encoding="utf-8")
    code1, _, err1 = run_cli("check-config", str(p1))
    over_fails = code1 == 1 and "ceiling" in err1 and "allow_overthink" in err1

    # max (the other over-ceiling level) without allow_overthink -> also rejected.
    cfg_max = load_example()
    cfg_max["model_routing"]["host_models"]["codex"]["code_specialized"]["thinking"] = "max"
    pmax = tmp / "max.json"
    pmax.write_text(json.dumps(cfg_max, indent=2), encoding="utf-8")
    code_max, _, err_max = run_cli("check-config", str(pmax))
    max_fails = code_max == 1 and "ceiling" in err_max and "allow_overthink" in err_max

    # xhigh WITH allow_overthink -> check-config passes (explicit escape hatch).
    cfg_ok = load_example()
    block = cfg_ok["model_routing"]["host_models"]["codex"]["strong_reasoning"]
    block["thinking"] = "xhigh"
    block["allow_overthink"] = True
    p2 = tmp / "over-ok.json"
    p2.write_text(json.dumps(cfg_ok, indent=2), encoding="utf-8")
    code2, _, err2 = run_cli("check-config", str(p2))
    escape_ok = code2 == 0

    # setup-models surfaces an advisory ceiling warning (codex supports xhigh).
    target = tmp / "project"
    target.mkdir()
    cfg3 = write_routing_config(tmp / "warn.json", "codex", {
        "cheap_fast": {"model": "gpt-5.5", "thinking": "low"},
        "strong_reasoning": {"model": "gpt-5.5", "thinking": "xhigh"},
        "code_specialized": {"model": "gpt-5.5", "thinking": "high"},
    })
    code3, _, err3 = run_cli("setup-models", "--config", str(cfg3), "--host", "codex", "--target", str(target))
    warns = code3 == 1 and "ceiling" in err3

    ok = over_fails and max_fails and escape_ok and warns
    return ok, f"xhigh_fails(exit={code1})={over_fails}; max_fails(exit={code_max})={max_fails}; escape_ok(exit={code2})={escape_ok}; setup_warn(exit={code3})={warns}"


def case_brief_routing(tmp: Path) -> tuple[bool, str]:
    target = make_claude_target(tmp)
    cfg = write_routing_config(tmp / "config.json", "claude-code", {
        "cheap_fast": {"model": "haiku"},
        "strong_reasoning": {"model": "sonnet"},
        "code_specialized": {"model": "inherit"},
    })
    code, out, err = run_cli("brief", "--config", str(cfg), "--cwd", str(target))
    has_routing = "Model routing" in out
    has_drift = "drift" in out

    target2 = tmp / "project2"
    target2.mkdir()
    code2, out2, _ = run_cli("brief", "--cwd", str(target2))
    has_hint = "not configured" in out2

    ok = code == 0 and has_routing and has_drift and has_hint
    return ok, f"routing={has_routing}; drift={has_drift}; hint={has_hint}"


def case_dry_run(tmp: Path) -> tuple[bool, str]:
    target = make_claude_target(tmp)
    original = (target / ".claude/agents/quality-loop-planner.md").read_text()
    cfg = write_routing_config(tmp / "config.json", "claude-code", {
        "cheap_fast": {"model": "haiku"},
        "strong_reasoning": {"model": "sonnet"},
        "code_specialized": {"model": "inherit"},
    })
    code, out, err = run_cli(
        "setup-models", "--config", str(cfg), "--host", "claude-code",
        "--target", str(target), "--dry-run"
    )
    after = (target / ".claude/agents/quality-loop-planner.md").read_text()
    ok = code == 0 and "dry-run" in out and after == original and "model: inherit" in after
    return ok, f"exit={code}; dry_run_in_out={'dry-run' in out}; unchanged={after == original}"


def write_routing_dict(path: Path, routing: dict) -> Path:
    path.write_text(json.dumps({"model_routing": routing}), encoding="utf-8")
    return path


def make_dual_target(tmp: Path) -> Path:
    """A project with both file hosts installed (claude-code + droid)."""
    target = make_claude_target(tmp)
    droids_dir = target / ".factory" / "droids"
    droids_dir.mkdir(parents=True)
    for name in AGENT_NAMES:
        (droids_dir / f"{name}.md").write_text(make_agent_md(name), encoding="utf-8")
    return target


MULTIHOST_ROUTING = {
    "host": "claude-code",
    "host_models": {
        "claude-code": {
            "cheap_fast": {"model": "claude-haiku-4-5", "family": "claude", "thinking": "low"},
            "strong_reasoning": {"model": "claude-fable-5", "family": "claude", "thinking": "high"},
        },
        "droid": {
            "code_specialized": {"model": "glm-5.2-fast", "family": "glm", "thinking": "high"},
        },
        "codex": {
            "strong_reasoning": {"model": "gpt-5.6-sol", "family": "gpt", "thinking": "high"},
        },
    },
    "agents": {
        "quality-loop-context-mapper": "cheap_fast",
        "quality-loop-planner": "strong_reasoning",
        "quality-loop-reviewer": {"host": "codex", "class": "strong_reasoning"},
        "quality-loop-security-reviewer": {"host": "codex", "class": "strong_reasoning"},
    },
    "main_session": {"host": "droid", "class": "code_specialized", "model": "glm-5.2-fast"},
    "allow_same_family": False,
}


def case_v41_shape_backcompat(tmp: Path) -> tuple[bool, str]:
    """A v4.1-shaped config (string agents, single host) and its object-form
    equivalent ({host: <default>} entries) must produce byte-identical agent
    files -- the multi-host extension cannot change existing behavior."""
    models = {
        "cheap_fast": {"model": "haiku"},
        "strong_reasoning": {"model": "sonnet"},
        "code_specialized": {"model": "inherit"},
    }
    t1 = make_claude_target(tmp / "a")
    cfg1 = write_routing_config(tmp / "v41.json", "claude-code", dict(models))
    code1, out1, _ = run_cli("setup-models", "--config", str(cfg1), "--target", str(t1))
    t2 = (tmp / "b" / "project")
    agents_dir = t2 / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    for name in AGENT_NAMES:
        (agents_dir / f"{name}.md").write_text(make_agent_md(name), encoding="utf-8")
    cfg2 = write_routing_dict(tmp / "obj.json", {
        "host": "claude-code",
        "host_models": {"claude-code": dict(models)},
        "agents": {n: {"host": "claude-code", "class": c} for n, c in DEFAULT_AGENTS.items()},
    })
    code2, out2, _ = run_cli("setup-models", "--config", str(cfg2), "--target", str(t2))
    identical = all(
        (t1 / ".claude/agents" / f"{n}.md").read_text() == (t2 / ".claude/agents" / f"{n}.md").read_text()
        for n in AGENT_NAMES
    )
    single_host_view = "hosts=" not in out1 and "PRINT-ONLY" not in out1
    # agents: {} was legal in v4.1 (host configured, nothing to rewrite) -- it
    # must not regress into "no host selected" / "not configured".
    t3 = tmp / "c"
    t3.mkdir()
    cfg3 = write_routing_dict(tmp / "empty.json", {
        "host": "claude-code",
        "host_models": {"claude-code": dict(models)},
        "agents": {},
    })
    code3, out3, err3 = run_cli("setup-models", "--config", str(cfg3), "--target", str(t3))
    empty_ok = code3 == 0 and "no host selected" not in err3
    code4, out4, _ = run_cli("brief", "--config", str(cfg3), "--cwd", str(t3))
    empty_brief_ok = "host=claude-code" in out4 and "not set" not in out4
    ok = (
        code1 == 0 and code2 == 0 and identical and single_host_view
        and empty_ok and empty_brief_ok
    )
    return ok, (
        f"exits=({code1},{code2}); files_identical={identical}; single_host_view={single_host_view}; "
        f"empty_agents(exit={code3},ok={empty_ok}); empty_brief_ok={empty_brief_ok}"
    )


def case_multihost_apply(tmp: Path) -> tuple[bool, str]:
    """One setup-models run with no --host applies every host in the topology:
    rewrites the file host, notes the main-session-only droid leg, and prints
    the codex section behind the PRINT-ONLY banner."""
    target = make_dual_target(tmp)
    cfg = write_routing_dict(tmp / "config.json", MULTIHOST_ROUTING)
    code, out, err = run_cli("setup-models", "--config", str(cfg), "--target", str(target))
    mapper = (target / ".claude/agents/quality-loop-context-mapper.md").read_text()
    planner = (target / ".claude/agents/quality-loop-planner.md").read_text()
    droid_untouched = "model: inherit" in (target / ".factory/droids/quality-loop-reviewer.md").read_text()
    banner = "PRINT-ONLY" in out and "not applied or verified" in out
    codex_models = 'model = "gpt-5.6-sol"' in out
    droid_note = "no agent files assigned to droid" in out
    main_elsewhere = "runs on host 'droid'" in out
    no_applied_checkmark = "applied" not in out.lower() or "not applied" in out.lower()
    ok = (
        code == 0
        and "model: claude-haiku-4-5" in mapper
        and "model: claude-fable-5" in planner
        and droid_untouched and banner and codex_models and droid_note
        and main_elsewhere and no_applied_checkmark
    )
    return ok, (
        f"exit={code}; mapper={'claude-haiku-4-5' in mapper}; planner={'claude-fable-5' in planner}; "
        f"droid_untouched={droid_untouched}; banner={banner}; codex={codex_models}; "
        f"droid_note={droid_note}; main_elsewhere={main_elsewhere}"
    )


def case_multihost_host_filter(tmp: Path) -> tuple[bool, str]:
    """--host filters a multi-host topology to that host's slice only."""
    target = make_dual_target(tmp)
    routing = json.loads(json.dumps(MULTIHOST_ROUTING))
    routing["agents"]["quality-loop-context-mapper"] = {"host": "droid", "class": "cheap_fast"}
    routing["host_models"]["droid"]["cheap_fast"] = {"model": "glm-5.2", "family": "glm", "thinking": "low"}
    cfg = write_routing_dict(tmp / "config.json", routing)
    code, out, err = run_cli("setup-models", "--config", str(cfg), "--host", "droid", "--target", str(target))
    droid_mapper = (target / ".factory/droids/quality-loop-context-mapper.md").read_text()
    claude_untouched = all(
        "model: inherit" in (target / ".claude/agents" / f"{n}.md").read_text() for n in AGENT_NAMES
    )
    # --host on a multi-host topology is a pure FILTER: string agents belonging
    # to the default host must NOT be retargeted onto the selected host.
    droid_planner_untouched = "model: inherit" in (
        target / ".factory/droids/quality-loop-planner.md"
    ).read_text()
    no_retarget = "quality-loop-planner: model" not in out
    no_codex = "gpt-5.6-sol" not in out
    ok = (
        code == 0 and "model: glm-5.2" in droid_mapper and claude_untouched
        and droid_planner_untouched and no_retarget and no_codex
    )
    return ok, (
        f"exit={code}; droid_mapper={'model: glm-5.2' in droid_mapper}; claude_untouched={claude_untouched}; "
        f"planner_not_retargeted={droid_planner_untouched and no_retarget}; no_codex={no_codex}"
    )


def case_cross_host_family(tmp: Path) -> tuple[bool, str]:
    """Cross-host reviewer heterogeneity on model family: same family across
    hosts fails; allow_same_family suppresses the family error but never the
    same-model error."""
    # Implementer on droid resolves to a claude-family model; reviewer pinned to
    # codex also resolves to claude family -> error.
    base = load_example()
    routing = json.loads(json.dumps(MULTIHOST_ROUTING))
    routing["host_models"]["droid"]["code_specialized"] = {"model": "anthropic/claude-sonnet-5"}
    routing["main_session"] = {"host": "droid", "class": "code_specialized"}
    routing["host_models"]["codex"]["strong_reasoning"] = {"model": "claude-sonnet-4-5"}
    base["model_routing"] = routing
    p1 = tmp / "same-family.json"
    p1.write_text(json.dumps(base), encoding="utf-8")
    code1, _, err1 = run_cli("check-config", str(p1))
    family_flagged = code1 == 1 and "same model family" in err1 and "allow_same_family" in err1

    # allow_same_family: true -> family error suppressed.
    base2 = json.loads(json.dumps(base))
    base2["model_routing"]["allow_same_family"] = True
    p2 = tmp / "same-family-allowed.json"
    p2.write_text(json.dumps(base2), encoding="utf-8")
    code2, _, err2 = run_cli("check-config", str(p2))
    allowed_ok = code2 == 0

    # Same concrete model across hosts -> error even with allow_same_family,
    # and the comparison is case-insensitive (one model is not two models
    # because of capitalization).
    base3 = json.loads(json.dumps(base2))
    base3["model_routing"]["host_models"]["codex"]["strong_reasoning"]["model"] = "ANTHROPIC/CLAUDE-SONNET-5"
    p3 = tmp / "same-model.json"
    p3.write_text(json.dumps(base3), encoding="utf-8")
    code3, _, err3 = run_cli("check-config", str(p3))
    same_model_flagged = code3 == 1 and "same model" in err3

    # Different families across hosts (glm vs gpt) -> clean.
    base4 = load_example()
    base4["model_routing"] = json.loads(json.dumps(MULTIHOST_ROUTING))
    p4 = tmp / "hetero.json"
    p4.write_text(json.dumps(base4), encoding="utf-8")
    code4, _, err4 = run_cli("check-config", str(p4))
    hetero_ok = code4 == 0

    # Blind-spot regression: a HOST-LESS reviewer agents entry is what
    # setup-models applies; pointing it at the implementer's class must fail
    # even though the REVIEW step class differs.
    base5 = load_example()
    base5["model_routing"]["host"] = "claude-code"
    base5["model_routing"]["host_models"]["claude-code"]["code_specialized"] = {"model": "claude-opus-4-8"}
    base5["model_routing"]["host_models"]["claude-code"]["strong_reasoning"] = {"model": "gpt-5.6-sol", "family": "gpt"}
    base5["model_routing"]["agents"]["quality-loop-reviewer"] = {"class": "code_specialized"}
    p5 = tmp / "hostless-reviewer.json"
    p5.write_text(json.dumps(base5), encoding="utf-8")
    code5, _, err5 = run_cli("check-config", str(p5))
    blind_spot_flagged = code5 == 1 and "reviewer heterogeneity" in err5

    # No false positive: main_session pinning an explicitly DIFFERENT model may
    # share the reviewer's class and host.
    base6 = load_example()
    base6["model_routing"]["host"] = "claude-code"
    base6["model_routing"]["host_models"]["claude-code"]["strong_reasoning"] = {"model": "claude-sonnet-5", "family": "claude"}
    for step in base6["steps"]:
        if step.get("step") == "IMPLEMENT_SLICE":
            step["model_class"] = "strong_reasoning"
    base6["model_routing"]["main_session"] = {"host": "claude-code", "class": "strong_reasoning", "model": "gpt-5.6-terra"}
    p6 = tmp / "ms-distinct.json"
    p6.write_text(json.dumps(base6), encoding="utf-8")
    code6, _, err6 = run_cli("check-config", str(p6))
    ms_override_ok = code6 == 0 and "reviewer heterogeneity" not in err6

    ok = (
        family_flagged and allowed_ok and same_model_flagged and hetero_ok
        and blind_spot_flagged and ms_override_ok
    )
    return ok, (
        f"family(exit={code1},flagged={family_flagged}); allowed(exit={code2}); "
        f"same_model(exit={code3},flagged={same_model_flagged}); hetero(exit={code4}); "
        f"hostless_reviewer(exit={code5},flagged={blind_spot_flagged}); ms_distinct(exit={code6},clean={ms_override_ok})"
    )


def case_family_alias_hole(tmp: Path) -> tuple[bool, str]:
    """The alias hole: implementer 'sonnet' and reviewer 'claude-sonnet-4-5' are
    different strings but the same family -- must now fail on a single host."""
    cfg = load_example()
    cfg["model_routing"]["host"] = "claude-code"
    cfg["model_routing"]["host_models"]["claude-code"]["code_specialized"] = {"model": "sonnet"}
    # strong_reasoning stays "sonnet"-family ("claude-sonnet-4-5") for REVIEW.
    cfg["model_routing"]["host_models"]["claude-code"]["strong_reasoning"] = {"model": "claude-sonnet-4-5"}
    p = tmp / "alias.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    code, _, err = run_cli("check-config", str(p))
    flagged = code == 1 and "same model family" in err and "'claude'" in err
    ok = flagged
    return ok, f"exit={code}; flagged={flagged}"


def case_family_unknown_skips(tmp: Path) -> tuple[bool, str]:
    """Unknown/BYOK/placeholder ids must skip the family check, never fail it."""
    # BYOK id with no recognizable family tokens on the implementer leg (the
    # main_session must resolve from the block, so it carries no model of its
    # own here).
    cfg = load_example()
    routing = json.loads(json.dumps(MULTIHOST_ROUTING))
    routing["host_models"]["droid"]["code_specialized"] = {"model": "custom:my-fast-model"}
    routing["main_session"] = {"host": "droid", "class": "code_specialized"}
    cfg["model_routing"] = routing
    p1 = tmp / "byok.json"
    p1.write_text(json.dumps(cfg), encoding="utf-8")
    code1, _, err1 = run_cli("check-config", str(p1))
    byok_ok = code1 == 0 and "heterogeneity" not in err1

    # Placeholder (inherit) on the reviewer leg.
    cfg2 = load_example()
    routing2 = json.loads(json.dumps(MULTIHOST_ROUTING))
    routing2["host_models"]["codex"]["strong_reasoning"] = {"model": "inherit"}
    cfg2["model_routing"] = routing2
    p2 = tmp / "inherit.json"
    p2.write_text(json.dumps(cfg2), encoding="utf-8")
    code2, _, err2 = run_cli("check-config", str(p2))
    inherit_ok = code2 == 0 and "heterogeneity" not in err2

    # Explicit family declaration beats the prefix match (BYOK id declared glm
    # vs gpt reviewer stays clean; declared gpt vs gpt reviewer fails).
    cfg3 = load_example()
    routing3 = json.loads(json.dumps(MULTIHOST_ROUTING))
    routing3["host_models"]["droid"]["code_specialized"] = {"model": "custom:my-fast-model", "family": "gpt"}
    routing3["main_session"] = {"host": "droid", "class": "code_specialized"}
    cfg3["model_routing"] = routing3
    p3 = tmp / "declared.json"
    p3.write_text(json.dumps(cfg3), encoding="utf-8")
    code3, _, err3 = run_cli("check-config", str(p3))
    declared_flagged = code3 == 1 and "same model family" in err3

    ok = byok_ok and inherit_ok and declared_flagged
    return ok, f"byok(exit={code1}); inherit(exit={code2}); declared_family(exit={code3},flagged={declared_flagged})"


def case_topology_validation(tmp: Path) -> tuple[bool, str]:
    """Malformed topology fields are rejected with named errors."""
    checks = []
    for label, mutate, needle in [
        ("bad_agent_host", lambda r: r["agents"].__setitem__("quality-loop-reviewer", {"host": "turbo", "class": "strong_reasoning"}), "turbo"),
        ("bad_agent_shape", lambda r: r["agents"].__setitem__("quality-loop-reviewer", 7), "model_class string or an"),
        ("bad_main_class", lambda r: r.__setitem__("main_session", {"host": "droid", "class": "turbo_class"}), "turbo_class"),
        ("bad_allow_flag", lambda r: r.__setitem__("allow_same_family", "yes"), "allow_same_family"),
        ("bad_family_type", lambda r: r["host_models"]["droid"]["code_specialized"].__setitem__("family", 3), "family"),
        ("hostless_main_session", lambda r: (r.__setitem__("host", None), r.__setitem__("main_session", {"class": "code_specialized"})), "main_session needs a host"),
        ("pinned_host_without_block", lambda r: r["agents"].__setitem__("quality-loop-reviewer", {"host": "pi", "class": "strong_reasoning"}), "host_models.pi is not defined"),
    ]:
        cfg = load_example()
        routing = json.loads(json.dumps(MULTIHOST_ROUTING))
        mutate(routing)
        cfg["model_routing"] = routing
        p = tmp / f"{label}.json"
        p.write_text(json.dumps(cfg), encoding="utf-8")
        code, _, err = run_cli("check-config", str(p))
        checks.append((label, code == 1 and needle in err))
    ok = all(c[1] for c in checks)
    return ok, "; ".join(f"{label}={passed}" for label, passed in checks)


def case_brief_multihost(tmp: Path) -> tuple[bool, str]:
    """brief renders per-host routing, labels print hosts as declared-not-
    verified, names the main session, and still detects file-host drift."""
    target = make_dual_target(tmp)
    cfg = write_routing_dict(target / "quality-loop.config.json", MULTIHOST_ROUTING)
    # Apply first so the file host matches the config (fresh files say `inherit`,
    # which is honest drift until setup-models runs).
    run_cli("setup-models", "--config", str(cfg), "--target", str(target))
    code, out, err = run_cli("brief", "--config", str(cfg), "--cwd", str(target))
    hosts_line = "hosts=claude-code (default), droid, codex" in out
    print_only = "print-only: declared, not verified" in out
    main_line = "main session (implementer): host=droid model=glm-5.2-fast" in out
    no_drift_yet = "drift" not in out
    # Introduce drift on the file host: planner file says another model.
    planner = target / ".claude/agents/quality-loop-planner.md"
    planner.write_text(planner.read_text().replace("model: claude-fable-5", "model: stale-model"))
    code2, out2, _ = run_cli("brief", "--config", str(cfg), "--cwd", str(target))
    drift = "drift: quality-loop-planner model=stale-model, config says claude-fable-5" in out2
    ok = code == 0 and hosts_line and print_only and main_line and no_drift_yet and drift
    return ok, (
        f"hosts_line={hosts_line}; print_only={print_only}; main={main_line}; "
        f"clean_before={no_drift_yet}; drift_after={drift}"
    )


def case_routing_variants_validate(tmp: Path) -> tuple[bool, str]:
    """Every shipped routing variant splices into the example config check-
    config-clean, keeps the reviewer in a different family than the implementer,
    and keeps strong_reasoning effort at the 'high' ceiling."""
    variants_dir = ROOT / "assets" / "routing"
    variant_files = sorted(variants_dir.glob("*.json"))
    if len(variant_files) < 3:
        return False, f"expected >=3 variants in {variants_dir}, found {len(variant_files)}"
    results = []
    for vf in variant_files:
        variant = json.loads(vf.read_text(encoding="utf-8"))
        cfg = load_example()
        cfg["model_routing"] = variant
        p = tmp / vf.name
        p.write_text(json.dumps(cfg), encoding="utf-8")
        code, _, err = run_cli("check-config", str(p))
        clean = code == 0
        # Guard rails of the knob, checked on the data itself.
        same_family_off = variant.get("allow_same_family") is False
        efforts_ok = all(
            block.get("thinking") in (None, "minimal", "low", "medium", "high")
            for hblock in variant.get("host_models", {}).values()
            for block in hblock.values()
        )
        results.append((vf.name, clean and same_family_off and efforts_ok))
    ok = all(passed for _, passed in results)
    return ok, "; ".join(f"{name}={passed}" for name, passed in results)


CASES = [
    ("claude-code rewrite applies preset models", case_claude_code_rewrite),
    ("idempotency: second run reports unchanged", case_idempotency),
    ("thinking write then remove", case_thinking_write_remove),
    ("droid rewrite writes model + reasoningEffort", case_droid_rewrite),
    ("droid missing .factory/droids/ exits non-zero with install hint", case_droid_missing_dir),
    ("codex print contains model + effort levels, no file writes", case_codex_print),
    ("pi print contains /model + thinking + fresh-session note", case_pi_print),
    ("unsupported thinking on codex warns and exits 1", case_unsupported_thinking),
    ("check-config: rejects unknown host/class/thinking, accepts valid", case_check_config),
    ("check-config: same model_class on IMPLEMENT_SLICE+REVIEW fails; placeholder does not", case_check_config_same_model_class),
    ("check-config: planner/orchestrator step must route to strong_reasoning", case_check_config_planner_strong_reasoning),
    ("example config is schema-valid AND checker-valid (P2.13)", case_example_config_schema_valid),
    ("effort ceiling: xhigh/max rejected without allow_overthink, warned in setup", case_effort_ceiling),
    ("brief: routing section, drift detection, unconfigured hint", case_brief_routing),
    ("dry-run leaves files untouched", case_dry_run),
    ("v4.1 shape and object-form equivalent produce byte-identical files", case_v41_shape_backcompat),
    ("multi-host: one run applies file hosts, prints codex behind PRINT-ONLY banner", case_multihost_apply),
    ("multi-host: --host filters to that host's slice only", case_multihost_host_filter),
    ("cross-host family heterogeneity: same family fails; allow_same_family suppresses; same model never", case_cross_host_family),
    ("alias hole: 'sonnet' vs 'claude-sonnet-4-5' same family fails on one host", case_family_alias_hole),
    ("unknown/BYOK/placeholder ids skip the family check; declared family wins", case_family_unknown_skips),
    ("topology validation rejects malformed host/class/main_session/family fields", case_topology_validation),
    ("brief multi-host: per-host lines, print-only label, main session, drift", case_brief_multihost),
    ("shipped routing variants are check-config-clean with floors held", case_routing_variants_validate),
]


if __name__ == "__main__":
    raise SystemExit(main_loop(CASES, "routing eval cases passed"))
