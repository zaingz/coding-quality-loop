# Coding Quality Loop (Droid)

Droid loads custom droids from `.factory/droids/` (project scope) or
`~/.factory/droids/` (user scope). Each droid is a Markdown file with YAML
frontmatter (`name`, `description`, `model`) plus a system prompt. Invoke a
droid with the `Task` tool or `droid exec`. See
https://docs.factory.ai/cli/droid-exec/overview

## Install

```bash
# Project-local: copy the example role droids into your repo
mkdir -p .factory/droids
cp examples/droid/.factory/droids/*.md .factory/droids/

# Or copy the skill for the main implementer thread
cp SKILL.md .factory/droids/  # the implementer reads SKILL.md from the repo root
```

## Role wiring

The main session is the **implementer** (single-threaded writes). Read-only
roles run as separate droids with fresh context:

| Role | Droid | Model class | When |
|---|---|---|---|
| context mapper | `quality-loop-context-mapper` | cheap/fast | EXPLORE |
| planner | `quality-loop-planner` | strong-reasoning | MINIMALITY_GATE + PLAN |
| reviewer | `quality-loop-reviewer` | strong-reasoning (fresh session) | REVIEW |
| security reviewer | `quality-loop-security-reviewer` | strong-reasoning (fresh session) | risk boundaries only |

The implementer stays the main thread. The reviewers and mapper are dispatched
as read-only subagents so they do not inherit the implementer's confidence.
This matches Cognition's 2026 finding: multi-agent works when writes stay
single-threaded and other agents contribute intelligence, not parallel writes
(https://cognition.com/blog/multi-agents-working).

## Model routing

Each droid ships with `model: inherit` (host-neutral at rest). To wire real
models, fill the `model_routing` section in `quality-loop.config.json` and run:

```bash
python3 scripts/quality_loop.py setup-models --host droid
```

This rewrites each droid's `model:` frontmatter to the configured Factory model
id (e.g. `claude-sonnet-4-5-20250929`, `gpt-5-codex`, or `custom:<id>` for
BYOK) and sets `reasoningEffort:` (`low`/`medium`/`high`) where configured. The
`assets/quality-loop.config.example.json` profiles are the canonical
role-to-model-class mapping; the droid frontmatter is the Droid-native
expression of the same routing data. Run `brief` to see the active routing and
detect drift.

## One-line usage

```bash
# headless driven run (the skill lives in the repo root)
droid exec "Follow the Coding Quality Loop in SKILL.md to fix the failing test and summarize verification evidence."
```

## Harness-agnostic notes

The `model` field in each droid's frontmatter is the Droid-native expression of
the per-role routing data. Droids ship with `model: inherit` so they are
host-neutral at rest; run `setup-models --host droid` to write configured model
ids and `reasoningEffort` values. The
`assets/quality-loop.config.example.json` profiles are the canonical
role-to-model-class mapping.
