---
name: coding-quality-loop
description: "Use when a coding agent must turn a software goal, bug, issue, or refactor into a small, verified, independently reviewed code change."
license: MIT
compatibility: "Portable Markdown skill with optional Python helper scripts. Requires git for diff checks; Python 3.10+ for bundled validation utilities."
metadata:
  author: zaingz
  version: "3.0.0"
---

# Coding Quality Loop

## When to Use

Use this skill when the user asks an agent to implement, fix, refactor, test, review, or prepare a software change from a high-level goal. Do not use it as process theater for trivial edits. Match ceremony to the task class.

## Task Classes (default to the smallest that is safe)

| Class | Looks like | Process |
|---|---|---|
| **Tiny** | typo, copy, one-line config | inspect, edit, smallest check. No artifacts. |
| **Small** | local bug, one module, low risk | quick context map, mini spec, minimal fix, targeted test. |
| **Medium** | multiple files, feature, migration, auth/payment/data risk | validation contract, plan, right-size gate, **independent review**, completion record. |
| **Mission** | multi-day, multi-module, multi-repo | orchestrator + worker tasks + validators, milestones, shared artifacts. |

## Lifecycle

```text
PLAN -> EXECUTE -> REVIEW
```

- **PLAN** — task contract, context map, validation contract, right-size gate, plan. Gate: plan + contract exist and are checkable.
- **EXECUTE** — implement in small slices, verify with evidence. Gate: smallest sufficient checks pass with recorded evidence.
- **REVIEW** — independent review, ship/handoff, retrospective. Gate: fresh-context reviewer checked the diff against the contract; completion record exists for non-trivial work.

Sub-step machine names (for records/configs): `INTAKE`, `EXPLORE`, `MINIMALITY_GATE`, `PLAN` (PLAN); `IMPLEMENT_SLICE`, `VERIFY` (EXECUTE); `REVIEW`, `PACKAGE`, `RETROSPECT` (REVIEW). The helper script maps `status` to `phase` via `resolve_phase()`.

## Calibration (model-adaptive ceremony)

The same scaffolding helps weaker models and can hurt stronger ones. In our own evals, CQL lifted GLM-5.2 +8.0, Claude +4.5, Codex +1.0 on a Sudoku task, but **hurt** GPT-5 by −9.0 on a search-library task where the right-size gate pushed it into a 60x-slower monolith. Calibrate:

- **Strong models** (frontier-class): skip ceremony on tiny/small. For medium+, write the validation contract and run independent review, but do not over-constrain the plan. Add an explicit anti-compression rule: the right-size gate is about diff size and dependency minimality, not about collapsing architecture into fewer files. Do not monolith.
- **Weaker models**: run full scaffolding. The validation contract and context map prevent the most common failure: wrong-layer fixes and unmapped blast radius.
- **Review is paid only when the task exceeds what the model does reliably solo.** A frontier model on a one-module bug fix may not need a separate reviewer. A migration always does.
- **Cross-frontier routing works as a capability router.** Route review to a different model family than implementation; route planning to the strongest reasoning model available. The implementer and validator must not be the same model on medium+.

## Right-Size Gate

Before writing code, choose the highest valid rung:

1. No change needed. 2. Delete or simplify. 3. Reuse existing function/component/pattern. 4. Standard library. 5. Native platform behavior. 6. Already-installed dependency. 7. One-liner or localized patch. 8. Minimal new code.

If the solution needs a new dependency, framework, queue, cache, service, migration, or abstraction, justify why every lower rung is insufficient.

**Non-negotiables** (never sacrificed for minimality): trust-boundary validation, data-loss prevention, security, accessibility, explicitly required behavior, real-world calibration.

**Minimal diff is not minimal architecture.** Collapsing a multi-feature medium task into one monolithic file is not minimality, it is under-fanned modularity. When the task is performance-sensitive (search, indexing, ranking, rendering, hot paths, pipelines, anything with a benchmark), the right-size gate must also produce a **worst-case-complexity commitment** and a **p50/p95 target** for the hot path, recorded in the validation contract. "Simple linear scan" is not simpler than the required data structure when the brief includes a benchmark. Escalate at PLAN if the chosen approach cannot hit the target.

