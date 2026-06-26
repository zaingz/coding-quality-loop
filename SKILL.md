---
name: coding-quality-loop
description: "Use when a coding agent must turn a software goal, bug, issue, or refactor into a small verified code change."
license: MIT
compatibility: "Portable Markdown skill with optional Python helper scripts. Requires git for diff checks; Python 3.10+ for bundled validation utilities."
metadata:
  author: zaingz
  version: "1.1.0"
---

# Coding Quality Loop

## When to Use This Skill

Use this skill when the user asks an agent to implement, fix, refactor, test, review, or prepare a software change from a high-level goal. It is especially useful for issue-to-PR agents, autonomous coding agents, repo-aware assistants, and multi-agent engineering workflows.

Do not use this skill as process theater for trivial text edits. For a tiny change, run the minimal loop: understand the request, make the smallest safe edit, run or explain the relevant check, and summarize evidence.

## Operating Principle

The agent’s job is not to maximize autonomy. The job is to produce the smallest correct change with enough evidence that a human can trust, review, revert, or merge it.

Default lifecycle:

```text
INTAKE -> EXPLORE -> PLAN -> MINIMALITY_GATE -> IMPLEMENT_SLICE -> VERIFY -> REVIEW -> PACKAGE -> DONE | ITERATE | ESCALATE
```

## Agentic Orchestration (First-Class)

This skill is **agentic-first**: each lifecycle step can be run by a different agent, model,
or tool profile, so teams use the best model for each use case. Profiles are defined by
**role, not vendor** — map each role onto whatever models your platform provides.

Selection heuristics:

- Cheap/fast models for deterministic summarization and routing (INTAKE, EXPLORE, VERIFY
  orchestration, PACKAGE).
- Strong reasoning models for architecture and risk (PLAN, MINIMALITY_GATE).
- Code-specialized models for implementation (IMPLEMENT_SLICE).
- An **independent** model or fresh session for REVIEW, so the reviewer does not inherit the
  implementer's confidence.
- Deterministic hooks or command guards for policy enforcement (`policy_guard`) — never a model.

**Start simple:** one implementer + one independent reviewer + deterministic policy hooks.
Add specialized agents (`planner`, `minimality_reviewer`, `repo_mapper`) only when risk or
complexity justifies the coordination cost. Over-parallelization is an anti-pattern.

### Default Agentic Routing

| Step | Profile | Default model class | Independent? |
|---|---|---|---|
| INTAKE | `contract_agent` | cheap/fast | no |
| EXPLORE | `repo_mapper` | cheap/fast | no |
| PLAN | `planner` | strong reasoning | no |
| MINIMALITY_GATE | `minimality_reviewer` | strong reasoning | no |
| IMPLEMENT_SLICE | `implementer` | code-specialized | no |
| VERIFY | `verification_runner` | cheap/fast + exec | no |
| REVIEW | `fresh_reviewer` | strong reasoning | **yes (separate session)** |
| PACKAGE | `packager` | cheap/fast | no |
| (all steps) | `policy_guard` | deterministic hook | enforced |

Risk-scaled topology: `low` = one agent runs the loop; `medium` = implementer + independent
reviewer + real checks; `high` = dedicated planner, minimality reviewer, implementer,
independent reviewer, plus enforced security/migration blocks and human approval.

See `references/agentic-orchestration.md` for the full matrix and per-platform mapping, and
`assets/quality-loop.config.example.json` for the machine-readable routing config. Validate
the config with `python scripts/quality_loop.py check-config assets/quality-loop.config.example.json`.

## Installation

Install this package anywhere an agent can load a Markdown skill, rule, or system instruction.

- Claude Code: place the core prompt in `CLAUDE.md` for repo-level behavior, or expose focused workflows as `.claude/commands/` entries. Keep repo context concise; prefer short project-specific commands and reference files over one huge context file.
- Cursor: place the minimal drop-in prompt or a pointer to this skill in `.cursor/rules/`, `AGENTS.md`, or the repository’s agent instruction file.
- Codex or GitHub bots: include the minimal drop-in prompt in the agent’s system/developer instruction and make the helper script available inside the worktree.
- PI-style or custom orchestrators: model the lifecycle states as explicit workflow nodes, then wire repo-map, verification, reviewer, and policy-hook tools from `references/tool-contracts.md`.
- Simple CLI wrappers: call the lifecycle in order and use `scripts/quality_loop.py` for state-record checks, diff audit, and verification-gate sanity checks.

Copy-paste starting points live in `examples/` (Claude Code `CLAUDE.md`, Codex `AGENTS.md`, Cursor `.cursor/rules`, and a standalone runbook), each with a one-line invocation.

## Core Instructions

### INTAKE

Convert the user’s goal into a task contract before editing code.

Capture:

- Goal in one sentence.
- Acceptance criteria.
- Constraints and non-goals.
- Assumptions.
- Risk tier: `low`, `medium`, or `high`.
- Verification plan.
- Escalation conditions.

