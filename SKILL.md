---
name: coding-quality-loop
description: "Use when a coding agent must turn a software goal, bug, issue, or refactor into a small, verified, independently reviewed code change."
license: MIT
compatibility: "Portable Markdown skill with optional Python helper scripts. Requires git for diff checks; Python 3.10+ for bundled validation utilities."
metadata:
  author: zaingz
  version: "2.3.2"
---

# Coding Quality Loop

## When to Use This Skill

Use this skill when the user asks an agent to implement, fix, refactor, test, review, or prepare a software change from a high-level goal. It is built for issue-to-PR agents, autonomous coding agents, repo-aware assistants, and multi-agent engineering workflows.

Do not use it as process theater for trivial edits. Match the ceremony to the task class (see **Task Classes**). A typo fix should run the smallest possible loop; a payment-path migration should run the full one.

## What This Is: An Engineering Operating System

This is not a better prompt. Prompts are being replaced by **durable process artifacts** that survive across sessions, agents, and models. The skill packages an *engineering operating system* for coding agents, built from five parts:

1. **Durable repo instructions** — `AGENTS.md`, `CLAUDE.md`, `.cursor/rules` carry standing rules and commands so behavior is consistent without re-prompting.
2. **Reusable skills** — focused `SKILL.md` workflows with triggers, steps, and exit criteria are the portable unit of agent capability.
3. **Mission artifacts** — `context-map.md`, `validation-contract.md`, `plan.md`, `execution-log.md`, `decision-log.md`, `completion-record.md` make long-horizon work orchestratable instead of cramming everything into one context.
4. **Independent verification** — for non-trivial work the implementer and validator are separate, because an implementer grading its own work inflates confidence and hides gaps.
5. **Complexity discipline** — prefer deletion, reuse, the standard library, native platform features, and minimal custom code *before* writing new code. Minimalism is a first-class quality property, not an afterthought.

Cross-cutting principle behind all five: **deterministic gates beat advisory text, and repo maps beat context stuffing.** When a rule matters, enforce it with a hook or a check; when an agent needs to understand a codebase, give it a map, not the whole tree.

The agent's job is not to maximize autonomy. The job is to produce the **smallest correct change with enough evidence that a human can trust, review, revert, or merge it.**

## Task Classes (Default to the Smallest That Is Safe)

Pick the smallest class that safely satisfies the goal. Escalate a class only when risk, blast radius, or uncertainty demands it.

| Class | Looks like | Process |
|---|---|---|
| **Tiny** | typo, copy, one-line config, obvious test update | inspect the file, edit, run the smallest check. No mission artifacts. |
| **Small** | local bug, one module, low risk | quick context map, mini spec, minimal fix, targeted test. |
| **Medium** | multiple files, a feature, a migration, auth/payment/data risk | full spec + **validation contract**, plan, complexity brake, **independent review**, completion record. |
| **Mission** | multi-day, multi-module, multi-repo, uncertain architecture | orchestrator + worker tasks + validators, milestones, shared mission artifacts. |

A tiny task must **not** be forced through mission ceremony. A medium task must **not** be shipped without a validation contract and an independent review.

## Lifecycle

Canonical operating model:

```text
INTAKE -> CONTEXT MAP -> SPEC / VALIDATION CONTRACT -> COMPLEXITY BRAKE -> PLAN
  -> IMPLEMENT IN SMALL SLICES -> VERIFY -> INDEPENDENT REVIEW
  -> SHIP / HANDOFF -> RETROSPECTIVE / SKILL UPDATE
```

The helper script, config, and state record use stable short machine names. The mapping:

| Canonical step | Machine name | Primary artifact |
|---|---|---|
| INTAKE | `INTAKE` | task contract |
| CONTEXT MAP | `EXPLORE` | `context-map.md` |
| SPEC / VALIDATION CONTRACT | `INTAKE`+`PLAN` | `validation-contract.md` |
| COMPLEXITY BRAKE | `MINIMALITY_GATE` | minimality decision |
| PLAN | `PLAN` | `plan.md` |
| IMPLEMENT IN SMALL SLICES | `IMPLEMENT_SLICE` | diff + `execution-log.md` |
| VERIFY | `VERIFY` | command evidence |
| INDEPENDENT REVIEW | `REVIEW` | review verdict |
| SHIP / HANDOFF | `PACKAGE` | `completion-record.md` |
| RETROSPECTIVE / SKILL UPDATE | `RETROSPECT` | durable harness change |

