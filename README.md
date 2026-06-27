<div align="center">

# Coding Quality Loop

### Make your AI coding agent ship changes you can trust — not giant diffs you have to babysit.

[![License: MIT](https://img.shields.io/badge/license-MIT-111111?style=flat-square)](LICENSE)
[![version](https://img.shields.io/badge/version-1.4.0-111111?style=flat-square)](CHANGELOG.md)
[![Agent Skills spec](https://img.shields.io/badge/agent--skills-spec%20compatible-111111?style=flat-square)](https://agentskills.io/specification)
[![evals](https://github.com/zaingz/coding-quality-loop/actions/workflows/evals.yml/badge.svg)](https://github.com/zaingz/coding-quality-loop/actions/workflows/evals.yml)
[![offline gates](https://img.shields.io/badge/offline%20gates-9%2F9%20%2B%2026%2F26%20%2B%2020%2F20-111111?style=flat-square)](evals/)
[![runtime deps](https://img.shields.io/badge/runtime%20deps-none-111111?style=flat-square)](scripts/quality_loop.py)
[![hosts](https://img.shields.io/badge/works%20with-Claude%20Code%20·%20Codex%20·%20Cursor%20·%20Pi-111111?style=flat-square)](#install--use-matrix)

</div>

AI coding agents are fast — but point one at a vague ticket and it will refactor things nobody
asked for, pull in a dependency you didn't want, claim "tests pass" without showing them, and sign
off on its own work. You're left holding a big change you can't tell is correct.

**Coding Quality Loop makes the agent work like a careful engineer instead.** It pins down what
"done" means before writing any code, changes as little as possible, proves the change with a test
you can actually see, and has a *separate* agent review the work before it reaches you. What comes
back is small, checked, and reversible — something you can read, trust, and merge in minutes.

It's a portable [Agent Skill](https://agentskills.io/specification) — drop it into Claude Code,
Codex, Cursor, Pi, or any skills-aware host as a copy-paste prompt, a loadable skill, or a
multi-agent config. No new tools, no lock-in.

---

**Contents** ·
[What's different](#whats-different) ·
[Quickstart](#quickstart-30-seconds) ·
[The loop](#the-loop) ·
[What it enforces (and what it doesn't)](#what-it-enforces--and-what-it-deliberately-does-not) ·
[Project memory](#project-memory) ·
[Proof you can run](#proof-you-can-run) ·
[Install matrix](#install--use-matrix) ·
[What's in the box](#whats-in-the-box) ·
[How it compares](#how-it-compares) ·
[FAQ](#faq) ·
[Philosophy](#philosophy)

---

## What's different

Same agent, same model — the difference is the process wrapped around it.

You ask your agent to *"fix the checkout retry bug."*

| Without the loop | With the loop |
|---|---|
| a sprawling diff across many files | a focused fix in one or two files |
| a new dependency you didn't ask for | no new dependencies |
| "looks right to me" | a test that **fails before the fix and passes after** — shown, not claimed |
| you review it cold, by yourself | a *second* agent already checked it against the goal |
| hope you can undo it | a one-line rollback, written down |
| relearns the same lesson next session | remembers it — and recalls it next time |

That's the whole idea: smaller changes, real proof, a second set of eyes, and memory that
sticks — so you read, trust, and merge in minutes instead of babysitting. The work also scales to the risk: a typo just
gets fixed; a payment migration runs the full process. See a real worked example in
[`examples/walkthrough/`](examples/walkthrough/README.md).

<details>
<summary>What the agent actually produces, step by step (for the curious)</summary>

| Step | What the agent produces |
|---|---|
| Task contract | goal, acceptance criteria, constraints, risk tier |
| Context map | the 2–3 relevant files, callers, and tests — not the whole tree |
| Minimality decision | the smallest safe change; bigger rewrites explicitly rejected |
| Small diff | one focused change, existing conventions, no new deps |
| Verification evidence | a failing-then-passing test + typecheck, recorded |
| Independent review | a separate agent checks the diff against the contract → approve |
| Handoff | a PR summary with an evidence table, a risk note, and a one-line rollback |

The state record in the walkthrough passes the same [`verify-gates`](scripts/quality_loop.py)
check the loop enforces — the proof isn't just prose.

</details>

---

## Quickstart (30 seconds)

No install required — paste the skill into one rule/system prompt and invoke it.

```bash
# A — no install: copy the skill into your agent's instructions, then prompt it
#   "Follow the Coding Quality Loop. Ship the smallest correct change with validation evidence."

# B — install as a portable skill (Claude Code shown; see the matrix for other hosts)
cp -r . .claude/skills/coding-quality-loop        # project scope
#   ~/.claude/skills/coding-quality-loop           # or user scope

# C — drive the orchestrated, multi-agent config from any runtime
python3 scripts/quality_loop.py check-config assets/quality-loop.config.example.json
```

Then: *"Use the coding-quality-loop skill to fix the invoice rounding bug and open a PR."*

---

## The loop

Ten stages, smallest-safe-first. The **complexity brake runs twice** — once to choose the
smallest approach, once to confirm nothing crept in before review.

```text
  ┌─ INTAKE ──────── task contract: goal, acceptance criteria, risk tier
  ├─ CONTEXT MAP ─── the 2–3 files that matter, callers, tests — not the whole tree
  ├─ VALIDATION ──── write down what "done" means, before writing code
  ├─ COMPLEXITY ──── pick the smallest valid rung; reject bigger rewrites with reasons
  ├─ PLAN ────────── files to change, slices, verification commands, rollback
  ├─ IMPLEMENT ───── one small, reviewable, revertible slice at a time
  ├─ VERIFY ──────── run the smallest sufficient checks; record exact commands + results
  ├─ REVIEW ──────── a separate agent checks the diff against the contract, in fresh context
  ├─ SHIP ────────── PR handoff + completion record (the shipping gate)
  └─ RETROSPECT ──── turn every repeated mistake into a durable harness change, not a chat fix
```

Across tasks, those durable lessons can persist in an optional
[per-project memory](#project-memory) — so the agent recalls them next time instead of
relearning them.

### Ceremony scales with risk

A tiny task must **not** be forced through mission ceremony. A medium task must **not** ship
without a validation contract and an independent review. ([Task classes →](SKILL.md#task-classes-default-to-the-smallest-that-is-safe))

| Class | Looks like | Process |
|---|---|---|
| **Tiny** | typo, one-line config, obvious test update | inspect, edit, smallest check. No mission artifacts. |
| **Small** | local bug, one module, low risk | quick context map, mini spec, minimal fix, targeted test. |
| **Medium** | multiple files, a feature, a migration, auth/payment/data risk | validation contract, plan, complexity brake, **independent review**, completion record. |
| **Mission** | multi-day, multi-module, uncertain architecture | orchestrator + worker tasks + validators, milestones, shared artifacts. |

---

## What it enforces — and what it deliberately does *not*

The differentiator is that the gates are **executable**, not advisory — and that the README is
honest about where the executable part stops. `scripts/quality_loop.py` is a portable,
stdlib-only checker; it **complements** CI, tests, scanners, and human review — it does not
replace them.

**Enforced today** (`verify-gates` / `check-record` / `diff-audit`, pinned by [evals](evals/)):

- Non-trivial work (medium/mission, or any medium/high-risk or security-sensitive task) requires a
  named implementer, a real **validation contract**, an approving **independent review** by someone
  *other than* the implementer (fresh context, no self-patching), and — at ship — a **completion
  record** with evidence. Required fields must be present and non-empty; bare booleans, empty
  strings, and nonexistent paths are rejected. (It checks *shape* — that the evidence exists and is
  well-formed — not whether the content is substantive. A small low-risk task ships with handoff
  evidence, not a formal completion record.)
- **Detected-risk floor.** An *honestly described* boundary task cannot silently self-downgrade:
  the record's own goal/criteria/plan are scanned (word-boundary matched) for auth/authz, secrets,
  crypto, payments, migrations, destructive, and infra boundaries; any hit forces high-risk +
  security-review gates regardless of the declared tier.
- **UNDERSTAND is gated.** Non-trivial work must carry a substantive context map (entry points /
  likely files plus callers or tests) — the "map the change before editing" rule is checked.
- Every `pass` command carries a verifiable evidence handle and a known `class`; a recorded
  minimality decision; and `diff-audit` flags for secrets (including **untracked files** and
  **test-weakening**), dependency edits, migrations, and oversized diffs.
- **Repeated failure → durable change.** A recurring mistake must become a rule/test/hook/
  checklist/template, so a clean final record cannot bury a mistake corrected only in chat.

**Not enforced — by design, to stay portable** (be precise; this is the candor that makes the
rest trustable):

- It does **not** run your test suite, type checker, or security scanner — it checks that the
  *evidence* of those runs is present and well-formed. Recorded evidence (including RED→GREEN) is
  *attested, not re-executed*.
- Reviewer/implementer separation is compared as trimmed strings and fresh context is
  self-attested — a discipline, not a cryptographic guarantee.
- The detected-risk floor is a curated text-scan heuristic — it catches honest mis-tiering, not an
  agent deliberately phrasing around it. **Deterministic policy hooks** remain the backstop for
  anything you cannot afford an agent to get wrong.
- **`verify-gates` reads the record, not the diff.** It confirms the agent's recorded evidence is
  present and well-formed; it does not inspect the actual change. `diff-audit` (which reads real git
  state — secrets, untracked files, diff size, dependency/migration edits) and your CI are the
  blocking layer. Wire `diff-audit`'s exit code as a hard fail for anything that must not slip.
- It is not a model runtime: no recovery, telemetry, or git-worker handoff. Wiring the routed
  steps to real models/sessions is the host's job.

---

## Project memory

Most agents relearn the same lesson every session. The loop can keep a tiny, per-project ledger of
**distilled lessons** — failure modes, conventions ("no new dependencies here"), and gotchas
("this module broke twice") — so a lesson learned once is *recalled the next time*, not
rediscovered. New in v1.4.0.

It is **retrieval, not context stuffing**: only a ≤40-line index auto-loads, and recall is
budget-capped and scoped to the goal and files of the task at hand. Lessons are distilled (never
raw transcripts), **secrets are redacted before they are written**, and writes stay **advisory** —
memory adds no new gate.

```bash
# recall relevant prior lessons before mapping a change
python3 scripts/quality_loop.py memory-recall --goal "fix checkout retry" \
  --files src/payments/charge.py --risk high
# at retrospective, keep a lesson worth remembering
python3 scripts/quality_loop.py memory-commit agent-record.json
```

The default backend is **stdlib-only and checked-in** (`.quality-loop/memory/` — git-diffable and
team-shared). Two optional, loop-integrated backends plug in via config and degrade gracefully to
files: **[Honcho](https://honcho.dev)** (reasoning-based recall) and
**[Graphify](https://github.com/safishamsi/graphify)** (code-graph relevance). See
[`references/memory.md`](references/memory.md).

---

## Proof you can run

Every claim above is checkable on a clean checkout — no dependencies:

```bash
python3 -m py_compile scripts/*.py evals/*.py                                   # 1. byte-compile
python3 scripts/quality_loop.py check-config assets/quality-loop.config.example.json   # 2. config
python3 scripts/quality_loop.py eval-cases evals/cases --config assets/quality-loop.config.example.json   # 3. static
python3 evals/run_evals.py                                                      # 4. behavioral gates
python3 evals/run_memory_evals.py                                              # 5. memory gates
```

Current result: **9/9 static** + **26/26 behavioral** + **20/20 memory cases pass**, re-run on every
push by a dependency-free [GitHub Actions workflow](.github/workflows/evals.yml). The suites prove
different things, and are labeled honestly:

- The **static** suite is an *intake-classification regression test* — it pins the routing table
  (risk tier, task class, required gates). It does not prove a gate fires on real prose.
- The **behavioral** suite is where *the gates actually fire* — it drives the real CLI against
  constructed records and asserts hard-to-fake behavior (a self-downgraded boundary task is
  blocked, placeholder/wrong-content artifacts are rejected, the implementer can't be the reviewer,
  untracked secrets are flagged). One case is a docs-presence lint, not a gate.
- The **memory** suite drives the `memory-recall` / `commit` / `prune` CLI against constructed
  stores and asserts the anti-bloat and safety invariants hold — the index stays ≤40 lines even
  with multi-line lessons, recall respects its budget, and secrets are redacted before they land.

For medium/high-risk work, create and audit a state record:

```bash
python3 scripts/quality_loop.py init-record --goal "Fix checkout retry bug" --risk-tier medium --output agent-record.json
python3 scripts/quality_loop.py diff-audit --base origin/main
python3 scripts/quality_loop.py verify-gates agent-record.json
```

---

## Install & use matrix

Pick your host. Full copy-paste files live in [`examples/`](examples/); every path below is a real
file in this repo.

| Host | Install | Invoke |
|---|---|---|
| **Claude Code** (skill — progressive disclosure) | `cp -r . .claude/skills/coding-quality-loop` (project) or `~/.claude/skills/coding-quality-loop` (user) | `claude "Use the coding-quality-loop skill to fix the failing test and open a PR."` |
| **Claude Code** (instruction-only) | `cp examples/claude-code/CLAUDE.md ./CLAUDE.md` (or `/init`, then paste the loop) | `claude "Follow the Coding Quality Loop to fix the failing test."` |
| **Codex** | `cp examples/codex/AGENTS.md ./AGENTS.md` | `codex "Follow the Coding Quality Loop in AGENTS.md to fix the bug."` |
| **Cursor** | `cp -r examples/cursor/.cursor ./.cursor` | in chat: `@coding-quality-loop fix the retry bug with verification evidence` |
| **Pi** | `cp -r . ~/.agents/skills/coding-quality-loop` (or in-repo `.agents/skills/`) | `/skill:coding-quality-loop implement the change with a validation contract and independent review` |
| **Standalone / custom** | route each step from `assets/quality-loop.config.example.json` | follow [`examples/standalone/`](examples/standalone/run-quality-loop.md) |

> **Honesty note:** this repo is **not** yet on a plugin marketplace. The copy-to-folder paths
> above work today; `gh skill install` works once a maintainer publishes a release (see
> [Release & pinning](#release--pinning)).

### Three adoption levels

- **No install** — paste the [Minimal Drop-In Prompt](SKILL.md#minimal-drop-in-prompt) or a host
  rule file. Zero scripts, zero config. Best for trying it on one task.
- **Install** — copy the skill folder so the agent pulls `references/`, `assets/`, and the
  state-record schema *on demand* via progressive disclosure. Best for repeated use.
- **Orchestrated** — adopt `assets/quality-loop.config.example.json` and route each step to a
  role-based agent profile. Best for multi-agent / production setups.

---

## What's in the box

A single Agent Skill package following the open
[Agent Skills specification](https://agentskills.io/specification): `SKILL.md` at the root plus
optional sibling folders. **Progressive disclosure** is the core mechanism — the agent always sees
the frontmatter `name`/`description`, loads the full `SKILL.md` when relevant, and pulls
references/assets/scripts only when a step needs them.

```text
coding-quality-loop/
├── SKILL.md            # the skill: when-to-use, lifecycle, task classes, roles, gates
├── assets/             # templates + schemas loaded on demand (contract, validation contract,
│                       #   plan, logs, completion record, PR summary, record schema, config)
├── references/         # deep-dive docs pulled only when needed (lifecycle, orchestration,
│                       #   reviewer checklists, tool contracts, engineering-OS, philosophy,
│                       #   the memory contract + Honcho/Graphify backends)
├── examples/           # host-native copy-paste: claude-code, codex, cursor, pi, standalone,
│                       #   + a real before/after walkthrough with a passing state record
├── evals/              # offline eval cases + harness that prove the gates fire
├── scripts/            # quality_loop.py + quality_loop_memory.py — stdlib-only, no third-party deps
└── .quality-loop/      # per-project lessons memory (git-diffable; grows as the agent learns)
```

Copying the folder into any skills-aware host *is* the install. There is no build step.

---

## Why agentic-first

One model grading its own work is the dominant failure mode. The skill splits the loop into
role-based profiles — `orchestrator`, `context_mapper`, `implementer`, `validator`,
`simplicity_reviewer`, `security_reviewer`, `policy_guard` — and lets you map each role to the best
available model. Defaults stay simple: **one implementer + one independent validator +
deterministic policy hooks.** Add specialists only when risk justifies the coordination cost;
over-parallelization is an anti-pattern. ([Orchestration →](references/agentic-orchestration.md))

---

## How it compares

Other strong skills make different bets, and they're worth your time:
[**superpowers**](https://github.com/obra/superpowers) leans into subagent-driven TDD and a
two-stage review; [**addyosmani/agent-skills**](https://github.com/addyosmani/agent-skills) ships a
broad 24-skill SDLC suite; [**ponytail**](https://github.com/DietrichGebert/ponytail) is a focused
minimality ladder.

The Coding Quality Loop's bet is narrower: **executable gates plus candor.** It is the same
philosophy as those projects, compressed into one dependency-free package where the non-negotiables
are checked by a script you can read and run — and where the README tells you exactly what the
script does *not* check. It is positioned against two failure modes, not against other skills:
instruction-only prompts that **drift**, and full autonomy that produces **unreviewable diffs**.

---

## FAQ

**Does this slow the agent down?** Only where slowness buys trust. Ceremony scales with risk — a
typo runs the smallest possible loop with no mission artifacts; the full loop is reserved for work
whose blast radius justifies it.

**Does it actually run my tests?** No — and it says so. It checks that the *evidence* of a test run
is present and well-formed, not that the run happened. Pair it with CI and real scanners; the loop
makes the agent *record* proof, it doesn't *be* your test runner.

**Is the independent review really independent?** The checker enforces a distinct, named reviewer
in fresh context who didn't patch the code. Identity is string-compared and freshness is
self-attested — strong as a discipline, not a cryptographic guarantee. For production, wire the
reviewer to a genuinely separate session or model.

**Do I need the Python helper?** No. The loop works as pure instructions (Level 1). The helper is
an optional, stdlib-only accelerator for teams that want runnable record gates.

**Will it work with my agent?** If it loads `SKILL.md` or accepts a system prompt, yes — Claude
Code, Codex, Cursor, Pi, and standalone runtimes are covered with copy-paste files.

**Does it remember across sessions?** Optionally, yes. With [project memory](#project-memory)
enabled, distilled lessons persist per-project and are recalled — budget-capped — at the start of
the next task, so the agent stops relearning the same thing. It's advisory (no new gate),
stdlib-only by default, and redacts secrets before writing.

---

## Philosophy

> **Bounded autonomy. Smallest correct change. Evidence over confidence.**

Seven defaults the loop encodes, not slogans:

1. **An engineering operating system, not a clever prompt** — durable artifacts that outlive the session.
2. **Bounded autonomy is the product** — the boundary is what makes the output trustable.
3. **Ship the smallest correct change** — deletion, reuse, stdlib, native features before new code.
4. **Evidence over confidence** — every acceptance criterion paired with the check that proves it.
5. **Deterministic gates over vibes** — when a rule matters, a hook or check enforces it.
6. **Repo maps over context stuffing** — a concise map beats reading the whole tree.
7. **Durable harness changes over repeated chat corrections** — a fix becomes a rule, not a re-explanation.

Read the full manifesto — problem framing, trends, honestly-cited inspirations, and explicit
non-goals — in [`references/philosophy.md`](references/philosophy.md).

---

## Release & pinning

Skills are executable instruction/resource bundles — treat them like any dependency:

- **Inspect before you install.** Read `SKILL.md` and `scripts/quality_loop.py` — no hidden
  network access, no build step; the helper is stdlib-only.
- **Pin for team use.** Install from a tagged release or a pinned tree SHA, not a moving branch.
  The packaged version is in `SKILL.md` frontmatter (`metadata.version`) and [`CHANGELOG.md`](CHANGELOG.md).
- **`gh skill` once published.** When a maintainer runs `gh skill publish` (validates against the
  Agent Skills spec and writes repo/ref/tree-SHA provenance into the frontmatter), consumers can
  `gh skill install <repo> --pin <tag|sha>`. Until then, copy-to-folder is the supported install —
  provenance is not hand-faked.
- **Enforce the non-negotiables with hooks.** Advisory text drifts; wire the `policy_guard` rules
  (secrets, destructive migrations, auth/billing, diff-size limits) as deterministic host hooks.

<details>
<summary><strong>How this maps to official platform docs</strong></summary>

Portable, but aligned with how today's platforms load instructions and enforce policy:

- **Claude Code memory** — project/user/local `CLAUDE.md`, `.claude/rules/`, `/init`. <https://docs.anthropic.com/en/docs/claude-code/memory>
- **Claude Code hooks** — `PreToolUse` / `PostToolUse` / `Stop` hooks are the deterministic `policy_guard`. <https://docs.anthropic.com/en/docs/claude-code/hooks>
- **Codex `AGENTS.md`** — global, project, and nested overrides. <https://developers.openai.com/codex/guides/agents-md>
- **Codex skills** — `SKILL.md` directories with progressive disclosure. <https://developers.openai.com/codex/skills>
- **Cursor rules** — `.cursor/rules` in `.mdc` format. <https://docs.cursor.com/en/context/rules>
- **Pi skills** — loaded from `~/.agents/skills/`, `.agents/skills/`, etc. <https://pi.dev/docs/latest/skills>
- **Anthropic Agent Skills** — `SKILL.md` folders, progressive disclosure. <https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills>
- **Agent Skills specification** — the open, cross-agent package shape this repo targets. <https://agentskills.io/specification>

The design also draws on Factory Missions (long work split into focused units with fresh agents and
validation contracts), the Aider repo map (concise maps beat context stuffing), and the OpenAI
agent improvement loop (the harness is the unit of improvement).

</details>

---

## License

MIT — see [LICENSE](LICENSE).
