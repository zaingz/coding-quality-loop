# Agentic Orchestration

The Coding Quality Loop is **agentic-first**: each lifecycle step is a node that can be
run by a different agent, model, or tool profile. Teams pick the best model for each use
case instead of forcing one model to do intake, architecture, implementation, and review.

The canonical lifecycle is three phases — **PLAN → EXECUTE → REVIEW** (see
`references/lifecycle.md`) — and every step below is a sub-step of one of those phases:
`contract_agent`, `repo_mapper`, `planner`, and `minimality_reviewer` run during **PLAN**;
`implementer` and `verification_runner` run during **EXECUTE**; `fresh_reviewer` and
`packager` run during **REVIEW**. Roles are still mapped by step, not by phase, because a
step is the smallest unit that has its own model-selection heuristic.

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
| `simplicity_reviewer` | `minimality_reviewer` | Deletion / reuse / stdlib / native / dependency / abstraction review — the right-size gate as a reviewer, run before plan and before review. | optional |
| `security_reviewer` | (boundary only) | Reviews changes at risk boundaries: auth, permissions, secrets, payments, PII, migrations, upload/download, network, shell, dependency changes. | **yes** |
| `advisor` | (on-demand, small/medium default) | Consulted by the executor at reasoning walls; returns guidance, **never code and never tool calls**; capped at `max_uses` ≈ 3. See the Advisor Pattern below. | consulted |
| `policy_guard` | `policy_guard` | Deterministic safety blocks. Never a model. | enforced |

The `orchestrator` and `security_reviewer` are not per-step profiles in the base config; they
are mission/boundary roles. Wire them in for medium/mission work and at risk boundaries. The
`advisor` is not a step either — it is an on-demand consult the executor invokes at reasoning
walls, and it is the default topology below high-risk (see Advisor Pattern).

## Default Step-to-Agent Matrix

The `Phase` column shows which of the three canonical phases (PLAN / EXECUTE / REVIEW) each
machine-name step belongs to; see `references/lifecycle.md` for the full mapping.

| Phase | Step | Profile | Default model class | Required artifacts | Gate |
|---|---|---|---|---|---|
| PLAN | INTAKE | `contract_agent` | cheap/fast | task contract | contract has goal, criteria, risk tier |
| PLAN | EXPLORE | `repo_mapper` | cheap/fast | repo map | likely files named |
| PLAN | PLAN | `planner` | strong reasoning | plan | plan names files + verification |
| PLAN | MINIMALITY_GATE | `minimality_reviewer` | strong reasoning | minimality decision | rung chosen + lower rungs rejected |
| EXECUTE | IMPLEMENT_SLICE | `implementer` | code-specialized | diff | diff scoped to plan |
| EXECUTE | VERIFY | `verification_runner` | cheap/fast + exec | command evidence | evidence matches risk tier |
| REVIEW | REVIEW | `fresh_reviewer` | strong reasoning (separate session) | review verdict | verdict + findings recorded |
| REVIEW | PACKAGE | `packager` | cheap/fast | PR handoff | handoff complete |
| (all) | (all) | `policy_guard` | deterministic hook | block/allow log | no unsafe action passed |

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

## Model capability glossary

The step heuristics above route by *task shape*. To route by *model*, an orchestrator also
needs a shared vocabulary for what separates models. Define these terms once so routing
decisions are explicit rather than folklore:

- **Intelligence** — the hardest problem a model can carry unsupervised. Governs planning,
  the minimality gate, debugging, and risk assessment, where a wrong call costs the most
  downstream.
- **Taste** — judgment on the things a test cannot catch: public API/SDK surface, UX, naming,
  copy, and whether a diff reads the way a senior engineer on this codebase would write it.
  A model can be highly intelligent and still have weak taste (e.g. solve any problem but
  write your TypeScript like a Python dev).
- **Cost** — price/latency per unit of work. A **tiebreaker only**, never a gate.

Routing rule of thumb: the orchestrator and the independent reviewer want the highest
intelligence **and** taste (they decide and they judge shipped surface); the implementer
wants a code-specialized model that matches conventions; deterministic map/verify/package
steps want the cheap, fast tier. Never route real reasoning or implementation to a
minimal-capability tier — cheap-fast is for schema-following steps, not for problems that
reward thought.

## Reasoning effort ceiling

Route reasoning effort at **`high`**. Effort is *per step*, not per-task endurance: a higher
setting does not let a model take more steps or work longer on a 500-step task — it makes the
model think harder on *every individual step*. Above `high` (`xhigh`, `max`, and equivalents),
models tend to second-guess themselves, over-produce, and ship larger diffs than the task
warranted, at materially higher cost, and their reviews get noisier rather than sharper.