The **complexity brake runs twice**: once before PLAN (choose the smallest approach) and again before INDEPENDENT REVIEW (confirm nothing crept in).

## Mental Model: Map the Change Before You Touch It

Before editing, build a small graph of the change. This is the thinking behind INTAKE + CONTEXT MAP, and it prevents wrong-layer fixes:

```text
goal
 ├─ user-visible behavior        (what changes for the user / caller?)
 ├─ non-goals                    (what must NOT change?)
 ├─ constraints                  (perf, compat, deadlines, policy)
 ├─ affected surfaces
 │    ├─ APIs / contracts
 │    ├─ DB / schema / migrations
 │    ├─ UI
 │    ├─ jobs / queues / schedules
 │    ├─ auth / security
 │    └─ external integrations
 ├─ existing patterns to reuse
 ├─ tests that cover / should cover it
 ├─ risks                        (data loss, regression, blast radius)
 └─ evidence                     (what proof will make this trustworthy?)
```

## Roles (Agentic Orchestration, First-Class)

Each lifecycle step can run as a different agent, model, or tool profile, mapped by **role, not vendor**. Start simple — **one implementer + one independent validator + deterministic policy hooks** — and add roles only when risk justifies the coordination cost. Over-parallelization is an anti-pattern.

| Role | Owns | Notes |
|---|---|---|
| `orchestrator` | scope, classify task, context, spec, validation contract, decompose, assign workers, collect validator findings, create fix tasks, **stop if unsafe** | medium/mission only |
| `context_mapper` (config: `repo_mapper`) | repo layout, relevant modules, entry points, data flow, existing helpers, tests/commands | outputs **findings, not raw dumps** |
| `implementer` (config: `implementer`) | bounded task, no speculative abstraction, no unrelated cleanup, smallest meaningful test, coherent slice | cannot be the final validator |
| `validator` (config: `fresh_reviewer`) | acceptance criteria, behavior contract, regression risk, edge cases, evidence | **fresh context; does not implement** |
| `simplicity_reviewer` (config: `minimality_reviewer`) | deletion / reuse / stdlib / native / dependency / abstraction review | the complexity brake, as a reviewer |
| `security_reviewer` | auth, permissions, secrets, payments, PII, migrations, upload/download, network, shell, dependency changes | **only at risk boundaries** |
| `policy_guard` | deterministic safety blocks | a hook/command guard, **never a model** |

Detailed routing, model-selection heuristics, mission topology, and per-platform mapping are in `references/agentic-orchestration.md`. Machine-readable routing is `assets/quality-loop.config.example.json` (validate with `python3 scripts/quality_loop.py check-config ...`). To wire real models per host, copy that file to `quality-loop.config.json`, fill the `model_routing` section, and run `python3 scripts/quality_loop.py setup-models` — it rewrites agent frontmatter for Claude Code/Droid or prints the Codex/Pi settings to apply. `brief` shows the active routing and flags drift.

## Core Instructions

### INTAKE

Convert the goal into a task contract before editing code: one-sentence goal, acceptance criteria, constraints, non-goals, assumptions, risk tier (`low|medium|high`), task class, verification plan, escalation conditions.

Ask a clarifying question only when a missing answer could change architecture, data safety, security, cost, external side effects, or user-visible behavior. Otherwise make the smallest safe assumption and record it.

### CONTEXT MAP (EXPLORE)

Map narrowly before editing. Identify entry points, callers, tests, config, and contracts touched by the task; existing utilities to reuse; likely files to edit; likely verification commands. Output **findings**, not a repository tour. Use `assets/context-map.md` for medium/mission work.

### SPEC / VALIDATION CONTRACT

For medium/mission work, write **down what "done" means before implementing** using `assets/validation-contract.md`: each acceptance criterion paired with the concrete check that proves it, plus regression risks and the evidence required. Verification is a contract, not a vague instruction — the validator checks the diff against *this*, not against the implementer's confidence.

