# Coding Quality Loop

**Bounded autonomy for coding agents.** Stop agents from turning a vague ticket into a big,
unverified diff — make them ship the *smallest correct change* with a task contract, validation
evidence, and an independent fresh-context review.

`coding-quality-loop` is a portable [Agent Skill](https://agentskills.io/specification): one
`SKILL.md` plus optional `assets/`, `references/`, `scripts/`, and `evals/`. It works as a
copy-paste prompt, a loadable skill, or a multi-agent orchestration config — on Claude Code,
Codex, Cursor, Pi, and any custom agent runtime.

![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Agent Skills spec](https://img.shields.io/badge/agent--skills-spec%20compatible-blue)
![Offline evals](https://img.shields.io/badge/offline%20evals-9%2F9%20cases%20%2B%2015%2F15%20gates-brightgreen)
![Dependencies](https://img.shields.io/badge/runtime%20deps-none%20(stdlib%20only)-lightgrey)

---

## The problem

Autonomous coding agents are useful right up until they aren't. One model does intake,
architecture, implementation, *and* self-review — so it inflates its own confidence, skips
evidence, over-engineers, and produces a large diff you can't trust enough to merge or revert.

The fix isn't "more autonomy." It's **bounded autonomy**: explicit scope, deterministic
evidence, and review by a separate agent. That boundary is the product.

### Before / after

A risky one-liner like *"fix the checkout retry bug"* normally becomes a sprawling diff with a
"looks right to me" sign-off. With this loop it becomes:

| Step | What the agent produces |
|---|---|
| Task contract | goal, acceptance criteria, constraints, risk tier (`medium`) |
| Context map | the 2–3 relevant files, callers, and tests — not the whole tree |
| Minimality decision | smallest safe "rung" chosen; bigger rewrites explicitly rejected |
| Small diff | one focused change, existing conventions, no new deps |
| Verification evidence | failing-then-passing regression test + typecheck, recorded |
| Independent review | a *separate* agent checks the diff against the contract → approve |
| Handoff | PR summary with evidence table, risk note, and a one-line rollback |

See it end to end in [`examples/walkthrough/`](examples/walkthrough/README.md).

### Who it's for

Issue-to-PR agents, autonomous coding agents, repo-aware assistants, and multi-agent
engineering workflows — and the teams who need those changes to be reviewable and reversible.

### When *not* to use it

Tiny tasks stay tiny. A typo or one-line config edit runs the smallest possible loop with **no
mission artifacts** — the skill matches ceremony to risk and refuses process theater (see
[Task Classes](SKILL.md#task-classes-default-to-the-smallest-that-is-safe)).

---

## 30-second start

No install required — paste the skill into one rule/system prompt and invoke it:

```bash
# Option A — no install: copy the skill into your agent's instructions and prompt it
#   "Follow the Coding Quality Loop. Ship the smallest correct change with validation evidence."

# Option B — install as a portable Agent Skill (works on Pi, Codex, and any skills-aware host)
cp -r . ~/.agents/skills/coding-quality-loop

# Option C — drive the orchestrated, multi-agent config from any runtime
python3 scripts/quality_loop.py check-config assets/quality-loop.config.example.json
```

Then invoke it: *"Follow the Coding Quality Loop to fix the invoice rounding bug and open a PR."*

---

## Install & use matrix

Pick your host. Full copy-paste files live in [`examples/`](examples/). All paths below are real
files in this repo.

| Host | Install | Invoke |
|---|---|---|
| **Claude Code** | `cp examples/claude-code/CLAUDE.md ./CLAUDE.md` (or `/init`, then paste the loop) | `claude "Follow the Coding Quality Loop to fix the failing test and open a PR."` |
| **Codex** | `cp examples/codex/AGENTS.md ./AGENTS.md` | `codex "Follow the Coding Quality Loop in AGENTS.md to fix the bug."` |
| **Cursor** | `cp -r examples/cursor/.cursor ./.cursor` → rule at `.cursor/rules/coding-quality-loop.mdc` | in chat: `@coding-quality-loop fix the retry bug with verification evidence` |
| **Pi** | `cp -r . ~/.agents/skills/coding-quality-loop` (or in-repo `.agents/skills/`) | `/skill:coding-quality-loop implement the change with a validation contract and independent review` |
| **Standalone / custom agent** | route each step from `assets/quality-loop.config.example.json` | follow [`examples/standalone/run-quality-loop.md`](examples/standalone/run-quality-loop.md) |
| **GitHub `gh skill` / generic `.agents/skills`** | copy the folder into `.agents/skills/coding-quality-loop/`; `gh skill install` works once a release is published (see [Release & pinning](#release--pinning)) | host-native invocation (`/skill:`, `$skill`, etc.) |

> **Honesty note:** this repo is **not** yet published to a plugin marketplace, and
> `gh skill install zaingz/coding-quality-loop` only works after a maintainer publishes and
> validates a release. The copy-to-folder paths above always work today.

### Install vs. no-install

- **No install** — paste the [Minimal Drop-In Prompt](SKILL.md#minimal-drop-in-prompt) or a host
  rule file. Zero scripts, zero config. Best for trying it on one task.
- **Install** — copy the skill folder so the agent can pull `references/`, `assets/` templates,
  and the state-record schema *on demand* via progressive disclosure. Best for repeated use.
- **Orchestrated** — adopt `assets/quality-loop.config.example.json` and route each lifecycle
  step to a role-based agent profile. Best for multi-agent / production setups.

---

## What's in the box (packaging & structure)

A single Agent Skill package following the open
[Agent Skills specification](https://agentskills.io/specification): `SKILL.md` at the root plus
optional sibling folders. **Progressive disclosure** is the core mechanism — the agent sees the
frontmatter `name`/`description` always, loads the full `SKILL.md` when relevant, and pulls
references/assets/scripts only when a step needs them.

```
coding-quality-loop/
├── SKILL.md            # the skill: when-to-use, lifecycle, task classes, roles, gates
├── assets/             # templates + schemas loaded on demand (task contract, validation
│                       #   contract, plan, logs, completion record, PR summary, config schema)
├── references/         # deep-dive docs pulled only when needed (lifecycle, orchestration,
│                       #   reviewer checklists, tool contracts, engineering-OS rationale)
├── examples/           # host-native copy-paste files: claude-code, codex, cursor, pi,
│                       #   standalone, and a full before/after walkthrough
├── evals/              # offline eval cases + harness that prove the gates actually fire
└── scripts/            # quality_loop.py — stdlib-only helper (no third-party deps)
```

Because the package is self-contained and dependency-free, copying the folder into any
skills-aware host *is* the install. There is no build step.

---

## Why agentic-first

One model grading its own work is the common failure mode. This skill splits the loop into
role-based profiles — `orchestrator`, `context_mapper`, `planner`, `minimality_reviewer`,
`implementer`, `verification_runner`, `fresh_reviewer`/`validator`, `security_reviewer`,
`packager`, `policy_guard` — and lets you map each role to the best available model. Defaults
stay simple: **one implementer + one independent validator + deterministic policy hooks.** Add
specialized agents only when risk justifies it. See
[`references/agentic-orchestration.md`](references/agentic-orchestration.md) and
[`references/engineering-operating-system.md`](references/engineering-operating-system.md).

The canonical 10-step lifecycle (intake, context map, spec/validation contract, complexity
brake, plan, implement in small slices, verify, independent review, ship/handoff, retrospective)
routes **8 machine steps** (`INTAKE`, `EXPLORE`, `PLAN`, `MINIMALITY_GATE`, `IMPLEMENT_SLICE`,
`VERIFY`, `REVIEW`, `PACKAGE`); the *spec/validation contract* and *retrospective* phases are
enforced as artifact and rule gates rather than separately routed model steps (mapping table in
`SKILL.md`).

---

## Proof / evidence

The differentiator is that the gates are **executable**, not advisory. `scripts/quality_loop.py`
is a portable, stdlib-only checker you can run right now:

```bash
# 1. Byte-compile the helper and eval harness
python3 -m py_compile scripts/*.py evals/*.py

# 2. Validate the orchestration config
python3 scripts/quality_loop.py check-config assets/quality-loop.config.example.json

# 3. Run the static eval cases (one per risk/behavior scenario)
python3 scripts/quality_loop.py eval-cases evals/cases --config assets/quality-loop.config.example.json

# 4. Run the behavioral eval harness (asserts each gate fires for the right reason)
python3 evals/run_evals.py
```

Current result on a clean checkout: **9/9 static eval cases pass** and **15/15 behavioral
gate cases pass.** The cases cover real scenarios rather than generic productivity claims:

- low-risk docs change, medium multifile behavior change, high-risk migration + security escalation
- the over-engineering trap (minimality brake catches an unnecessary dependency)
- tiny task that must *not* require mission artifacts
- medium work that requires a validation contract + independent review
- security boundary that triggers a distinct reviewer and a hard gate
- a repeated mistake that must become a durable harness update

A lightweight, dependency-free GitHub Actions workflow
([`.github/workflows/evals.yml`](.github/workflows/evals.yml)) runs all four checks on every push
and PR, so the "evals pass" claim is continuously verifiable.

### Per-record gates

For medium/high-risk work, create and audit a state record:

```bash
python3 scripts/quality_loop.py init-record --goal "Fix checkout retry bug" --risk-tier medium --output agent-record.json
python3 scripts/quality_loop.py diff-audit --base origin/main
python3 scripts/quality_loop.py verify-gates agent-record.json
```

---

## What the helper enforces (and what it does not)

`scripts/quality_loop.py` complements — it does **not** replace — CI, tests, security scanners,
and human review. Be precise about what its gates actually verify.

**Enforced today (`verify-gates` / `check-record`):**

- Non-trivial work (medium/mission class, medium/high risk, or security-sensitive) requires a
  named implementer, a validation contract, an independent review, and — at `package`/`done` —
  a completion record.
- **Deep artifact validation.** A validation contract or completion record is accepted only if
  it is a string path to a file that exists, or an inline object with real content (goal,
  acceptance criteria, evidence). Bare booleans, numbers, empty strings, nonexistent paths, and
  shape-only placeholders (e.g. `{"placeholder":"yes"}`) are rejected.
- **Independent review integrity.** The reviewer must be named, distinct from the implementer,
  working with fresh context, must not have patched the code, and must record an approving
  verdict with no unresolved blocking findings. High-risk/security-sensitive work additionally
  requires a distinct security review.
- **Repeated-failure → durable harness change.** If a record sets `repeated_failure: true` or
  `repair_attempts >= 2`, it must carry a `harness_update` (a rule/test/hook/checklist/template
  change) as retrospective evidence — so a clean final record cannot hide a repeated mistake
  that was only corrected in chat.
- Risk-tier-appropriate executable checks, no failed/unclassified commands, a recorded
  minimality decision, and `diff-audit` flags for secrets, dependency edits, migrations, and
  oversized diffs.

**Not enforced (by design, to stay portable):**

- It does not run real test suites, type checkers, or security scanners — it checks that the
  *evidence* of those runs is present and well-formed.
- Reviewer/implementer identity is compared as trimmed strings; it is not verified against
  session or cryptographic provenance, and fresh context is self-attested.
- It is **not** a full mission-agent runtime: no automatic recovery, telemetry, trace ingestion,
  or git-based worker handoff. The config describes routing for 8 machine steps; wiring those to
  real models/sessions is the host platform's job.
- Deterministic blocking of dangerous tool calls (the `policy_guard`) is documented but must be
  wired as host hooks (e.g. Claude Code `PreToolUse`/`Stop`); the helper does not intercept tool
  calls itself.

---

## Release & pinning

Skills are executable instruction/resource bundles, so treat them like any dependency:

- **Inspect before you install.** Read `SKILL.md` and `scripts/quality_loop.py` — there is no
  hidden network access or build step; the helper is stdlib-only.
- **Pin for team use.** Install from a tagged release or a pinned tree SHA rather than a moving
  branch, so everyone's agents load the same gates. The current packaged version is recorded in
  `SKILL.md` frontmatter (`metadata.version`) and tracked in [`CHANGELOG.md`](CHANGELOG.md).
- **Enforce the non-negotiables with hooks.** Advisory text is not a guarantee — wire the
  `policy_guard` rules (secrets, destructive migrations, auth/billing, diff-size limits) as
  deterministic host hooks for anything you cannot afford an agent to get wrong.

---

## How this maps to official docs

Portable, but aligned with how today's platforms load instructions and enforce policy:

- **Claude Code memory** — project/user/local `CLAUDE.md`, `.claude/rules/`, `@path` imports,
  `/init`. https://docs.anthropic.com/en/docs/claude-code/memory
- **Claude Code hooks** — `PreToolUse` / `PostToolUse` / `Stop` hooks in a shareable
  `.claude/settings.json` are the deterministic `policy_guard`.
  https://docs.anthropic.com/en/docs/claude-code/hooks
- **Codex `AGENTS.md`** — global `~/.codex/AGENTS.md`, project `AGENTS.md`, nested overrides.
  https://developers.openai.com/codex/guides/agents-md
- **Codex skills** — `SKILL.md` directories with optional scripts/references/assets; progressive
  disclosure keeps context small. https://developers.openai.com/codex/skills
- **Cursor rules** — `.cursor/rules` in `.mdc` format (Always / Auto Attached / Agent Requested /
  Manual), referenced via `@ruleName`. https://docs.cursor.com/en/context/rules
- **Pi skills** — loaded from `~/.pi/agent/skills/`, `~/.agents/skills/`, `.pi/skills/`,
  `.agents/skills/`, or settings; registered as `/skill:name`. https://pi.dev/docs/latest/skills
- **Anthropic Agent Skills** — `SKILL.md` folders with optional scripts/resources and progressive
  disclosure. https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- **Agent Skills specification** — the open, cross-agent package shape this repo targets.
  https://agentskills.io/specification

The design also draws on Factory Missions (long work split into focused units with fresh agents
and validation contracts), the Aider repo map (concise maps beat context stuffing), and the
OpenAI agent improvement loop (the harness is the unit of improvement).

---

## Philosophy

The goal is **bounded autonomy**: small diffs, explicit contracts, deterministic evidence, and
fresh-context review by an independent agent. The loop should not overcomplicate by default, and
it should never claim success without verification evidence or a clear explanation of blocked
checks. The agent's job is not to maximize autonomy — it is to produce the smallest correct
change with enough evidence that a human can trust, review, revert, or merge it.

## License

MIT — see [LICENSE](LICENSE).