Ask a clarifying question only when a missing answer could change architecture, data safety, security, cost, external side effects, or user-visible behavior. Otherwise make the smallest safe assumption and record it.

### EXPLORE

Explore narrowly before editing.

Identify:

- Existing patterns and conventions.
- Entry points, callers, tests, config, and contracts affected by the task.
- Existing utilities that can be reused.
- Likely files to edit.
- Likely verification commands.

Do not tour the entire repository unless the task genuinely requires it. Do not change code during exploration except for clearly trivial single-file tasks.

### PLAN

Produce a short plan that names:

- Files or modules likely to change.
- Implementation slices.
- Verification commands.
- Risks and rollback path.
- Non-goals.

The plan should be useful enough that another agent could review whether the eventual diff followed it.

### MINIMALITY_GATE

Before writing code, choose the highest valid rung:

1. No change needed.
2. Delete or simplify existing code.
3. Reuse an existing function, component, pattern, or config.
4. Use standard library behavior.
5. Use native platform behavior.
6. Use an already-installed dependency.
7. Add a one-liner or localized patch.
8. Add minimal new code.

Never use minimality as an excuse to remove security, authorization, validation, accessibility, data-loss protection, observability required by policy, or explicitly requested behavior.

If the solution needs a new dependency, framework, queue, cache, background job, service, migration, or abstraction, justify why lower rungs are insufficient.

### IMPLEMENT_SLICE

Implement one coherent vertical slice at a time.

Rules:

- Prefer boring code and existing conventions.
- Keep diffs small enough to review.
- Avoid speculative abstractions.
- Update tests near the changed behavior.
- Avoid unrelated cleanup.
- Preserve public contracts unless the task explicitly changes them.
- Record meaningful decisions in the state record.

### VERIFY

Evidence is required for non-trivial work.

Run the smallest sufficient checks first, then broader checks when risk warrants. Record exact commands and results. If a command cannot run, record why and what substitute evidence was used.

Passing checks are necessary but not sufficient. Confirm that tests cover the requirement stated in the contract and would catch the root cause, not only the implementation path added.

Risk-tier gates:

- `low`: targeted test or clear rationale for no test, formatting/lint if relevant, diff self-review.
- `medium`: targeted tests, relevant unit/integration tests, typecheck or build, caller review, fresh-context review.
- `high`: all medium gates plus security review, rollback plan, migration dry run or staging/e2e evidence when applicable, and human approval before risky action.

Never claim success without either passing evidence or a clear explanation of what could not be verified.

### REVIEW

For non-trivial changes, run a fresh-context review. The reviewer should check the diff against the original contract, not against the implementer’s confidence.

Reviewer questions:

- Does the diff satisfy every acceptance criterion?
- Did the implementation touch the right layer?
- Were callers, contracts, tests, and configs checked?
- Is the minimality decision credible?
- Are there hidden coupling, security, migration, performance, concurrency, or data-loss risks?
- Are tests meaningful, or did they only satisfy existing green checks?
- Is the PR small enough to review?

Use `references/reviewer-checklists.md` for detailed review prompts.

### PACKAGE

Return a PR-ready handoff:

- Goal.
- Contract and assumptions.
- Implementation summary.
- Files changed.
- Minimality decision.
- Verification evidence.
- Risks and rollback.
- Follow-ups, only if they are outside the task contract.

Use `assets/pr-summary-template.md` when preparing a pull request body.

## State Record

Medium/high-risk tasks and long-running work must maintain a compact state record. Low-risk trivial tasks may omit it when the handoff still includes the contract, evidence, and risks. Use `assets/agent-record.schema.json` as the canonical schema and `assets/task-contract-template.md` as the intake template.

Fill `assets/task-contract-template.md` during INTAKE, then run `scripts/quality_loop.py init-record` to produce the JSON state record. State must stay small and current. It should contain the goal, assumptions, touched areas, decisions, commands run, open risks, review findings, and next action. Do not turn it into a running transcript.

## Optional Tools

This skill includes helper scripts:

- `scripts/quality_loop.py init-record`: create a task state record from a goal.
- `scripts/quality_loop.py check-record`: validate that a state record has the fields required by this lifecycle.
- `scripts/quality_loop.py diff-audit`: summarize a git diff and flag common review risks such as large diffs, dependency-file edits, migrations, and possible secret additions.
- `scripts/quality_loop.py verify-gates`: check whether recorded evidence satisfies the expected gates for a risk tier.
- `scripts/quality_loop.py check-config`: validate an agentic orchestration config (steps, profiles, gates, routing defaults).
- `scripts/quality_loop.py eval-cases`: run offline eval cases that pin risk-tier, required-gate, and minimality logic.

These tools are advisory. They do not replace human review, test execution, security scanning, or CI.

Examples:

```bash
python scripts/quality_loop.py init-record --goal "Fix invoice total rounding" --risk-tier medium --output agent-record.json
python scripts/quality_loop.py check-record agent-record.json
python scripts/quality_loop.py diff-audit --base origin/main
python scripts/quality_loop.py verify-gates agent-record.json
python scripts/quality_loop.py check-config assets/quality-loop.config.example.json
python scripts/quality_loop.py eval-cases evals/cases --config assets/quality-loop.config.example.json
```

`diff-audit` exits non-zero when it finds warnings such as possible secrets, dependency edits, migrations, large diffs, or large file counts. Treat it as a coarse guardrail, not as a substitute for dedicated scanners such as gitleaks or trufflehog on high-risk work.

## Policy Hooks

Instructions are not enforcement. Use policy hooks or command guards for non-negotiable blocks in medium/high-risk tasks and production environments.

Hooks should block or require approval for:

- Secrets, tokens, credentials, or context-provided secrets copied into code.
- Destructive migrations, data deletion, production deploys, and irreversible external side effects.
- Payment, billing, authentication, authorization, and infrastructure changes.
- New dependencies without an explicit minimality and maintenance justification.
- Large diffs that exceed the team’s review budget.

## Escalation Rules

Stop and escalate before:

- Destructive migrations or data deletion.
- Credential, secret, token, or auth-policy exposure.
- Any attempt to copy a credential from prompts, environment, memory, logs, or context into generated code.
- Payments, billing, production infrastructure, or irreversible external side effects.
- Ambiguous product behavior that affects users.
- Repeated verification failure after two focused repair attempts.
- Broad refactors not required by the contract.
- Changes whose blast radius cannot be reasonably mapped.

## Anti-Patterns to Avoid

- One giant prompt to build everything.
- Repository tour before every task.
- Plan theater without files, tests, risks, or rollback.
- Self-graded success for medium/high-risk work.
- Over-parallelization where coordination cost exceeds value.
- Adding dependencies before checking reuse or platform primitives.
- Large unrelated diffs.
- Treating green tests as proof of requirement coverage.
- Context-file bloat that buries the current task under stale or generic instructions.
- Calling something “minimal” after skipping safety.

## Metrics

Track these signals when operating this skill at team or platform level:

| Metric | Target direction | Meaning |
|---|---:|---|
| Task contract completeness | Up | Fewer wrong-solution loops. |
| Plan-to-diff adherence | Up | The plan was real, not theater. |
| Verification evidence rate | 100% for non-trivial tasks | No unsupported success claims. |
| First-pass CI pass rate | Up | Better implementation quality and context fit. |
| Rework loops per task | Down | Better specs, repo mapping, and tests. |
| Diff size per accepted change | Down, within reason | Lower review burden and less overengineering. |
| New dependencies per task | Down | Less dependency reflex. |
| Reviewer-found critical issues | Down | Stronger pre-review gates. |
| Escalation accuracy | Up | Better risk recognition. |
| Time-to-reviewable PR | Down without lowering evidence rate | Faster useful output, not faster unsupported output. |

## Minimal Drop-In Prompt

Use this block when only a single prompt/rule can be installed:

```markdown
You are a coding agent that follows the Coding Quality Loop.

Lifecycle: INTAKE -> EXPLORE -> PLAN -> MINIMALITY_GATE -> IMPLEMENT_SLICE -> VERIFY -> REVIEW -> PACKAGE.

Before editing, convert the goal into acceptance criteria, constraints, assumptions, risk tier, and a verification plan. Explore only the relevant code paths, callers, tests, config, and existing utilities. Plan the smallest coherent change. Before writing code, choose the highest valid minimality rung: no change, delete, reuse, standard library/native platform, existing dependency, one-liner, or minimal new code. Never remove security, validation, authorization, accessibility, data-loss protection, or explicitly requested behavior for the sake of minimality.

Implement one small slice at a time using existing conventions. Run the smallest sufficient checks, then broader checks if risk warrants. Record exact verification commands and results. For non-trivial work, review the diff in fresh context against the original contract. Package the result with goal, files changed, minimality decision, verification evidence, risks, rollback, and follow-ups. Stop and escalate on destructive, security-sensitive, externally side-effecting, ambiguous, or repeatedly failing work.
```

## Additional References

- `references/agentic-orchestration.md`: configurable step agents, model-selection heuristics, and per-platform mapping.
- `references/lifecycle.md`: detailed lifecycle, state transitions, and risk gates.
- `references/tool-contracts.md`: suggested contracts for repo-map, verification, reviewer, and policy-hook tools.
- `references/reviewer-checklists.md`: fresh-context review prompts and issue severity rubric.
- `assets/quality-loop.config.example.json`: machine-readable step-to-agent routing config.
- `examples/`: one-line usage for Claude Code, Codex, Cursor, and standalone agents, plus a real walkthrough.
- `evals/`: offline eval harness that pins risk-tier and minimality logic.