### COMPLEXITY BRAKE (MINIMALITY_GATE)

Before writing code, choose the highest valid rung:

1. No change needed.
2. Delete or simplify existing code.
3. Reuse an existing function, component, pattern, or config.
4. Use standard library behavior.
5. Use native platform behavior.
6. Use an already-installed dependency.
7. Add a one-liner or localized patch.
8. Add minimal new code.

If the solution needs a new dependency, framework, queue, cache, background job, service, migration, or abstraction, justify why every lower rung is insufficient.

**Non-negotiables — never sacrificed for minimality:** trust-boundary validation, data-loss prevention, security, accessibility, explicitly required behavior, and real-world calibration (the change must behave correctly under realistic inputs and load, not just in the happy path).

**Minimality is not a license to pick a slower algorithm.** When the task is performance-sensitive (search/indexing/ranking, rendering, hot request paths, data pipelines, batch jobs, or anything with an explicit benchmark in the brief), the complexity brake must also produce a **worst-case-complexity commitment** and a **p50/p95 target** for the hot path, recorded in the validation contract. "Simple linear scan" is not simpler than "inverted index + posting-list merge" when the brief includes a benchmark harness — it is a covert requirement miss. Escalate at PLAN if the chosen approach cannot hit the target; do not discover the miss at VERIFY.

### PLAN

Produce a short plan (`assets/plan.md`) naming files/modules to change, implementation slices, verification commands, risks, rollback path, and non-goals. The plan should let another agent check whether the eventual diff followed it.

### IMPLEMENT IN SMALL SLICES

Implement one coherent vertical slice at a time. Prefer boring code and existing conventions. Keep diffs small. Avoid speculative abstractions and unrelated cleanup. Update tests near the changed behavior. Preserve public contracts unless the task explicitly changes them. Record meaningful decisions in `decision-log.md` and progress in `execution-log.md` for mission work.

### VERIFY

Evidence is required for non-trivial work. Run the smallest sufficient checks first, then broader checks as risk warrants. Record exact commands and results. If a command cannot run, record why and what substitute evidence was used.

Passing checks are necessary but not sufficient: confirm tests cover the contract requirement and would catch the root cause, not only the code path you added. See **Quality Gates by Task Type**.

### INDEPENDENT REVIEW

For non-trivial changes, a **fresh-context** reviewer (separate session, ideally a different model) checks the diff against the validation contract — not the implementer's confidence. The implementer may not be the final validator. Use `references/reviewer-checklists.md`. Add a `security_reviewer` pass when the change touches a risk boundary.

### SHIP / HANDOFF (PACKAGE)

Return a PR-ready handoff and, for non-trivial tasks, a **completion record** (`assets/completion-record.md`): goal, contract, implementation summary, files changed, minimality decision, verification evidence, risks/rollback, and follow-ups outside the contract. Use `assets/pr-summary-template.md` for the PR body.

### RETROSPECTIVE / SKILL UPDATE

Close the loop. Every **repeated** mistake becomes a durable harness change — an `AGENTS.md`/`CLAUDE.md` rule, a `SKILL.md` step, a test, a hook, a review-checklist item, a repo-map entry, or a validation-contract template — **not** a repeated chat correction. See **Improvement Loop**.

Make this checkable: when a verification failure recurs, record it on the state record with `repeated_failure: true` (or `repair_attempts >= 2`) and capture the durable fix in `harness_update`. `verify-gates` then requires the `harness_update` evidence before the record can pass, so a clean final record cannot silently bury a repeated mistake.

### PERSISTENT PROJECT MEMORY (optional, advisory)

Across tasks, the loop can keep a small per-project ledger of **distilled lessons** —
failure modes, conventions, gotchas, and preferences — so a lesson learned once is recalled
later instead of relearned. It is retrieval, not context stuffing: only a <=40-line
`MEMORY.md` index may auto-load, and recall is budget-capped and relevance-scoped.

- **Recall at INTAKE / CONTEXT MAP** (recommended, not gated):
  `python3 scripts/quality_loop.py memory-recall --goal "<goal>" --files a,b,c --risk medium --budget 1500`
  Consider the returned lessons before mapping the change.