`high` is the ceiling for routine routing. `check-config` rejects `xhigh`/`max` in
`model_routing` unless the specific model-class block sets `"allow_overthink": true` — an
explicit, greppable escape hatch reserved for a genuinely ambiguous, architecture-sensitive
one-off, never a default and never bulk work.

## Escalation policy

Model classes are defaults, not ceilings. Use the cheap, fast tier to *explore, draft, and
gather information*; when its output does not clear the bar, escalate to a more capable model
and redo the work — without asking. Judge the output, not the price tag: escalating a single
task costs far less than shipping mediocre work and reworking it later. This is why cost is a
tiebreaker rather than a gate — it should never prevent using the right model for a step that
ships.

## Advisor Pattern (default for small/medium)

The `advisor` role is the **default topology below high-risk**: a cheap executor
drives the entire loop and consults a stronger reasoning model *only at reasoning
walls*. This is Anthropic's advisor-tool pattern
([advisor tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool)),
which converges with the "smart friend" finding from Cognition's multi-agent
research (April 2026). The advisor gets a fork of the executor's context and returns
**reasoning, never code and never tool calls** — the executor stays in control and
acts on the advice. Prefer this to a full multi-agent split until the task is
genuinely high-risk: it is cheaper than routing every step to a strong model and
keeps one driver in control.

**Triggers (reasoning walls):**
- 2 failed repair attempts on the same issue.
- Merge conflicts or ambiguous integration points.
- Architecture uncertainty where the chosen approach may not hit the perf/correctness target.

**Constraints:**
- The advisor **never calls tools** — it reads the forked context and returns guidance.
- Cap consultations at **`max_uses` ≈ 3**. Hitting the cap is a signal to escalate
  (split roles, add a reviewer, or stop for human input), not to keep paying for
  back-and-forth.

**Config.** The optional `advisor` block in `quality-loop.config.example.json` carries
`enabled_for` (task classes, default `["small","medium"]`), `executor_model_class`,
`advisor_model_class`, `advisor_calls_tools: false`, and `max_uses`.

**Per-host wiring:**
- **Claude Code**: subagent with a stronger model (e.g., Opus) invoked via the Task tool.
- **Droid (Factory)**: Task tool with a stronger model droid.
- **Codex**: subagent with a higher thinking level.

**Key insight from Cognition:** the pattern works best when the advisor is genuinely
stronger. Cross-frontier delegation (Claude + GPT together) works as a **capability
router**: consult whichever model is best at the specific sub-task, not just a
"smarter" one.

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
  ├─ simplicity_reviewer   -> right-size gate before review
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

## Config-Driven Model Setup

The config ships a `model_routing` section that maps each model class
(`cheap_fast`, `strong_reasoning`, `code_specialized`) to a real model identifier and
optional thinking level, per host. Fill it once and `setup-models` applies it through each
host's native mechanism:

| Host | Mechanism | What `setup-models` does |
|---|---|---|
| Claude Code | `.claude/agents/*.md` `model:` + `effort:` frontmatter | Rewrites agent files in place |
| Droid | `.factory/droids/*.md` `model:` + `reasoningEffort:` frontmatter | Rewrites droid files in place |
| Codex | `config.toml` `model` / `model_reasoning_effort` + per-role `config_file` layers | Prints the TOML to add (no file writes) |
| Pi | `/model` commands + thinking levels | Prints the commands to run per role (no file writes) |

Workflow:

```bash
# 1. Copy the example to your repo root and fill model_routing (set host, adjust your block)
cp assets/quality-loop.config.example.json quality-loop.config.json

# 2. Apply (rewrites frontmatter for claude-code/droid; prints for codex/pi)
python3 scripts/quality_loop.py setup-models --host claude-code
python3 scripts/quality_loop.py setup-models --host droid
python3 scripts/quality_loop.py setup-models --host codex
python3 scripts/quality_loop.py setup-models --host pi

# 3. Check the active routing and drift at session start
python3 scripts/quality_loop.py brief
```

Agent files ship with `model: inherit` so they are host-neutral at rest; `setup-models`
writes the configured identifiers. For Codex, copy the printed TOML into `~/.codex/config.toml`
(or a trusted `.codex/config.toml`) and create the per-role `config_file` layer files. For Pi,
run the printed `/model` commands before each role; reviewers run in a fresh session so they
do not inherit the implementer's context.

Thinking levels are represented generically (`minimal`-`max`) and mapped per host. An
unsupported level for a host is warned and omitted; `setup-models` exits non-zero so CI
catches the divergence. `brief` detects drift between the config and the actual agent-file
`model:` values for file-based hosts.

