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

| Role | Droid | Model | When |
|---|---|---|---|
| context mapper | `quality-loop-context-mapper` | haiku (cheap/fast) | EXPLORE |
| planner | `quality-loop-planner` | sonnet (strong-reasoning) | MINIMALITY_GATE + PLAN |
| reviewer | `quality-loop-reviewer` | sonnet (strong-reasoning, fresh session) | REVIEW |
| security reviewer | `quality-loop-security-reviewer` | sonnet (strong-reasoning, fresh session) | risk boundaries only |

The implementer stays the main thread. The reviewers and mapper are dispatched
as read-only subagents so they do not inherit the implementer's confidence.
This matches Cognition's 2026 finding: multi-agent works when writes stay
single-threaded and other agents contribute intelligence, not parallel writes
(https://cognition.com/blog/multi-agents-working).

## One-line usage

```bash
# headless driven run (the skill lives in the repo root)
droid exec "Follow the Coding Quality Loop in SKILL.md to fix the failing test and summarize verification evidence."
```

## Harness-agnostic notes

The `model` field in each droid's frontmatter expresses per-role routing:
`haiku` for the context mapper (cheap/fast), `sonnet` for the planner and
reviewers (strong-reasoning). Replace these with your provider's model
identifiers. The `assets/quality-loop.config.example.json` profiles are the
canonical role-to-model-class mapping; the droid frontmatter is the Droid-native
expression of the same routing data.