- **Commit at RETROSPECTIVE** (manual; you decide it is worth keeping):
  `python3 scripts/quality_loop.py memory-commit agent-record.json`
  Distills `harness_update`, `minimality_decision`, and notable `review_findings` into lesson
  rows under `.quality-loop/memory/`.
- **Prune periodically:** `python3 scripts/quality_loop.py memory-prune`.

Writes are advisory — `verify-gates` adds no new hard block. Optional backends (`honcho` for
reasoning recall, `graphify` for code-graph relevance) plug in via the config `memory` block
and degrade to the dependency-free files backend when absent. See `references/memory.md`,
`references/memory-honcho.md`, and `references/memory-graphify.md`.

A **global cross-project store** (`~/.quality-loop/global/`) holds user-level conventions and
preferences that apply across all projects. Recall merges project + global lessons under a
split-capped budget. Commit to it with `--global`:

```bash
python3 scripts/quality_loop.py memory-commit --lesson "always read the migration guide before editing schema files" --kind convention --global
```

### SESSION CONTINUITY (longitudinal assistant)

Long-running projects span multiple sessions. The loop bridges context windows with a
session-start **briefing** and a **progress file** — the same pattern Anthropic's long-running
agent harness uses (progress file + git as memory):

- **At session start**, run `brief` to get up to speed:
  `python3 scripts/quality_loop.py brief`
  Prints the last run summary, open risks from the last record, top recalled lessons, and the
  progress-file tail. Wired into the Claude Code `SessionStart` hook; add a one-line
  "run brief at session start" to `AGENTS.md` for Codex/Droid/Pi.
- **At PACKAGE / RETROSPECT**, update `.quality-loop/progress.md` (copy the template from
  `assets/progress.md` on first use): current goal, recent sessions (one bullet each), open
  risks, next step. Leave the repo in a clean state (commit progress, no half-implemented
  features).
- **Resume**: `brief` surfaces the next step; pick up from there instead of guessing.

## Hard Rules

- **Understand before editing.** No edit before the change is mapped (CONTEXT MAP + mental-model graph).
- **Write down "done" first.** Non-trivial work needs a validation contract before implementation.
- **Prefer existing code.** Reuse, stdlib, and native platform features come before new code and new dependencies.
- **The implementer cannot be the final validator.** Non-trivial review is independent.
- **No success claim without evidence.** Non-trivial work ends with files, tests, evidence, risks, and follow-ups recorded.
- **Delete when deletion is the simplest correct solution.** Less code is a valid — often the best — outcome.
- **Don't game the tests.** A bug fix shows a failing-then-passing (RED→GREEN) reproduction; tests are never weakened, skipped, or deleted to reach green, and the fix is not co-mutated with the test that should catch it.
- **Stop at risk boundaries.** Escalate before destructive, security-sensitive, or irreversible actions.

## Enforcement Matrix

Every Hard Rule maps to a deterministic owner (a script you can run) or an explicit
**advisory** label. Candor is auditable: this is the trust artifact that says where the
machine stops and the human/host begins. `verify-gates` reads the record; `verify-gates
--against-diff` and `diff-audit` read git; `run-evidence` re-executes commands. Host hooks
(Ring 1) remain a documented integration point, not a shipped dependency.

| Hard Rule | Deterministic owner | Advisory where not deterministic |
|---|---|---|
| Understand before editing | `verify-gates` (repo_map gate) + `--against-diff` (scope integrity) | context-map *quality* is advisory |
| Write down "done" first | `verify-gates` (validation_contract required for non-trivial) | contract *substance* is advisory |
| Prefer existing code | `verify-gates` (minimality_decision required) | rung *choice* is advisory |
| Implementer cannot be the final validator | `verify-gates` (reviewer != implementer string-compare) | fresh_context is self-attested (advisory) |
| No success claim without evidence | `verify-gates` (evidence handle required) + `run-evidence` (re-execution) + `--against-diff` (phantom completion) | evidence *substance* beyond re-execution is advisory |
| Delete when deletion is simplest | `verify-gates` (minimality_decision.rung) | whether deletion was *considered* is advisory |
| Don't game the tests | `--against-diff` (bugfix-test co-presence) + `run-evidence --red-green` (RED at base / GREEN at HEAD) + `diff-audit` (test-weakening warning) | test *coverage* of the contract is advisory |
| Stop at risk boundaries | `detect_risk_floor` (text scan) + `--against-diff` (diff-derived path floor) | whether to *escalate to a human* is advisory; wire host hooks for hard blocks |