## Core Instructions

### INTAKE
Convert the goal into a task contract: one-sentence goal, acceptance criteria, constraints, non-goals, assumptions, risk tier, task class, verification plan. Ask a clarifying question only when a missing answer could change architecture, data safety, security, or user-visible behavior.

### CONTEXT MAP (EXPLORE)
Map narrowly before editing: entry points, callers, tests, config, contracts touched. Output findings, not a repository tour.

### VALIDATION CONTRACT
For medium/mission, write down what "done" means before implementing: each acceptance criterion paired with the concrete check that proves it, plus regression risks and required evidence. The validator checks the diff against this, not against the implementer's confidence.

### PLAN
Name files/modules to change, implementation slices, verification commands, risks, rollback path, non-goals.

### IMPLEMENT IN SMALL SLICES
One coherent slice at a time. Existing conventions, no speculative abstractions, no unrelated cleanup. Small diffs. Update tests near the changed behavior.

### VERIFY
Run the smallest sufficient checks first, then broader as risk warrants. Record exact commands and results. A bug fix shows a failing-then-passing (RED to GREEN) reproduction. Tests are never weakened, skipped, or deleted to reach green.

### INDEPENDENT REVIEW
For non-trivial changes, a **fresh-context** reviewer (separate session, different model) checks the diff against the validation contract. The implementer is not the final validator. The reviewer should **execute** tests and benchmarks when possible, not just read the diff. Verdict records `ran_checks: true|false`. Add a security review at risk boundaries.

**Communication bridge:** after the reviewer produces findings, the implementer filters them against the contract. In-scope findings become fix tasks. Out-of-scope findings become follow-ups, not blockers. This prevents review loops.

### SHIP / HANDOFF
Return a PR-ready handoff and, for non-trivial tasks, a completion record: goal, contract, implementation summary, files changed, right-size decision, verification evidence, risks/rollback, follow-ups.

### RETROSPECTIVE
Every **repeated** mistake becomes a durable harness change: a rule, a test, a hook, a checklist item, an eval case. Not a repeated chat correction. When a verification failure recurs, record `repeated_failure: true` and capture the durable fix in `harness_update`.

## Roles

| Role | Owns | Model class |
|---|---|---|
| `orchestrator` | scope, classify, decompose, assign, stop if unsafe | strong reasoning (mission only) |
| `context_mapper` | repo layout, relevant modules, findings not dumps | cheap/fast |
| `implementer` | bounded task, smallest test, coherent slice | code-specialized |
| `validator` | acceptance criteria, evidence, regression risk | strong reasoning, **separate session** |
| `simplicity_reviewer` | right-size gate as reviewer | strong reasoning |
| `security_reviewer` | auth, secrets, payments, PII, migrations, dependencies | strong reasoning, boundary only |
| `policy_guard` | deterministic safety blocks | **never a model** (hook/command) |

Start simple: one implementer + one independent validator + deterministic hooks. Add roles only when risk justifies the coordination cost. Over-parallelization is an anti-pattern.

**Smart friend (optional):** the implementer can consult a stronger model on defined triggers: 2 failed repair attempts, merge conflicts, or architecture uncertainty. The stronger model gets a fork of the implementer's context and responds with guidance, not code. Per-host wiring: Claude subagent, Droid Task tool, Codex subagent. See `references/agentic-orchestration.md`.

## Hard Rules

1. **Understand before editing.** No edit before the change is mapped.
2. **Write down "done" first.** Non-trivial work needs a validation contract before implementation.
3. **Prefer existing code.** Reuse, stdlib, native before new code and new dependencies.
4. **The implementer cannot be the final validator.** Non-trivial review is independent.
5. **No success claim without evidence.** Non-trivial work ends with tests, evidence, risks, and follow-ups recorded.
6. **Don't game the tests.** A bug fix shows RED then GREEN; tests are never weakened.
7. **Stop at risk boundaries.** Escalate before destructive, security-sensitive, or irreversible actions.
8. **Delete when deletion is the simplest correct solution.**

