# Agentic Orchestration

The Coding Quality Loop is **agentic-first**: each lifecycle step is a node that can run on a
different agent, model, or tool profile, so a team picks the best model for each step instead
of forcing one model to do intake, architecture, implementation, and review. This file defines
the routing model; its machine-readable form is `assets/quality-loop.config.example.json`.

Phases and sub-steps are canonical in `references/lifecycle.md`; task classes and roles are
canonical in **SKILL.md** (§Task Classes, §Roles). This file adds only the routing surface.

## The working surface (what the package actually runs)

### Step → profile → model class

Route by *step*, not by vendor: each step has its own cost/capability profile. Deterministic
schema-following steps (intake, explore, verify orchestration, package) go to the cheap/fast
tier; architecture and risk (plan, minimality gate) reward the strongest reasoning; the diff
goes to a code-specialized model; review must be independent. Policy enforcement is never a
model — it is a hook or command guard.

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
| PLAN | INTAKE | `contract_agent` | cheap/fast | task contract | goal + criteria + risk tier present |
| PLAN | EXPLORE | `repo_mapper` | cheap/fast + repo tools | repo map | likely files named |
| PLAN | PLAN | `planner` | strong reasoning | plan | names files + verification |
| PLAN | MINIMALITY_GATE | `minimality_reviewer` | strong reasoning | minimality decision | rung chosen + lower rungs rejected |
| EXECUTE | IMPLEMENT_SLICE | `implementer` | code-specialized | diff | diff scoped to plan |
| EXECUTE | VERIFY | `verification_runner` | cheap/fast + exec | command evidence | evidence matches risk tier |
| REVIEW | REVIEW | `fresh_reviewer` | strong reasoning, **separate session** | review verdict | verdict + findings recorded |
| REVIEW | PACKAGE | `packager` | cheap/fast | PR handoff | handoff complete |
| (all) | policy | `policy_guard` | deterministic hook, **never a model** | block/allow log | no unsafe action passed |

Profiles are named by role, not vendor; map each to whatever your host provides. The
`orchestrator` and `security_reviewer` are mission/boundary roles, not per-step profiles —
wire them in for medium/mission work and at risk boundaries (canonical role table: SKILL.md
§Roles).

### Routing by model: intelligence, taste, cost

The step heuristics route by task *shape*. To route by *model*, name what separates models:

- **Intelligence** — the hardest problem a model carries unsupervised. Governs planning, the
  minimality gate, debugging, risk assessment — where a wrong call costs the most downstream.
- **Taste** — judgment a test cannot catch: public API/SDK surface, UX, naming, copy, whether
  a diff reads the way a senior engineer on this codebase would write it. A model can be highly
  intelligent and still have weak taste.
- **Cost** — price/latency per unit of work. A **tiebreaker only**, never a gate.

Rule of thumb: the orchestrator and the independent reviewer want the highest intelligence
**and** taste (they decide and judge shipped surface); the implementer wants a code-specialized
model that matches conventions; map/verify/package want the cheap/fast tier. Never route real
reasoning or implementation to a minimal-capability tier.

### Escalation and the reasoning-effort ceiling

Model classes are defaults, not ceilings. Use the cheap/fast tier to explore, draft, and gather
information; when its output does not clear the bar, escalate to a more capable model and redo
the work — without asking. Judge the output, not the price tag.

Route reasoning effort at **`high`**. Effort is *per step*, not per-task endurance: a higher
setting does not buy more steps, it makes the model think harder on each one. Above `high`
(`xhigh`, `max`), models second-guess, over-produce, and ship larger diffs at higher cost, and
their reviews get noisier rather than sharper. `check-config` rejects `xhigh`/`max` in
`model_routing` unless the specific model-class block sets `"allow_overthink": true` — an
explicit, greppable escape hatch for a genuinely ambiguous, architecture-sensitive one-off,
never a default and never bulk work.

### Enforced heterogeneity