Records may now carry optional `diff_sha256` (attest-review), `files_changed`
(completion record), and `red_green` (commands_run) fields — all optional, no adopter
break. Telemetry is local JSONL (`.quality-loop/telemetry.jsonl`); opt out with
`QUALITY_LOOP_NO_TELEMETRY=1`.

## Host Session Ring

Release 1.6 adds first-class host wiring without making any host mandatory:

- `hosts/claude-code/settings.json` wires `SessionStart`, `PreToolUse`, and `Stop`
  command hooks. Shims are stdlib Python and delegate to the core CLI.
- `.claude/agents/quality-loop-reviewer.md` and
  `.claude/agents/quality-loop-security-reviewer.md` are read-only reviewer
  subagents sourced from `references/reviewer-checklists.md`.
- `hosts/codex/hooks.json` uses Codex's current project hook schema. Codex still
  requires hook trust review in `/hooks`.
- `hosts/git/install-git-hooks.py` and `hosts/git/.pre-commit-config.yaml` provide
  the universal git backstop: staged `diff-audit` blocks secrets/test weakening.
- `action.yml` and `hosts/github/quality-loop-example.yml` provide CI wiring.
- `scripts/install.py` installs host wiring idempotently and prints what is
  enforced vs advisory.

Host hooks are advisory by default. A repo can opt into required edit-before-plan
blocking with `.quality-loop/config.json`:

```json
{"enforcement": "required"}
```

## Driven Mode

`scripts/quality_loop_run.py` is an optional **reference orchestrator** that runs the
loop locally instead of trusting a chat transcript. It uses a single host adapter
for all steps (no per-role model routing — that is the host's job via the config
profiles). It uses `scripts/quality_loop_hosts.py` adapters:

- `fake` for offline tests and fixture replay.
- `manual` for human relay.
- `claude` and `codex` for subprocess-backed host runs when available.

VERIFY is orchestrator-native: configured commands run locally with timeout,
redacted output tails, and output hashes stored in `commands_run[].evidence`.
REVIEW receives only contract + diff + evidence, not the implementer transcript.
PACKAGE writes a completion record and re-runs `verify-gates`. High-risk work
exits escalated before PACKAGE.

```bash
python3 scripts/quality_loop_run.py --goal "Fix invoice rounding" --host fake --dry-run
python3 scripts/quality_loop_run.py --record agent-record.json --host manual
```

## Proof Harness

`bench/` contains the benchmark protocol, 12 vendored tasks, objective metrics,
and a fixture-mode runner. The committed fixture result validates harness plumbing
only; live model sweeps must record host, model, seed, cost, artifacts, and null
results. Trigger evals live at `evals/run_trigger_evals.py` and can use a
caller-supplied judge command.

## Shipping Gate

An agent **may not claim completion** for a medium or mission task — or any high-risk or security-sensitive work — unless a completion record exists with verification evidence. Tiny and small low-risk tasks may ship with a contract + evidence + risks in the handoff; the runtime gate enforces exactly this threshold (it does not demand a completion record for small low-risk work). Enforce the gate with a `Stop`/PostToolUse hook in production (see **Harness Implementation Modes**).

## Quality Gates by Task Type

| Work type | Required gates |
|---|---|
| **Bug fix** | failing test reproducing the bug, then green; regression test; targeted suite. |
| **Feature** | acceptance-criteria tests, unit/integration, typecheck/build, fresh review. |
| **Refactor** | behavior-preserving tests pass unchanged; diff shows no behavior change; complexity brake confirms net simplification. |
| **Migration** | dry run / reversible plan, backfill strategy, staging or e2e evidence, rollback, human approval. |
| **Security-sensitive** | all of the above for its type **plus** `security_reviewer` pass and a deterministic hard gate. |

