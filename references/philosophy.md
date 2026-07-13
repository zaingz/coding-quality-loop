# Philosophy

> **Bounded autonomy. Smallest correct change. Evidence over confidence.**

This document is the *why* behind the Coding Quality Loop, and the *how* it becomes durable
artifacts: an **engineering operating system** for coding agents — portable process that makes
agent work consistent, verifiable, and improvable across sessions, models, and platforms. For
the executable lifecycle, see [`lifecycle.md`](lifecycle.md).

## The mantra

Seven lines we keep coming back to. Each is a default the loop encodes, not a slogan.

1. **An engineering operating system, not a clever prompt.** A prompt dies with the session.
   Process artifacts — durable instructions, skills, mission state, gates — survive across
   sessions, models, and platforms. Improve the harness, not the next message.
2. **Bounded autonomy is the product.** The boundary — explicit scope, deterministic evidence,
   independent review — is what makes agent output trustable. More autonomy without a boundary is
   just a larger diff you can't merge.
3. **Ship the smallest correct change.** Prefer deletion, reuse, the standard library, and native
   features before writing new code. Minimalism is a quality property, applied *before* planning
   and again before review — not a cleanup pass.
4. **Evidence over confidence.** "Looks right to me" is not a result. Every acceptance criterion
   is paired with the check that proves it; success is never claimed without evidence or a clear
   explanation of a blocked check.
5. **Deterministic gates over vibes.** When a rule matters, enforce it with a hook or a check.
   Advisory text drifts; a gate either fires or it doesn't.
6. **Repo maps over context stuffing.** Give the agent a concise map of the files, symbols, and
   relationships that matter — then let it request depth on demand. Reading the whole tree is slow
   and degrades the context that's left.
7. **Durable harness changes over repeated chat corrections.** A mistake corrected only in chat
   recurs next session. A mistake turned into a rule, test, hook, checklist, or template does not.

## The problem

Autonomous coding agents are genuinely capable — and they fail in predictable ways the moment one
model owns the entire loop: intake, architecture, implementation, *and* self-review.

- **They overbuild.** Given a one-line bug, an agent will refactor a module, add a dependency, and
  introduce an abstraction nobody asked for. The diff balloons; the blast radius grows.
- **They self-attest.** The same context that wrote the code grades it. Confidence inflates,
  gaps get rationalized, and "I verified this" means "I re-read my own work."
- **They lose context.** Long-horizon work degrades a single context window. Early decisions are
  forgotten, constraints drift, and the agent contradicts itself across a session.
- **They skip evidence.** A claim of "tests pass" is asserted, not shown. There is no failing-then-
  passing artifact, no recorded command, nothing a human can audit.
- **They repeat mistakes.** A correction given in chat is gone next session. The same defect comes
  back because nothing durable changed.

None of these are fixed by a smarter model or a longer prompt. They are fixed by *process*: scope
that is written down, evidence that is recorded, review by a separate agent, and corrections that
become artifacts. That is what this loop is.

## Trends we have observed

The industry is converging — fast — on the same moves, and the loop packages them rather than
invents them: **agent skills** as the portable unit of capability (progressive disclosure);
**durable repo instructions** (`AGENTS.md`, `CLAUDE.md`, `.cursor/rules` — short and accurate
beats long and vague); **mission artifacts** (context map, validation contract, plan, completion
record) for long work; **role separation**, because one context grading its own output is the
dominant failure mode; **independent validation** as a contract checked by a fresh context;
**hooks and policy gates** for the non-negotiables; **repo maps** over context stuffing; and
**eval/improvement loops** that treat the harness — not the prompt — as the unit of iteration,
pinned by regression evals. Two 2026 sharpenings: **harness engineering** is now a named
discipline (context engineering has replaced prompt engineering), and **multi-agent works as
capability routing, not parallel swarms** — writes stay single-threaded, extra agents contribute
intelligence (a clean-context reviewer catches bugs the coder cannot see), and longitudinal
continuity is files (progress file, feature list, git as memory), not machinery. Sources for
each are in Inspirations below.

