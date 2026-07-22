# Agentic Orchestration

The Coding Quality Loop is **orchestrator-first**. The main session is the **orchestrator**:
it reasons, holds the state machine, and makes *every* decision — task class, context map,
validation contract, right-size rung, plan, model routing, the verdict on findings, and the
stop-if-unsafe call. Everything else is a **worker**: a bounded, stateless task that receives a
**brief, not context** (canonical definition: SKILL.md §Orchestrator Layer). A
worker never sees the skill, the references, or the repository tour; it does the one job in the
brief and hands back a result the orchestrator judges.

This file defines the routing model; its machine-readable form is
`assets/quality-loop.config.example.json`. Phases and sub-steps are canonical in
**SKILL.md §Lifecycle** (expanded in `references/lifecycle.md`); task classes are canonical in **SKILL.md** (§Task Class); the
canonical role table is **§Role architecture** below. This file adds only the routing surface.

## The routed loop: two hosts, two vendors

The default topology is deliberately small: **one implementer on Claude Code and one independent
reviewer on Codex**, plus deterministic policy hooks. The orchestrator runs the Claude Code
main session; it dispatches the diff to the implementer and the review to a Codex worker on a
**different vendor**, then decides on the findings. That two-vendor split is the load-bearing
part — `check-config` hard-fails a medium+ config where the implementer and reviewer resolve to
the same model family, so "one model grading its own work" cannot happen by accident.

Other hosts (Cursor, Pi, Droid, standalone git/GitHub) are **install targets**: the skill and
gates drop into them cleanly and `setup-models` can wire their model frontmatter, but they sit
*outside* the routed kernel. Droid is a supported install target outside the routed kernel;
delegation to Droid is allowed only when an explicit harness routes it. Use install targets to
run the loop under a single host; reach for the routed two-vendor split when you want enforced
review independence.

## Brief, not context

The orchestrator's core discipline is what it withholds. The canonical one-line definition
lives in SKILL.md §Orchestrator Layer; expanded, a worker brief is one screen:

- **Goal** — the single outcome this worker owns.
- **Contract slice** — only the acceptance criteria and constraints this task touches.
- **Files** — the paths in scope; nothing else.
- **Commands** — how to build, test, and verify.
- **Done-check** — the observable condition that ends the task.

No skill text, no references, no repo tour, no prior worker's transcript. This keeps each
worker's token footprint tiny and its judgment uncontaminated by the orchestrator's running
context — the reviewer in particular must arrive with **fresh context** so it does not inherit
the implementer's confidence.

### Record each hand-off in the delegation ledger

When the [control plane](../docs/control-plane.md) is enabled, the orchestrator should append
one line per worker hand-off to `.quality-loop/delegations.jsonl` — an append-only JSONL ledger,
written at the moment of delegation (not reconstructed afterward). One object per line:

```json
{"ts": "2026-07-13T10:00:00Z", "task_id": "T-42", "role": "reviewer",
 "host": "codex", "model": "gpt-5", "brief_summary": "review the slice diff",
 "expected_agent_name": "reviewer", "session_id": "<worker session id, when known>"}
```