Risk-tier gates (`low`/`medium`/`high`) and detailed criteria are in `references/lifecycle.md`.

## Harness Implementation Modes

Adopt the lightest mode that fits your risk and tooling; combine as needed.

1. **Instruction-only** — `AGENTS.md` / `CLAUDE.md` / `.cursor/rules` carry the loop as standing, *advisory* guidance. Short and command-first beats long and vague.
2. **Skill-based** — ship as a skill directory (`.agents/skills/coding-quality-loop/SKILL.md`, a Claude skill, or a Pi skill). Portable, with progressive disclosure: metadata first, full `SKILL.md` when relevant, extra files on demand.
3. **Hook-enforced** — deterministic gates for protected folders, format/test after edit, dependency-change approval, destructive-command blocks, and the completion-record shipping gate. Hooks enforce; text only advises.
4. **Mission agent** — orchestrator + context mapper + workers + validators + simplicity/security reviewers, for **medium/mission work only**.

## Tool Surface

- **Minimum:** read, search, edit, shell, run tests, `git diff` / branch / commit / PR.
- **Useful extensions:** repo-map generator, AST search, browser automation, GitHub CLI, issue tracker, CI logs, Sentry/Datadog logs, read-only DB access, design docs, MCP connectors.
- **MCP only when** context lives outside the repo, changes frequently, or should be repeatable via a tool. Add a tool only when it removes a real manual loop — not for its own sake.

Suggested tool contracts (repo-map, verification runner, reviewer, security review, policy hook, completion record) are in `references/tool-contracts.md`.

## State Record and Mission Artifacts

Medium/high-risk and long-running work maintains a compact state record. Tiny tasks may omit it when the handoff still includes contract, evidence, and risks. Use `assets/agent-record.schema.json` as the canonical schema and the templates in `assets/` for human-readable artifacts:

- `task-contract-template.md`, `context-map.md`, `validation-contract.md`, `plan.md`, `execution-log.md`, `decision-log.md`, `completion-record.md`, `pr-summary-template.md`, `AGENTS.template.md`.

Fill the task contract during INTAKE, then run `scripts/quality_loop.py init-record` to produce the JSON state record. Keep state small and current: goal, assumptions, touched areas, decisions, commands run, open risks, review findings, next action. Do not turn it into a transcript.

## Optional Tools

Helper script commands (advisory; they do not replace human review, tests, scanners, or CI):