## Every gate must earn its tokens

Process is not free: a diligent medium loop spends roughly 15–22k tokens of scaffolding before
a line of the codebase is read, and the literature shows harnesses that silently double token
spend while passing every functional check. So each gate is held to the same standard as the
code it guards — an addition or a retention must be justified by a measured eval delta per token
of overhead it imposes, and a deletion is a win to celebrate rather than a regression to fear
(v3.0 cut ~40% of the surface this way and shipped stronger). Context is the scarce resource; the
process must practice the scarcity it preaches.

## Inspirations

We learned from prior art. These are influences on our thinking, cited as inspiration — **not**
endorsements of this project, and not claims of adoption by any of them.

- **Addy Osmani's writing on Agent Skills** — framing skills as the durable, composable unit of
  agent capability.
- **Anthropic Agent Skills & Claude Code** — `SKILL.md` folders, progressive disclosure, memory
  (`CLAUDE.md`), and deterministic hooks.
- **OpenAI Codex skills & `AGENTS.md`** — the skill directory shape and layered, nested durable
  instructions; "short and accurate beats long and vague."
- **Factory Missions** — splitting long work into focused units with fresh agents, shared state,
  validation contracts, and orchestrator/worker/validator roles.
- **Cursor rules** — `.mdc` rule types (Always / Auto Attached / Agent Requested / Manual) as a
  model for scoping when guidance applies.
- **Pi skills** — portable skill discovery across multiple install locations, registered as
  `/skill:name`.
- **Aider's repo map** — the insight that a concise map of the codebase beats stuffing the whole
  tree into context.
- **The OpenAI agent improvement loop** — treating the harness as the unit of iteration, pinned by
  evals.
- **Cognition's multi-agent research** (April 2026, "Multi-Agents: What's Actually Working") —
  the finding that multi-agent works when writes stay single-threaded and other agents contribute
  intelligence; the clean-context reviewer pattern; and cross-frontier delegation as capability
  routing.
- **Anthropic's long-running agent harness** (Nov 2025, "Effective harnesses for long-running
  agents") — the initializer + incremental-session pattern, progress file, feature-list JSON,
  and git as memory for longitudinal continuity.
- **Skill packaging conventions** (e.g. generic `.agents/skills/` layouts) — for portability
  across hosts.
- **YAGNI ("You Aren't Gonna Need It")** — build for the requirement in front of you, not an
  imagined future. The Right-Size Gate is YAGNI operationalized as a pre-implementation step.
- **DRY ("Don't Repeat Yourself")** — every rule, table, and definition lives in one canonical
  place and is pointed to, not copied; duplication in the docs is the same debt as duplication
  in code, and this package holds itself to it.

## How the loop translates this into a package

Inspiration is cheap; a usable, dependency-free package is the work. The loop turns the trends
above into one self-contained Agent Skill:

- A single `SKILL.md` plus optional `assets/`, `references/`, `examples/`, `evals/`, and
  `scripts/`, following the open [Agent Skills specification](https://agentskills.io/specification).
- **Progressive disclosure** so the agent sees the frontmatter always, loads `SKILL.md` when
  relevant, and pulls references/assets/scripts only when a step needs them.
- **Task classes** (tiny → small → medium → mission) so ceremony scales with risk — a typo runs no
  mission artifacts; a payment migration runs the full loop.
- **Templates** for every mission artifact, so the contract and review aren't improvised.
- **An executable, stdlib-only checker** (`scripts/quality_loop.py`) that validates the
  orchestration config, audits diffs, and enforces record gates — evidence you can run, not a
  promise.
- **Offline evals** that assert each gate fires for the right reason, wired into dependency-free
  CI so the claims stay verifiable.
- **Host-native install paths** for Claude Code, Codex, Cursor, Pi, and standalone runtimes, so
  the same philosophy drops into whatever you already use.

## The engineering operating system

Ad-hoc prompting is being replaced by reusable process artifacts. Each converging trend maps to
an artifact this skill ships — prompting → durable instructions, capability → skills, one
context → orchestration, vague verification → validation contract, complexity creep → complexity
discipline, advisory text → deterministic gates, context stuffing → repo maps. Those transitions
land as five concrete parts:

1. **Durable repo instructions** — `AGENTS.md` (global, project, nested overrides — closer
   instructions win), `CLAUDE.md` (project/user/local, imports, `/init`; keep ~200 lines),
   Cursor rules (`.cursor/rules/*.mdc`: Always / Auto Attached / Agent Requested / Manual).
2. **Reusable skills** — focused `SKILL.md` workflows with triggers, steps, and exit criteria;
   the portable capability unit, shareable across hosts.
3. **Mission artifacts** — `context-map.md`, `validation-contract.md`, `plan.md`,
   `execution-log.md`, `decision-log.md`, `completion-record.md`. Shared state that makes
   long-horizon work orchestratable.
4. **Independent verification** — implementer and validator separated for non-trivial work; the
   implementer is never the final validator, and the reviewer runs on a different vendor.
5. **Complexity discipline** — the right-size gate, applied before planning and again before
   review. Canonical rung ladder: SKILL.md §Right-Size Gate.

**Scaling rules.** Default to the smallest task class that safely satisfies the goal (canonical
definitions: SKILL.md §Task Classes). A tiny task must not be forced through mission ceremony; a
medium task must not ship without a validation contract and an independent review; a mission must
keep shared state compact and review at milestone boundaries with fresh context.

**Harness implementation modes** — adopt the lightest that fits, combine as risk grows:
instruction-only (the loop lives in `AGENTS.md` / `CLAUDE.md` / `.cursor/rules`; advisory);
skill-based (a portable skill directory with progressive disclosure); hook-enforced
(deterministic gates — protected-path writes, format/test after edit, dependency approval,
destructive-command blocks, the completion-record shipping gate); and mission agent
(orchestrator + workers + validators, for medium/mission work only).

**The improvement loop.** The harness — not the prompt — is the unit of iteration: collect
signals (traces, validator findings, escaped defects, diff size, evidence rate, repeated
mistakes), rank candidate changes by impact, apply the change as a durable artifact (a rule, a
test, a hook, a checklist item, a template), and pin a regression eval so the fix sticks. Every
repeated failure becomes a durable harness change (canonical: SKILL.md §RETROSPECTIVE), not a
repeated chat correction.

## What this deliberately is *not*

Knowing the non-goals is how the loop stays honest and small.

- **Not a model or an agent runtime.** It does not run models, manage sessions, recover from
  crashes, ingest traces, or hand off work between git workers. Wiring the routed steps to real
  models is the host platform's job.
- **Not a replacement for CI, tests, scanners, or human review.** The helper checks that the
  *evidence* of those runs is present and well-formed; it does not execute your test suite or
  security scanner.
- **Not a provenance or identity system.** Reviewer/implementer separation is compared as strings
  and fresh context is self-attested — it is a discipline, not a cryptographic guarantee.
- **Not a marketplace plugin (yet).** It installs by copying a folder. `gh skill install` works
  only once a maintainer publishes and validates a release.
- **Not process theater.** It refuses to force ceremony onto trivial work. If the smallest correct
  change is a one-line edit, the loop is a one-line edit.
- **Not a vendor lock-in.** It is portable by construction and takes no dependencies, so adopting
  it never traps you in one host.

## The one-sentence version

Produce the smallest correct change, with enough recorded evidence and independent review that a
human can trust it, revert it, or merge it — and turn every repeated mistake into a durable change
to the harness, not a repeated correction in chat.