The helper script enforces rules 1-6 as record-shape or diff-grounded gates. Rule 7 is a heuristic risk-floor scan. See `references/enforcement-matrix.md` for what is deterministic vs advisory.

## Persistent Project Memory (optional, advisory)

Recall distilled lessons at INTAKE; commit at RETROSPECTIVE. Retrieval, not context stuffing: <=40-line index, budget-capped recall, secrets redacted before writing. See `references/memory.md`.

## Session Continuity

At session start, run `brief` to get up to speed. At PACKAGE/RETROSPECT, update `.quality-loop/progress.md`. Resume from the surfaced next step.

## Helper Commands

**Primary verification (one command):**
```bash
python3 scripts/quality_loop.py verify agent-record.json --base origin/main --red-green
```
`verify` runs record-shape gates, diff-grounded reality checks, evidence re-execution, and AC-to-command coverage in one pass.

**Individual commands (for targeted checks):**
```bash
python3 scripts/quality_loop.py init-record --goal "Fix bug" --risk-tier medium --output agent-record.json
python3 scripts/quality_loop.py verify-gates agent-record.json --against-diff --base origin/main
python3 scripts/quality_loop.py diff-audit --base origin/main
python3 scripts/quality_loop.py run-evidence agent-record.json --red-green --base origin/main
python3 scripts/quality_loop.py attest-review review.json --base origin/main
python3 scripts/quality_loop.py brief
python3 scripts/quality_loop.py check-config assets/quality-loop.config.example.json
python3 scripts/quality_loop.py setup-models --host claude-code
python3 scripts/quality_loop.py eval-cases evals/cases --config assets/quality-loop.config.example.json
```

Memory: `memory-recall`, `memory-commit`, `memory-prune`, `memory-status`.

## Minimal Drop-In Prompt

```markdown
You are a coding agent that runs the Coding Quality Loop.

Lifecycle: PLAN -> EXECUTE -> REVIEW. Context is a budget; verification terminates each phase. PLAN covers intake, context map, validation contract, right-size gate, and planning. EXECUTE covers implementation slices and verification. REVIEW covers fresh-context review, packaging, and retrospective.

Pick the smallest safe task class. Before editing, map the change and, for non-trivial work, write a validation contract pairing each acceptance criterion with the check that proves it. Apply the right-size gate: choose the highest valid rung (no change, delete, reuse, stdlib, native, existing dependency, one-liner, minimal new code). Minimal diff is not minimal architecture or minimal performance: when the brief includes a benchmark, commit to a worst-case complexity and p50/p95 target at plan time.

Implement one slice at a time. Run the smallest sufficient checks; record commands and results. For non-trivial work, review the diff in fresh context (different session or model) against the contract, and execute tests when possible. Do not claim completion without a completion record. Stop and escalate on destructive, security-sensitive, or repeatedly failing work. Turn every repeated mistake into a durable rule, not a repeated correction.
```

## References

- `references/lifecycle.md`: detailed lifecycle, state transitions, risk gates, quality gates by task type.
- `references/agentic-orchestration.md`: role architecture, model-selection heuristics, mission topology, per-platform mapping, config-driven model setup.
- `references/reviewer-checklists.md`: fresh-context, simplicity, and security review prompts.
- `references/tool-contracts.md`: contracts for repo-map, verification, reviewer, security, policy hook.
- `references/memory.md`: persistent per-project lessons memory.
- `references/enforcement-matrix.md`: every hard rule mapped to its deterministic owner or advisory label.
- `assets/`: templates, schemas, routing config, per-role prompt cards.
- `evals/`: offline eval harness pinning task-class, risk-tier, minimality, security, completion-record, and retrospective logic.
