# Coding Quality Loop Lifecycle

## Canonical Operating Model and Machine Aliases

The documented operating model has ten steps. The helper script, config, and state record use
stable short machine names for compatibility. Both describe the same loop.

```text
INTAKE -> CONTEXT MAP -> SPEC / VALIDATION CONTRACT -> COMPLEXITY BRAKE -> PLAN
  -> IMPLEMENT IN SMALL SLICES -> VERIFY -> INDEPENDENT REVIEW
  -> SHIP / HANDOFF -> RETROSPECTIVE / SKILL UPDATE
```

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

The **complexity brake runs twice**: before PLAN (pick the smallest approach) and before
INDEPENDENT REVIEW (confirm nothing crept in).

## State Machine (machine names)

```text
INTAKE
  -> EXPLORE
  -> MINIMALITY_GATE
  -> PLAN
  -> IMPLEMENT_SLICE
  -> VERIFY
  -> REVIEW
  -> PACKAGE
  -> DONE | ITERATE | ESCALATE
```

## Task Classes

Default to the smallest class that safely satisfies the goal.

| Class | Looks like | Process |
|---|---|---|
| Tiny | typo, copy, one-line config, obvious test update | inspect, edit, smallest check; no mission artifacts |
| Small | local bug, one module, low risk | light context map, mini spec, minimal fix, targeted test |
| Medium | multiple files, feature, migration, auth/payment/data risk | full spec + validation contract, plan, independent review, completion record |
| Mission | multi-day, multi-module, multi-repo, uncertain architecture | orchestrator + workers + validators, milestones, shared mission artifacts |

## State Exit Criteria

### INTAKE

Exit when the agent has:

- One-sentence goal.
- Acceptance criteria.
- Constraints and non-goals.
- Assumptions.
- Risk tier.
- Initial verification plan.

If missing information could materially change the implementation, ask. If not, make the smallest safe assumption and record it.

### EXPLORE

Exit when the agent can name:

- Relevant entry points.
- Existing patterns to follow.
- Callers or consumers likely affected.
- Tests that cover or should cover the behavior.
- Config, schema, API, docs, or generated artifacts involved.
- Existing code that can be reused.

Exploration is read-only unless the task is trivial. For medium/mission work the output is
`context-map.md` — findings, not a repository dump.

### SPEC / VALIDATION CONTRACT

For medium/mission work, write down what "done" means before implementing. Exit when
`validation-contract.md` pairs every acceptance criterion with the concrete check that proves
it, lists invariants/non-goals, names regression risks, and flags any risk boundary touched
(which triggers a security review). Tiny/small tasks may fold this into the task contract.

### PLAN

Exit when the plan lists:

- Likely files or modules to change.
- Implementation steps.
- Verification commands.
- Risks.
- Rollback path.
- Non-goals.

Good plans name files or modules, but they do not pretend to know every edit before implementation. If the plan cannot name any likely file, return to EXPLORE.

### MINIMALITY_GATE

Exit when the agent has chosen and justified one rung:

`skip | delete | reuse | stdlib | native | existing_dependency | one_liner | minimal_new_code`

Lower rungs must be considered before higher rungs. New abstractions, dependencies, queues, caches, migrations, services, or frameworks require explicit justification.

### IMPLEMENT_SLICE

Exit when one coherent slice is complete. A slice should be reviewable, testable, and revertible.

### VERIFY

Exit when recorded evidence matches the risk tier or when blocked verification is explicitly explained.

### REVIEW

Exit when the diff has been checked against:

- Contract coverage.
- Right-layer implementation.
- Minimality.
- Tests and verification evidence.
- Security and data-safety concerns.
- Hidden coupling and regression risk.

Use `references/reviewer-checklists.md` for the detailed fresh-context review prompt and severity rubric.

### PACKAGE

Exit when the handoff includes:

- Goal and acceptance criteria.
- Summary of implementation.
- Files changed.
- Minimality decision.
- Verification evidence.
- Risks and rollback.
- Follow-ups outside the contract.

Do not list required unfinished acceptance criteria as follow-ups. If they are required by the contract, the task is not done.

Non-trivial tasks exit only with a `completion-record.md` containing verification evidence —
the shipping gate. No completion record → not done.

### RETROSPECTIVE / SKILL UPDATE

Exit when any **repeated** mistake has been converted into a durable harness change — an
`AGENTS.md`/`CLAUDE.md` rule, a `SKILL.md` step, a test, a hook, a review-checklist item, a
repo-map entry, or a validation-contract template. A one-off mistake needs no change; a
recurring one must never be left as a repeated chat correction.

## Quality Gates by Task Type

| Work type | Required gates |
|---|---|
| Bug fix | failing test reproducing the bug then green, regression test, targeted suite |
| Feature | acceptance-criteria tests, unit/integration, typecheck/build, fresh review |
| Refactor | behavior-preserving tests pass unchanged, diff shows no behavior change, complexity brake confirms net simplification |
| Migration | dry run / reversible plan, backfill strategy, staging or e2e evidence, rollback, human approval |
| Security-sensitive | gates for its type plus a `security_reviewer` pass and a deterministic hard gate |

## Risk Tiering

### Low Risk

Examples:

- Docs.
- Copy changes.
- Small UI tweak.
- One-line localized bug fix.

Required:

- Targeted check or explicit rationale for no check.
- Formatter/lint if applicable.
- Diff self-review.

### Medium Risk

Examples:

- Multi-file behavior change.
- API contract change.
- Persistence-adjacent change.
- Auth-adjacent logic.
- Shared utility change.

Required:

- Targeted tests.
- Relevant unit or integration tests.
- Typecheck or build if applicable.
- Caller/consumer review.
- Fresh-context review.

### High Risk

Examples:

- Authz/authn.
- Payments.
- Data migrations.
- Destructive operations.
- Secrets or credentials.
- Production infrastructure.
- External side effects.
- Concurrency or distributed systems.

Required:

- All medium-risk gates.
- Security review.
- Rollback plan.
- Migration dry run, staging evidence, or e2e evidence when applicable.
- Human approval before irreversible actions.

## Iteration Policy

If verification fails:

1. Identify the root cause.
2. Apply the smallest focused fix.
3. Rerun the failed check.
4. Rerun adjacent checks if the fix changes risk.

After two failed repair loops, escalate with evidence and recommended next steps.

## Long-Running Work

For work spanning multiple milestones:

- Split by independently verifiable slices.
- End each milestone with evidence and an updated state record.
- Spawn parallel workers only for independent areas with low coordination cost.
- Use fresh-context review at milestone boundaries.
- Keep the mission record compact; do not preserve every thought or log line.