`check-config` is the arbiter of independence: on medium+ work it verifies the implementer and
the `fresh_reviewer` resolve to a **different model family**, and `verify-gates` string-compares
reviewer ≠ implementer. Independence is enforced on the model identity, not on which CLI ran —
see the decision note below.

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
keeps one driver in control. The default assumes a **strong executor**
(Sonnet-class or better); with a weaker primary (GLM-class) the advisor pattern
underperforms, so keep orchestrator-delegates instead — see the
[Topology decision note](#topology-decision-note-2026) below.

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

Cross-frontier delegation works as a **capability router** — consult whichever model
is best at the specific sub-task, not merely a "smarter" one.

## Risk-Scaled Routing

| Risk tier | Suggested topology |
|---|---|
| `low` | One agent runs the whole loop; `policy_guard` hook stays on. |
| `medium` | Implementer + independent `fresh_reviewer`; `verification_runner` runs real checks. |
| `high` | Dedicated `planner`, `minimality_reviewer`, `implementer`, independent `fresh_reviewer`, plus `policy_guard` enforcing security/migration blocks and human approval. |

Start with **one implementer + one independent reviewer** plus deterministic policy hooks —
that single split captures most of the quality gain. Add a dedicated `planner`/
`minimality_reviewer` for architecturally significant work, a `repo_mapper` for large/unfamiliar
codebases; keep `contract_agent` and `packager` merged into the implementer for low-risk work.
Over-parallelization is an anti-pattern: if coordination cost exceeds the quality gain, collapse
roles back into fewer agents.

## Config-driven model setup

`assets/quality-loop.config.example.json` ships a `model_routing` section mapping each model
class (`cheap_fast`, `strong_reasoning`, `code_specialized`) to a real model identifier and
optional thinking level, per host. Fill it once and `setup-models` applies it through each
host's native mechanism:

| Host | Mechanism | What `setup-models` does |
|---|---|---|
| Claude Code | `.claude/agents/*.md` `model:` + `effort:` frontmatter | rewrites agent files in place |
| Droid | `.factory/droids/*.md` `model:` + `reasoningEffort:` frontmatter | rewrites droid files in place |
| Codex | `config.toml` `model` / `model_reasoning_effort` + per-role `config_file` layers | prints the TOML to add |
| Pi | `/model` commands + thinking levels | prints the commands to run per role |

```bash
cp assets/quality-loop.config.example.json quality-loop.config.json   # fill model_routing
python3 scripts/quality_loop.py setup-models --host claude-code        # apply (or codex/droid/pi)
python3 scripts/quality_loop.py check-config quality-loop.config.json  # validate routing + heterogeneity
python3 scripts/quality_loop.py brief                                  # active routing + drift at session start
```

Agent files ship with `model: inherit` so they are host-neutral at rest. Thinking levels are
generic (`minimal`–`max`) and mapped per host; an unsupported level is warned and omitted and
`setup-models` exits non-zero so CI catches the divergence. `brief` detects drift between the
config and the actual agent-file `model:` values for file-based hosts. Reviewers run in a fresh
session so they do not inherit the implementer's context.

### Per-host role wiring

Roles, prompts, and routing ship as files any host consumes without a custom runtime; each host
expresses the same config through its native mechanism. Per-role prompt cards live in
`assets/prompts/` (`intake.md`, `context-map.md`, `minimality.md`, `planner.md`,
`implementer.md`, `reviewer.md`, `security-reviewer.md`, `package.md`) — any harness or human
can run any role by pasting one card.

| Role | Claude Code | Droid | Codex | Cursor | Pi |
|---|---|---|---|---|---|
| context mapper | `.claude/agents/quality-loop-context-mapper.md` | `.factory/droids/quality-loop-context-mapper.md` | subagent / MCP | `.cursor/rules` chat | `/model <cheap-fast>` |
| planner | `.claude/agents/quality-loop-planner.md` | `.factory/droids/quality-loop-planner.md` | subagent | `.cursor/rules` chat | `/model <strong-reasoning>` |
| implementer | main thread | main session | main session | main session | main session |
| fresh reviewer | `.claude/agents/quality-loop-reviewer.md` | `.factory/droids/quality-loop-reviewer.md` | subagent (fresh) | new chat (fresh) | new Pi session |
| security reviewer | `.claude/agents/quality-loop-security-reviewer.md` | `.factory/droids/quality-loop-security-reviewer.md` | subagent (fresh) | new chat (fresh) | new Pi session |
| policy guard | `.claude/settings.json` hooks | host hooks / CI | `.codex/hooks.json` | host hooks / CI | host hooks / CI |

## Topology decision note (2026)

Two orchestration patterns are now viable, and the ground moved in 2026. Choose by executor
strength:

- **Orchestrator-delegates.** A coordinator spawns worker/reviewer agents and holds shared
  state. This is now **host-native**: Claude Code ships subagents, agent teams, and dynamic
  workflows (2026-05-28) that do exactly this without a custom runtime. The package does not
  execute delegation itself — it supplies the routing data and prompt cards the host wires up.
- **Executor-consults-advisor.** A single strong executor calls a stronger model as an
  in-request advisor (Anthropic's advisor strategy, blog 2026-04-09; `advisor_20260301`). This
  is an **API-level primitive inside one `/v1/messages` request**, *not* something a CLI harness
  can wire — present it as topology insight, not a shipped path.

**Decision rule.** The advisor topology needs a strong executor (Sonnet-class or better);
Cognition found it fails with a weak primary (it broke down with SWE-1.5-class implementers).
So with a GLM-class implementer, **keep orchestrator-delegates**; reserve the advisor pattern
for teams whose executor is already frontier-class and who are working at the API layer.

**Heterogeneity caveat.** Running review on a *different CLI* usually — but not always —
gives you model heterogeneity, because a harness can host another vendor's model (Droid can run
Claude models). Harness difference is not a proxy for model difference: `check-config` remains
the arbiter, comparing the resolved model families, not the CLIs.

A one-page cross-CLI review recipe (claude ⇄ codex ⇄ droid headless commands with verified
flags) is tracked separately; this note is the topology rationale behind it.

## Appendix: host-provided patterns the package does not execute

These are patterns hosts now provide natively. The package documents them and supplies routing
data and prompt cards, but it does **not** run them — wiring them to real models and workers is
the host platform's job (see `philosophy.md`, "What this deliberately is *not*").

- **Mission topology (long-horizon work).** For multi-day/multi-module/multi-repo work, split
  the mission: an orchestrator holds shared state (`context-map.md`, `validation-contract.md`),
  fresh worker agents each take one slice, a fresh validator checks each slice against the
  contract, and the orchestrator turns findings into new fix tasks. **Writes stay
  single-threaded**: concurrent workers must run in isolated git worktrees with non-overlapping
  declared file scopes; if scopes can collide, run serially rather than race the working tree.
  Review at milestone boundaries with fresh context; keep the mission record compact.
  (Pattern: [Factory Missions](https://factory.ai/news/missions-architecture).)
- **Smart friend (optional consult).** The consult-a-stronger-model pattern — triggers,
  constraints, and per-host wiring — is documented above under **Advisor Pattern**, and when it
  works (strong executor only) is the **Topology decision note**. Like mission topology, the
  package documents and routes it but does **not** execute the consult; wiring it to real models
  is the host platform's job.

**What the 2026 research confirms.** Cognition's April 2026 update ("Multi-Agents: What's
Actually Working") validates the core bet: multi-agent systems work best when **writes stay
single-threaded** and the extra agents **contribute intelligence rather than actions**; their
clean-context reviewer catches ~2 bugs per PR, 58% severe — exactly the `fresh_reviewer`
pattern. Anthropic's "Effective harnesses for long-running agents" (Nov 2025) shows
longitudinal continuity is files and prompts — a progress file, a feature list, and git as
memory — not machinery. See https://cognition.com/blog/multi-agents-working and
https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents.