`expected_agent_name` is the name the worker's session will report (the profile/agent handle
the host runs under); the control plane uses it to join the delegation to the session it ran
in and attribute exact token spend. A row MAY also carry an optional `session_id` — the
worker's session id, recorded at the moment of hand-off when the spawning harness knows it;
when present the control plane joins directly by that id and skips the fuzzy time-window
match entirely. This is the only record of *who was asked to do what,
when, and on which model* — the transcripts show what a session did, but only the orchestrator
knows it was a deliberate hand-off. The ledger is metadata only (never the brief's full text),
lives under `.quality-loop/` so it is excluded from the review attestation hash, and a
half-flushed line is skipped by the indexer rather than being fatal.

### Persistent workers (fix rounds); fresh reviewers (always)

Workers are stateless per **slice**, not per message. When review findings come back on a
slice, send the fix brief to the **same implementer worker session** instead of briefing a
fresh one: the brief, the diff it wrote, and the commands it ran are already in that session's
prompt cache, so a follow-up round bills at cache-read rates (~0.1× input) instead of a cold
re-brief, and the worker keeps the working state it built on round one. Hosts with persistent
agent sessions support this natively (Claude Code agent teams / follow-up messages; Codex
`resume`).

Three edges keep the pattern honest:

- **Reviewers never persist.** A reviewer session is consumed by its verdict; every review
  round gets a fresh session — a persistent reviewer inherits its own prior verdict exactly
  the way it must not inherit the implementer's confidence.
- **One ledger row per round, same `session_id`.** Record each follow-up hand-off as its own
  delegation row carrying the same worker `session_id`. Rows sharing a `session_id` are
  follow-up rounds by convention; the control plane links them to the session and attributes
  its tokens exactly once (see `docs/control-plane.md` §Delegation ledger).
- **Escalation ends persistence.** A recorded failing check that triggers a model-tier
  escalation (§Stock Routing) starts a fresh worker on the stronger model; never "continue"
  a failing session onto a new tier.

Persistence is a cost move, never a delegation of judgment: the orchestrator still judges
every round's output.

## Step → profile → model class

Route by *step*, not by vendor: each step has its own cost/capability profile. Deterministic
schema-following steps (intake, explore, verify orchestration, package) go to the cheap/fast
tier; architecture and risk (plan, minimality gate) reward the strongest reasoning; the diff
goes to a code-specialized model; review must be independent. Policy enforcement is never a
model — it is a hook or command guard.

- Intake, routing, and summarization are mostly deterministic. Cheap, fast models do this
  well and keep cost low.
- Planning and risk assessment reward strong reasoning. Spend the capable model here.
- Implementation rewards code-specialized models that follow conventions and keep diffs small.
- Review must be independent. Use a separate vendor, or at least a fresh session, so the
  reviewer does not inherit the implementer's confidence.
- Policy enforcement must be deterministic. Use hooks or command guards, not a model.

## Agent profiles

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
| `fresh_reviewer` | REVIEW: independent diff review vs contract | strong reasoning, separate vendor |
| `packager` | PACKAGE: assemble the PR handoff | cheap/fast, structured output |
| `policy_guard` | Cross-cutting: block unsafe actions | deterministic hook/tool, no model |

## Role architecture

Profiles map onto a small set of roles. The step-profiles above are the per-step handles; the
roles below describe responsibilities and apply across the lifecycle. Add roles only as risk
and class grow (tiny/small need none of the specialist roles).

| Role | Maps to profile(s) | Responsibilities | Independent? |
|---|---|---|---|
| `orchestrator` | the main session (Claude Code) | Reason and decide everything: set scope, classify the task, gather context, write the spec + validation contract, decompose into worker briefs, route models, collect findings, create fix tasks, and **stop if unsafe**. Workers never see its context. | n/a |
| `context_mapper` | `repo_mapper` | Repo layout, relevant modules, entry points, data flow, existing helpers/patterns, tests and commands. Outputs **findings, not raw dumps**. | no |
| `implementer` | `implementer` | One bounded task from a one-screen brief: no speculative abstraction, no unrelated cleanup, smallest meaningful test, a coherent slice. | no |
| `validator` | `fresh_reviewer` | Fresh context, **different vendor**; does **not** implement. Checks acceptance criteria, behavior contract, regression risk, edge cases, and evidence against the validation contract. | **yes** |
| `simplicity_reviewer` | `minimality_reviewer` | Deletion / reuse / stdlib / native / dependency / abstraction review — the right-size gate as a reviewer, run before plan and before review. | optional |
| `security_reviewer` | (boundary only) | Reviews changes at any risk boundary (canonical list: SKILL.md §Task Class). | **yes** |
| `policy_guard` | `policy_guard` | Deterministic safety blocks. Never a model. | enforced |

The `orchestrator` is the main session itself. `security_reviewer` is a boundary role, not a
per-step profile — wire it in at risk boundaries for medium/mission work. The table above is
the canonical role table.

## Default step-to-agent matrix

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
| REVIEW | REVIEW | `fresh_reviewer` | strong reasoning, **different vendor** | review verdict | verdict + findings recorded |
| REVIEW | PACKAGE | `packager` | cheap/fast | PR handoff | handoff complete |
| (all) | policy | `policy_guard` | deterministic hook, **never a model** | block/allow log | no unsafe action passed |

Profiles are named by role, not vendor; map each to whatever your host provides. The
`security_reviewer` is a boundary role, not a per-step profile — wire it in at risk boundaries
(canonical role table: §Role architecture above).

### Model capability glossary

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

**Escalation and the reasoning-effort ceiling.** Model classes are defaults, not ceilings. Use
the cheap/fast tier to explore, draft, and gather information; when its output does not clear
the bar, escalate to a more capable model and redo the work — without asking. Judge the output,
not the price tag.

Route reasoning effort at **`high`**. Effort is *per step*, not per-task endurance: a higher
setting does not buy more steps, it makes the model think harder on each one. Above `high`
(`xhigh`, `max`), models second-guess, over-produce, and ship larger diffs at higher cost, and
their reviews get noisier rather than sharper. `check-config` rejects `xhigh`/`max` in
`model_routing` unless the specific model-class block sets `"allow_overthink": true` — an
explicit, greppable escape hatch for a genuinely ambiguous, architecture-sensitive one-off,
never a default and never bulk work.

A higher-level harness may own effort routing instead of `model_routing`. One user's agent-os
setup (not shipped; see `docs/cross-cli-recipe.md` §One user's setup) does this explicitly:
planning uses max, review/read/computer-use use xhigh, and execution uses high. Keep CQL
routing host-neutral in that topology; `check-config` cannot apply or verify an external
wrapper's effort pin, so the wrapper and supervisor must verify it directly.

### Enforced heterogeneity

`check-config` is the arbiter of independence: on medium+ work it verifies the implementer and
the `fresh_reviewer` resolve to a different concrete model **and** a different model **family**,
across hosts. Family is the explicit `family` field on a `host_models` block when set, else a
well-known-prefix match — the checker recognizes the major vendor prefixes (claude/sonnet/opus/
haiku, gpt/codex, and other vendors) so harness diversity is never mistaken for model
heterogeneity; unknown or BYOK ids are skipped, never failed. This closes the alias hole —
`sonnet` vs `claude-sonnet-4-5` is not two reviewers — and the cross-host hole: running review
on a different CLI is not by itself model diversity. `"allow_same_family": true` is the
explicit, greppable escape hatch for same-family (never same-model) setups. `verify-gates`
additionally string-compares reviewer ≠ implementer on the record.

The same agent-os setup intentionally uses GPT-5.6 Sol in separate Droid implementation and
Codex review sessions. That external same-model route is not model heterogeneity and must
never be reported as if `check-config` proved it. Its independence comes from fresh context, separate hosts, a
non-editing reviewer, deterministic gates, and supervisor verification; CQL `model_routing`
stays host-neutral for this explicit harness-level exception.

## Config-driven model setup

`assets/quality-loop.config.example.json` ships a `model_routing` section mapping each model
class (`cheap_fast`, `strong_reasoning`, `code_specialized`) to a real model identifier and
optional thinking level, per host. Fill it once and `setup-models` applies it through each
host's native mechanism:

| Host | Mechanism | What `setup-models` does |
|---|---|---|
| Claude Code | `.claude/agents/*.md` `model:` + `effort:` frontmatter | rewrites agent files in place |
| Codex | `config.toml` `model` / `model_reasoning_effort` + per-role `config_file` layers | prints the TOML to add |
| Droid | `.factory/droids/*.md` `model:` + `reasoningEffort:` frontmatter | rewrites droid files in place |
| Pi | `/model` commands + thinking levels | prints the commands to run per role |

Claude Code and Codex are the routed loop; Droid and Pi are install targets `setup-models` can
still wire.

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

**Multi-host topologies.** An `agents` entry may be an object `{"host": ..., "class": ...}` to
pin that role to another harness, and `main_session {host, class, model}` declares where the
implementer runs (a declaration only — nothing is rewritten for it; it feeds the heterogeneity
check, `brief`, and print-host output; it must resolve to a host, so set `main_session.host`
or `model_routing.host` — check-config errors on a hostless main session). `setup-models` with
no `--host` then applies every host in the topology: file hosts get frontmatter rewrites; print
hosts (codex, pi) print behind an explicit `PRINT-ONLY — settings not applied or verified by
CQL` banner, and there is no print-host drift detection because their config lives outside the
repo — `brief` says "declared, not verified" instead of pretending. `--host` splits by config
shape: on a single-host config it keeps its historical meaning (retarget the default host); on a
multi-host topology it is a pure filter — it applies only that host's slice and never drags
default-host roles onto the selected host. Three pre-validated variants along the
intelligence↔cost dial (`max-intelligence` / `balanced` / `max-throughput`) ship in
`assets/routing/` with a dated model-menu README; each is pinned by an eval case that requires
`check-config` to pass with the floors held (strong-reasoning tier for plan/review classes,
different-family review, effort at the `high` ceiling).

### Per-host role wiring

Roles, prompts, and routing ship as files any host consumes without a custom runtime; each host
expresses the same config through its native mechanism. Per-role prompt cards live in
`assets/prompts/` (`intake.md`, `context-map.md`, `minimality.md`, `planner.md`,
`implementer.md`, `reviewer.md`, `security-reviewer.md`, `package.md`) — any harness or human
can run any role by pasting one card. Claude Code (implementer) and Codex (reviewer) are the
routed loop; the remaining columns are install-target conveniences.

| Role | Claude Code | Codex | Droid | Cursor | Pi |
|---|---|---|---|---|---|
| context mapper | `.claude/agents/quality-loop-context-mapper.md` | subagent / MCP | `.factory/droids/quality-loop-context-mapper.md` | `.cursor/rules` chat | `/model <cheap-fast>` |
| planner | `.claude/agents/quality-loop-planner.md` | subagent | `.factory/droids/quality-loop-planner.md` | `.cursor/rules` chat | `/model <strong-reasoning>` |
| implementer | main session | main session | main session | main session | main session |
| fresh reviewer | `.claude/agents/quality-loop-reviewer.md` | subagent (fresh) | `.factory/droids/quality-loop-reviewer.md` | new chat (fresh) | new Pi session |
| security reviewer | `.claude/agents/quality-loop-security-reviewer.md` | subagent (fresh) | `.factory/droids/quality-loop-security-reviewer.md` | new chat (fresh) | new Pi session |
| policy guard | `.claude/settings.json` hooks | `.codex/hooks.json` | host hooks / CI | host hooks / CI | host hooks / CI |

## Risk-scaled routing

| Risk tier | Suggested topology |
|---|---|
| `low` | One agent runs the whole loop; `policy_guard` hook stays on. |
| `medium` | Implementer (Claude Code) + independent `fresh_reviewer` (Codex); `verification_runner` runs real checks. |
| `high` | Dedicated `planner`, `minimality_reviewer`, `implementer`, independent `fresh_reviewer`, plus `policy_guard` enforcing security/migration blocks and human approval. |

Start with **one implementer + one independent reviewer** plus deterministic policy hooks —
that single split captures most of the quality gain. Add a dedicated `planner`/
`minimality_reviewer` for architecturally significant work, a `repo_mapper` for large/unfamiliar
codebases; keep `contract_agent` and `packager` merged into the implementer for low-risk work.
Over-parallelization is an anti-pattern: if coordination cost exceeds the quality gain, collapse
roles back into fewer agents.

## Mission topology (long-horizon work)

For multi-day/multi-module/multi-repo work, the orchestrator/worker split scales up: the
orchestrator holds shared state (`context-map.md`, `validation-contract.md`), fresh worker
agents each take one slice from a bounded brief, a fresh validator checks each slice against the
contract, and the orchestrator turns findings into new fix tasks. **Writes stay
single-threaded**: concurrent workers must run in isolated git worktrees with non-overlapping
declared file scopes; if scopes can collide, run serially rather than race the working tree.
Review at milestone boundaries with fresh context; keep the mission record compact. (Pattern:
[Factory Missions](https://factory.ai/news/missions-architecture).) Claude Code ships subagents,
agent teams, and dynamic workflows that wire this host-natively — the package supplies the
routing data and prompt cards; the host runs the delegation. The research grounding for this
topology (single-threaded writes, clean-context reviewer, files-as-continuity) is cited in
`references/philosophy.md` §Inspirations.

## Cross-CLI recipe

The one-page cross-CLI recipe (claude ⇄ codex headless commands with verified flags) lives at
`docs/cross-cli-recipe.md`; running review on a different CLI usually gives model heterogeneity
because a harness can host another vendor's model, but harness difference is not a proxy for
model difference — `check-config` remains the arbiter, comparing resolved model families, not
the CLIs.