- `init-record` — create a task state record from a goal.
- `brief` — print a session-start project briefing: last run summary, open risks, top recalled lessons, progress-file tail, and a suggested next step. Wire into a `SessionStart` hook or run manually at the start of each session.
- `check-record` — validate a state record against this lifecycle.
- `diff-audit` — summarize a git diff and flag large diffs, dependency edits, migrations, and possible secrets. `--staged` audits the cached (pre-commit) diff.
- `verify-gates` — check the recorded evidence against the risk tier: the validation contract and completion record must be a real existing file or an inline object whose required fields are present and non-empty (it rejects bare booleans, empty strings, and nonexistent paths — it checks *shape*, not whether the content is substantive), plus the repeated-failure → `harness_update` rule. It reads the **record**, not the diff; pair it with `diff-audit` and CI for the actual block. `--against-diff [--base REF]` adds the **reality layer**: phantom completion (package/done ∧ empty diff), scope integrity (changed files ⊄ repo_map/plan/completion_record), a diff-derived risk floor (auth/payments/migrations/.env/terraform/lockfiles force high-tier), bugfix-test co-presence, review freshness (recomputed `diff_sha256`), and promotes secret/test-weakening warnings to blocking at medium+.
- `attest-review` — embed a recomputed `git diff | sha256` into a review object (the reviewer's last act), so review freshness is checkable.
- `run-evidence` — re-execute each recorded `commands_run[result=pass]` against the real environment (allowlist `.quality-loop/allowed-commands`, per-command timeout, sidecar `.quality-loop/rerun-<task>.json`, never mutates the record). `--red-green` replays a `red_green: true` command in a `git worktree` at base (expect fail) and HEAD (expect pass); worktree unavailable → explicit "not proven", never a silent pass.
- `scan-text --stdin` — secret-scan text from stdin (for host hook shims); exits non-zero on a finding.
- `stats` — render the metrics table from local telemetry (`.quality-loop/telemetry.jsonl`), printing "not instrumented" for rows it can't compute. Telemetry is local-only, no network; opt out with `QUALITY_LOOP_NO_TELEMETRY=1`.
- `check-config` — validate an agentic orchestration config.
- `setup-models` — apply the `model_routing` config section to host agent files (Claude Code `.claude/agents/*.md`, Droid `.factory/droids/*.md`) by rewriting the `model:` frontmatter, or print the settings to apply (Codex `config.toml`, Pi `/model` commands). Run `brief` to see the active routing and detect drift.
- `eval-cases` — run offline eval cases that pin task-class, risk-tier, required-gate, security-reviewer, completion-record, complexity-brake, and retrospective logic.

```bash
python3 scripts/quality_loop.py init-record --goal "Fix invoice total rounding" --risk-tier medium --output agent-record.json
python3 scripts/quality_loop.py check-record agent-record.json
python3 scripts/quality_loop.py diff-audit --base origin/main
python3 scripts/quality_loop.py diff-audit --staged
python3 scripts/quality_loop.py verify-gates agent-record.json
python3 scripts/quality_loop.py verify-gates agent-record.json --against-diff --base origin/main
python3 scripts/quality_loop.py attest-review review.json --base origin/main
python3 scripts/quality_loop.py run-evidence agent-record.json --red-green --base origin/main
python3 scripts/quality_loop.py scan-text --stdin < suspicious-file.txt
python3 scripts/quality_loop.py stats
python3 scripts/quality_loop.py check-config assets/quality-loop.config.example.json
python3 scripts/quality_loop.py setup-models --config quality-loop.config.json --host claude-code
python3 scripts/quality_loop.py setup-models --config quality-loop.config.json --host codex
python3 scripts/quality_loop.py eval-cases evals/cases --config assets/quality-loop.config.example.json
```

`diff-audit` exits non-zero on warnings (possible secrets, dependency edits, migrations, large diffs/file counts). Treat it as a coarse guardrail, not a substitute for gitleaks/trufflehog on high-risk work.

## Policy Hooks

Instructions are not enforcement. Use policy hooks or command guards for non-negotiable blocks in medium/high-risk tasks and production. Block or require approval for:

- Secrets, tokens, or credentials copied into code (including from prompts, env, memory, or context).
- Destructive migrations, data deletion, production deploys, and irreversible external side effects.
- Payment, billing, authentication, authorization, and infrastructure changes.
- New dependencies without an explicit minimality and maintenance justification.
- Large diffs that exceed the team's review budget.
- A completion claim with no completion record (the shipping gate).

## Escalation Rules

Stop and escalate before:

- Destructive migrations or data deletion.
- Credential, secret, token, or auth-policy exposure, or copying a credential from any source into generated code.
- Payments, billing, production infrastructure, or irreversible external side effects.
- Ambiguous product behavior that affects users.
- Repeated verification failure after two focused repair attempts.
- Broad refactors not required by the contract.
- Changes whose blast radius cannot be reasonably mapped.

## Anti-Patterns to Avoid

- One giant prompt (or one giant context) to build everything.
- Repository tour before every task.
- Plan theater without files, tests, risks, or rollback.
- Self-graded success for medium/high-risk work.
- Over-parallelization where coordination cost exceeds value.
- Adding dependencies before checking reuse or platform primitives.
- Large unrelated diffs.
- Treating green tests as proof of requirement coverage.
- **Test-gaming** — weakening, skipping, or deleting tests to reach green; co-mutating implementation and the test that should catch it in one slice; claiming RED→GREEN without a recorded failing-then-passing run.
- Context-file bloat that buries the current task under stale or generic instructions.
- Calling something "minimal" after skipping safety.
- Confusing **minimal code** with **minimal performance**. Collapsing a multi-feature medium task into a single monolithic file, or into one test file per project, is not minimality — it is under-fanned modularity, and the diff will read that way to a fresh-context reviewer.
- Correcting the same mistake in chat instead of making a durable harness change.

## Metrics and Improvement Loop

Track these at team or platform level, and convert findings into durable harness changes:

| Metric | Target | Meaning |
|---|---:|---|
| Acceptance pass rate | Up | Diffs satisfy the contract first try. |
| Validator-found defects | Up early, down over time | Review catches issues before ship; gates improve. |
| Escaped defects | Down | Fewer bugs reach production. |
| Diff size per accepted change | Down, within reason | Lower review burden, less overengineering. |
| Review turnaround | Down without lowering evidence | Faster useful output. |
| Verification evidence rate | 100% for non-trivial | No unsupported success claims. |
| Dependencies avoided | Up | Complexity discipline working. |
| Repeated mistakes converted to harness changes | Up | The loop learns. |

**Retrospective rule:** every repeated failure becomes a durable harness change — an `AGENTS.md`/`SKILL.md` rule, a test, a hook, a review-checklist item, a repo-map entry, or a validation-contract template. Not a repeated chat correction. The harness — instructions, tools, routing, output requirements, and validation checks — is what improves; rank candidate changes and pin regressions with evals.

## Minimal Drop-In Prompt

Use this when only a single prompt/rule can be installed:

```markdown
You are a coding agent that runs the Coding Quality Loop — an engineering operating system, not just a prompt.

Lifecycle: INTAKE -> CONTEXT MAP -> SPEC/VALIDATION CONTRACT -> COMPLEXITY BRAKE -> PLAN -> IMPLEMENT IN SMALL SLICES -> VERIFY -> INDEPENDENT REVIEW -> SHIP/HANDOFF -> RETROSPECTIVE.

Pick the smallest safe task class (tiny/small/medium/mission); do not force a typo through mission ceremony. Before editing, map the change (goal, user-visible behavior, non-goals, constraints, affected surfaces, patterns, tests, risks, evidence) and, for non-trivial work, write a validation contract that pairs each acceptance criterion with the check that proves it. Apply the complexity brake: choose the highest valid rung — no change, delete, reuse, stdlib, native, existing dependency, one-liner, minimal new code — and never trade away security, validation, authorization, accessibility, data-loss protection, or required behavior for minimality.

Implement one small slice at a time in existing conventions. Run the smallest sufficient checks, then broader ones as risk warrants; record exact commands and results. For non-trivial work, review the diff in fresh context (a different session or model — the implementer is not the final validator) against the contract, and add a security review at any risk boundary (auth, secrets, payments, PII, migrations, upload/download, network, shell, dependency changes). Do not claim completion for non-trivial work without a completion record. Stop and escalate on destructive, security-sensitive, externally side-effecting, ambiguous, or repeatedly failing work. Turn every repeated mistake into a durable rule/test/hook, not a repeated correction.
```

## Additional References

- `references/engineering-operating-system.md`: the five-part OS, trend synthesis, task classes, harness modes, and tool surface in depth.
- `references/agentic-orchestration.md`: configurable step agents, role architecture, model-selection heuristics, mission topology, per-platform mapping.
- `references/lifecycle.md`: detailed lifecycle, state transitions, task classes, risk gates, quality gates by task type.
- `references/tool-contracts.md`: contracts for repo-map, verification, reviewer, security review, policy hook, and completion record.
- `references/reviewer-checklists.md`: fresh-context, simplicity, and security review prompts and severity rubric.
- `references/memory.md`: persistent per-project lessons memory — capability model, the
  backend-agnostic recall/commit/prune contract, storage, lifecycle wiring, and anti-bloat rules.
- `references/memory-honcho.md` and `references/memory-graphify.md`: optional loop-integrated
  memory backends (Honcho reasoning recall; Graphify code-graph relevance).
- `assets/`: task contract, context map, validation contract, plan, execution/decision logs, completion record, PR summary, progress template, `AGENTS.template.md`, state-record schema, routing config, and per-role prompt cards (`assets/prompts/`).
- `examples/`: one-line usage for Claude Code, Codex, Cursor, Pi, Droid, and standalone agents, plus a real walkthrough.
- `evals/`: offline eval harness pinning task-class, risk-tier, minimality, security-reviewer, completion-record, and retrospective logic.
