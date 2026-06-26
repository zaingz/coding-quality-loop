# Philosophy

> **Bounded autonomy. Smallest correct change. Evidence over confidence.**

This document is the *why* behind the Coding Quality Loop. For the *how* — the five parts, task
classes, and harness modes — see [`engineering-operating-system.md`](engineering-operating-system.md).
For the executable lifecycle, see [`lifecycle.md`](lifecycle.md).

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

The industry is converging — fast — on the same set of moves. The loop is an attempt to package
them coherently rather than invent them.

- **Agent skills as the unit of capability.** Reusable `SKILL.md` workflows with triggers, steps,
  and exit criteria, loaded via progressive disclosure (metadata first, full instructions when
  relevant, extra files on demand) are replacing one-off prompts.
- **Durable repo instructions.** `AGENTS.md`, `CLAUDE.md`, and `.cursor/rules` encode standing
  behavior every run inherits — short and accurate beats long and vague.
- **Mission artifacts for long work.** Broad work is split into focused units backed by shared
  state: context map, validation contract, plan, logs, completion record.
- **Role separation.** Orchestrator / worker / validator splits are emerging because one context
  grading its own output is the dominant failure mode.
- **Independent validation.** Verification is becoming a *contract* — each criterion paired with
  its proof — checked by a fresh context, not the implementer's optimism.
- **Hooks and policy gates.** Deterministic enforcement (`PreToolUse`/`PostToolUse`/`Stop`,
  protected paths, dependency approval) is replacing trust-the-text for the non-negotiables.
- **Repo maps and context engineering.** Concise maps of the codebase are beating context
  stuffing on both cost and quality.
- **Eval and improvement loops.** The harness — instructions, tools, routing, checks — is treated
  as the unit of improvement, with regression evals pinning fixes in place.
- **Platform-specific install surfaces.** The same skill now needs to drop cleanly into Claude
  Code, Codex, Cursor, Pi, and generic `.agents/skills` hosts.

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
- **Skill packaging conventions** (e.g. generic `.agents/skills/` layouts) — for portability
  across hosts.

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
