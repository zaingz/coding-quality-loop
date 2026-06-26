# Agentic Orchestration

The Coding Quality Loop is **agentic-first**: each lifecycle step is a node that can be
run by a different agent, model, or tool profile. Teams pick the best model for each use
case instead of forcing one model to do intake, architecture, implementation, and review.

This file defines the routing model. The machine-readable form is
`assets/quality-loop.config.example.json`.

## Why route by step

Different lifecycle steps have different cost and capability profiles:

- Intake, routing, and summarization are mostly deterministic. Cheap, fast models do this
  well and keep cost low.
- Planning and risk assessment reward strong reasoning. Spend the capable model here.
- Implementation rewards code-specialized models that follow conventions and keep diffs small.
- Review must be independent. Use a separate model or at least a fresh session so the
  reviewer does not inherit the implementer's confidence.
- Policy enforcement must be deterministic. Use hooks or command guards, not a model.

## Agent Profiles

Profiles are defined by **role, not vendor**. Map each role to whatever model or tool your
platform provides. The names below are stable handles used by the config and the lifecycle.

| Profile | Role | Model class heuristic |
|---|---|---|
| `contract_agent` | INTAKE: turn the goal into a task contract | cheap/fast, structured output |
| `repo_mapper` | EXPLORE: find the smallest relevant code map | cheap/fast with repo/search tools |
| `planner` | PLAN: design the smallest correct change | strong reasoning |
| `minimality_reviewer` | MINIMALITY_GATE: pick the highest valid rung | strong reasoning |
| `implementer` | IMPLEMENT_SLICE: write the diff | code-specialized |
| `verification_runner` | VERIFY: run checks, capture evidence | cheap/fast + sandboxed exec |
| `fresh_reviewer` | REVIEW: independent diff review vs contract | strong reasoning, separate session |
| `packager` | PACKAGE: assemble the PR handoff | cheap/fast, structured output |
| `policy_guard` | Cross-cutting: block unsafe actions | deterministic hook/tool, no model |

## Default Step-to-Agent Matrix

| Step | Profile | Default model class | Required artifacts | Gate |
|---|---|---|---|---|
| INTAKE | `contract_agent` | cheap/fast | task contract | contract has goal, criteria, risk tier |
| EXPLORE | `repo_mapper` | cheap/fast | repo map | likely files named |
| PLAN | `planner` | strong reasoning | plan | plan names files + verification |
| MINIMALITY_GATE | `minimality_reviewer` | strong reasoning | minimality decision | rung chosen + lower rungs rejected |
| IMPLEMENT_SLICE | `implementer` | code-specialized | diff | diff scoped to plan |
| VERIFY | `verification_runner` | cheap/fast + exec | command evidence | evidence matches risk tier |
| REVIEW | `fresh_reviewer` | strong reasoning (separate session) | review verdict | verdict + findings recorded |
| PACKAGE | `packager` | cheap/fast | PR handoff | handoff complete |
| (all) | `policy_guard` | deterministic hook | block/allow log | no unsafe action passed |

## Model Selection Heuristics

- **Deterministic summarization / routing** (INTAKE, EXPLORE, VERIFY orchestration,
  PACKAGE): cheap, fast models. These steps follow a schema; reasoning depth adds little.
- **Architecture and risk** (PLAN, MINIMALITY_GATE): strong reasoning models. Wrong
  decisions here cost the most downstream.
- **Implementation** (IMPLEMENT_SLICE): code-specialized models that respect existing
  conventions and produce small, reviewable diffs.
- **Review** (REVIEW): an independent model, or at minimum a fresh session of the same
  model with no implementation context. Reviewing your own work in the same context
  inflates confidence and hides gaps.
- **Policy** (`policy_guard`): never a model. Use platform hooks or command guards so the
  block is deterministic and cannot be argued away by a prompt.

## Defaults First

Start with **one implementer + one independent reviewer** plus deterministic policy hooks.
This single split captures most of the quality gain.

Add specialized agents only when risk or complexity justifies the coordination cost:

- Split out a dedicated `planner` / `minimality_reviewer` for high-risk or architecturally
  significant work.
- Split out a dedicated `repo_mapper` for large or unfamiliar codebases.
- Keep `contract_agent` and `packager` merged into the implementer for low-risk tasks.

Over-parallelization is an anti-pattern: if coordination cost exceeds the quality gain,
collapse roles back into fewer agents.

## Risk-Scaled Routing

| Risk tier | Suggested topology |
|---|---|
| `low` | One agent runs the whole loop; `policy_guard` hook stays on. |
| `medium` | Implementer + independent `fresh_reviewer`; `verification_runner` runs real checks. |
| `high` | Dedicated `planner`, `minimality_reviewer`, `implementer`, independent `fresh_reviewer`, plus `policy_guard` enforcing security/migration blocks and human approval. |

## Mapping Profiles to Platforms

The same role maps onto different vendors. Examples (illustrative, not prescriptive):

- **Claude Code**: subagents/commands per profile; `policy_guard` via `.claude/settings.json`
  PreToolUse/PostToolUse/Stop hooks. See
  https://docs.anthropic.com/en/docs/claude-code/hooks
- **Codex**: subagents and skills per profile; `AGENTS.md` carries the loop; MCP servers
  back `verification_runner` and `repo_mapper`. See
  https://developers.openai.com/codex/concepts/customization
- **Cursor**: project rules in `.cursor/rules` carry the loop; agent steps map to chat/agent
  runs. See https://docs.cursor.com/en/context/rules
- **Standalone / custom orchestrator**: model each step as an explicit workflow node and
  wire the tool contracts from `references/tool-contracts.md`; load
  `assets/quality-loop.config.example.json` to drive routing.

## Config-Driven Routing

`assets/quality-loop.config.example.json` encodes this matrix as data: each step maps to a
profile, a model placeholder, allowed tools, required artifacts, and the gate that must pass
before the step is considered complete. Orchestrators can read it directly; humans can read
it as documentation. Validate it with:

```bash
python scripts/quality_loop.py check-config assets/quality-loop.config.example.json
```
