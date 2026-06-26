# Coding Quality Loop Lifecycle

## State Machine

```text
INTAKE
  -> EXPLORE
  -> PLAN
  -> MINIMALITY_GATE
  -> IMPLEMENT_SLICE
  -> VERIFY
  -> REVIEW
  -> PACKAGE
  -> DONE | ITERATE | ESCALATE
```

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

Exploration is read-only unless the task is trivial.

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
