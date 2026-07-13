# Coding Quality Loop (Pi)

> **Maintenance mode — outside the v5 routed loop.** The first-class v5 loop routes
> **Claude Code (implementer) + Codex (independent reviewer)**. Pi remains a supported
> install target: the skill, gates, and `setup-models --host pi` still work, and this
> example is kept current, but Pi is not part of the two-vendor routed kernel.

Pi loads skills as directories containing `SKILL.md` plus optional scripts/references/assets,
with progressive disclosure (metadata first, full instructions when relevant). Pi discovers
skills from `~/.pi/agent/skills/`, `~/.agents/skills/`, `.pi/skills/`, `.agents/skills/`, and
any directories listed under `skills` in settings. Each skill registers as `/skill:name`.
See https://pi.dev/docs/latest/skills

## Install

```bash
# Project-local: place the skill where Pi looks for it
mkdir -p .agents/skills
cp -r /path/to/coding-quality-loop .agents/skills/coding-quality-loop
# (this folder's .pi/settings.json already lists .agents/skills and .pi/skills)
```

For a user-level install, copy the skill into `~/.pi/agent/skills/coding-quality-loop` or
`~/.agents/skills/coding-quality-loop` instead.

## One-line usage

```text
/skill:coding-quality-loop implement the requested change with a validation contract and an independent review
```

Pi can also invoke the skill implicitly when a request matches its description. The bundled
`.pi/settings.json` shows the minimal `skills` configuration.

## Role wiring (right model per use case)

Pi lets you set a provider and model per role. Map each Quality Loop role to the model class
that fits it, following `assets/quality-loop.config.example.json`:

| Role | Model class | Pi config |
|---|---|---|
| context mapper (EXPLORE) | cheap/fast | `/model <cheap-fast-model>` before mapping |
| planner (MINIMALITY_GATE + PLAN) | strong reasoning | `/model <strong-reasoning-model>` for planning |
| implementer (IMPLEMENT_SLICE) | code-specialized | the main session model |
| reviewer (REVIEW) | strong reasoning, separate session | start a new Pi session or use a different provider for review |

To generate the `/model` commands and thinking levels for each role from your
config, fill the `model_routing` section in `quality-loop.config.json` and run:

```bash
python3 scripts/quality_loop.py setup-models --host pi
```

This prints the `/model` commands to run per role (no files written). Reviewers
still need a fresh Pi session so they do not inherit the implementer's context.

The implementer stays the main thread (single-threaded writes). The reviewer runs in a fresh
session so it does not inherit the implementer's confidence. This matches Cognition's 2026
finding: multi-agent works when writes stay single-threaded and other agents contribute
intelligence (https://cognition.com/blog/multi-agents-working).

For mission-class multi-day work with parallel workers, Pi's provider routing and session
management can carry the coordination cost without a custom runtime — but the routed v5 kernel
(Claude Code + Codex) is where enforced review independence lives.
