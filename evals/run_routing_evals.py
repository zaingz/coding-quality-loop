#!/usr/bin/env python3
"""Offline eval harness for config-based model routing (setup-models).

Exercises the full CLI path (setup-models, check-config, brief) against temp
dirs with constructed agent files and configs. No models, no network.

Run: python evals/run_routing_evals.py   (exits non-zero if any case fails)
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "quality_loop.py"
EXAMPLE_CONFIG = ROOT / "assets" / "quality-loop.config.example.json"

sys.path.insert(0, str(ROOT / "scripts"))
import quality_loop_routing as qlroute  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"

DEFAULT_AGENTS = dict(qlroute.DEFAULT_AGENTS)
AGENT_NAMES = list(DEFAULT_AGENTS.keys())


def run_cli(*args: str, cwd: str | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd) if cwd else None,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


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

    ok = over_fails and escape_ok and warns
    return ok, f"over_fails(exit={code1})={over_fails}; escape_ok(exit={code2})={escape_ok}; setup_warn(exit={code3})={warns}"


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
    ("effort ceiling: xhigh/max rejected without allow_overthink, warned in setup", case_effort_ceiling),
    ("brief: routing section, drift detection, unconfigured hint", case_brief_routing),
    ("dry-run leaves files untouched", case_dry_run),
]


def main() -> int:
    failures = 0
    for name, fn in CASES:
        with tempfile.TemporaryDirectory() as td:
            try:
                ok, detail = fn(Path(td))
            except Exception as exc:  # noqa: BLE001
                ok, detail = False, f"exception: {exc!r}"
        print(f"[{PASS if ok else FAIL}] {name}\n        {detail}")
        failures += 0 if ok else 1
    print(f"\n{len(CASES) - failures}/{len(CASES)} routing eval cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
