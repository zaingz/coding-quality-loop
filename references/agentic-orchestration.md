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

## Role Architecture

Profiles map onto a small set of roles. The step-profiles above are the per-step handles; the
roles below describe responsibilities and apply across the lifecycle. Add roles only as risk
and class grow (tiny/small need none of the specialist roles).

| Role | Maps to profile(s) | Responsibilities | Independent? |
|---|---|---|---|
| `orchestrator` | (medium/mission only) | Set scope, classify the task, gather context, write the spec + validation contract, decompose into worker tasks, assign workers, collect validator findings, create fix tasks, and **stop if unsafe**. | n/a |
| `context_mapper` | `repo_mapper` | Repo layout, relevant modules, entry points, data flow, existing helpers/patterns, tests and commands. Outputs **findings, not raw dumps**. | no |
| `implementer` | `implementer` | One bounded task: no speculative abstraction, no unrelated cleanup, smallest meaningful test, a coherent slice. | no |
| `validator` | `fresh_reviewer` | Fresh context; does **not** implement. Checks acceptance criteria, behavior contract, regression risk, edge cases, and evidence against the validation contract. | **yes** |
| `simplicity_reviewer` | `minimality_reviewer` | Deletion / reuse / stdlib / native / dependency / abstraction review — the complexity brake as a reviewer, run before plan and before review. | optional |
| `security_reviewer` | (boundary only) | Reviews changes at risk boundaries: auth, permissions, secrets, payments, PII, migrations, upload/download, network, shell, dependency changes. | **yes** |
| `policy_guard` | `policy_guard` | Deterministic safety blocks. Never a model. | enforced |

The `orchestrator` and `security_reviewer` are not per-step profiles in the base config; they
are mission/boundary roles. Wire them in for medium/mission work and at risk boundaries.

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

## Mission Topology (long-horizon work)

For mission-class work (multi-day, multi-module, multi-repo, uncertain architecture), one
context degrades and an implementer self-grading its own work inflates confidence. Split the
work, following the Missions architecture pattern
([Factory Missions](https://factory.ai/news/missions-architecture)):

```text
orchestrator
  ├─ context_mapper        -> context-map.md (shared)
  ├─ validation contract   -> validation-contract.md (shared)
  ├─ worker (implementer)  -> slice 1   ─┐
  ├─ worker (implementer)  -> slice 2   ─┤ fresh validator per slice / milestone
  ├─ worker (implementer)  -> slice 3   ─┘
  ├─ simplicity_reviewer   -> complexity brake before review
  ├─ security_reviewer     -> at risk boundaries only
  └─ collect findings -> create fix tasks -> stop if unsafe
```

Principles:

- **Serial is the safe default.** Parallelize only independent areas with low coordination cost.
  Concurrent writers must run in **isolated workspaces (git worktrees)** with **non-overlapping
  declared file scopes** and an orchestrator-owned conflict policy; if scopes can collide, run
  them serially rather than racing the working tree.
- Fresh agents per worker task; the orchestrator holds shared state, not every detail.
- Validators check the **validation contract**, not the implementer's narrative.
- The orchestrator turns validator findings into new fix tasks rather than patching inline.
- Review at milestone boundaries with fresh context; keep the mission record compact.

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
- **Pi**: ship the loop as a skill under `~/.pi/agent/skills/`, `~/.agents/skills/`,
  `.pi/skills/`, or `.agents/skills/`; register a `skills` directory in `.pi/settings.json` and
  invoke with `/skill:coding-quality-loop`; set a provider/model per role with `/model`. See
  https://pi.dev/docs/latest/skills
- **Droid (Factory)**: custom droids in `.factory/droids/` (project) or `~/.factory/droids/`
  (user), each a Markdown file with `name`/`description`/`model` frontmatter plus a system
  prompt. The main session is the implementer; read-only roles (mapper, planner, reviewer)
  run as separate droids via the `Task` tool or `droid exec`. See
  https://docs.factory.ai/cli/droid-exec/overview
- **Standalone / custom orchestrator**: model each step as an explicit workflow node and
  wire the tool contracts from `references/tool-contracts.md`; load
  `assets/quality-loop.config.example.json` to drive routing.

## Harness-Agnostic Wiring

The loop is **harness-agnostic by design**: roles, prompts, and routing data ship as files
that any host can consume without a custom runtime. The config is routing **data**; each host
expresses it through its native mechanism.

| Role | Claude Code | Droid | Codex | Cursor | Pi |
|---|---|---|---|---|---|
| context mapper | `.claude/agents/quality-loop-context-mapper.md` | `.factory/droids/quality-loop-context-mapper.md` | subagent / MCP | `.cursor/rules` chat | `/model <cheap-fast>` |
| planner | `.claude/agents/quality-loop-planner.md` | `.factory/droids/quality-loop-planner.md` | subagent | `.cursor/rules` chat | `/model <strong-reasoning>` |
| implementer | main thread | main session | main session | main session | main session |
| fresh reviewer | `.claude/agents/quality-loop-reviewer.md` | `.factory/droids/quality-loop-reviewer.md` | subagent (fresh) | new chat (fresh) | new Pi session |
| security reviewer | `.claude/agents/quality-loop-security-reviewer.md` | `.factory/droids/quality-loop-security-reviewer.md` | subagent (fresh) | new chat (fresh) | new Pi session |
| policy guard | `.claude/settings.json` hooks | host hooks / CI | `.codex/hooks.json` | host hooks / CI | host hooks / CI |

Per-role prompt cards live in `assets/prompts/` (`intake.md`, `context-map.md`,
`minimality.md`, `planner.md`, `implementer.md`, `reviewer.md`, `security-reviewer.md`,
`package.md`). Any harness or human can run any role by pasting one card.

### What the 2026 research confirms

Cognition's April 2026 update ("Multi-Agents: What's Actually Working") validates the core
bet: multi-agent systems work best today when **writes stay single-threaded** and the
additional agents **contribute intelligence rather than actions**. Their clean-context
reviewer (no shared context with the coder) catches ~2 bugs per PR, 58% severe — exactly the
`fresh_reviewer` pattern. Their "smart friend" finding: cross-frontier delegation works as a
**capability router** ("route to whichever model is best at the specific sub-task"), which is
the per-role model routing this config encodes. See
https://cognition.com/blog/multi-agents-working

Anthropic's "Effective harnesses for long-running agents" (Nov 2025) shows that longitudinal
continuity is files and prompts, not machinery: a progress file, a feature-list, and git as
memory bridge context windows. See
https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

## Config-Driven Routing

`assets/quality-loop.config.example.json` encodes this matrix as data: each step maps to a
profile, a model placeholder, allowed tools, required artifacts, and the gate that must pass
before the step is considered complete. Orchestrators can read it directly; humans can read
it as documentation. Validate it with:

```bash
python3 scripts/quality_loop.py check-config assets/quality-loop.config.example.json
```
