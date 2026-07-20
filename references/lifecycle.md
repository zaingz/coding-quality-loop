# Coding Quality Loop Lifecycle

## Canonical Operating Model: Three Phases

An LM runs a plan-execute-review loop, and context is a budget. **PLAN → EXECUTE → REVIEW** is
the narrative grouping the loop is organized around — it is *not* a field in the record and
nothing enforces it directly. The mechanism underneath is the record's `status` field and the
gates that read it (see the state machine below). Phases are how we talk about the work; the
`status` value is how the checker reasons about it. Each phase is conventionally closed by a
verification gate before the next begins:

```text
PLAN -> EXECUTE -> REVIEW
```

- **PLAN** — turn the goal into a task contract, map the change, write the validation
  contract, apply the right-size gate, and produce a plan. Closes when the plan and (for
  non-trivial work) the validation contract exist and are checkable.
- **EXECUTE** — implement in small slices and verify. Closes when the smallest sufficient
  checks pass with recorded evidence.
- **REVIEW** — independent review and ship/handoff. Closes when a fresh-context reviewer has
  checked the diff against the validation contract and, for non-trivial work, a completion
  record exists.

## Sub-Steps and Machine Aliases

Every sub-step inherits one of the three phases above; nothing is unlabeled. The sub-step
machine names below correspond to the record's `status` values (lowercased) — and `status`,
not any phase field, is what the gates key off. The names are stable — existing records,
configs, and automation keep working across releases. Each sub-step maps onto a phase as
shown:

| Phase | Canonical sub-step | Machine name | Primary artifact |
|---|---|---|---|
| PLAN | INTAKE | `INTAKE` | task contract |
| PLAN | CONTEXT MAP | `EXPLORE` | `context-map.md` |
| PLAN | SPEC / VALIDATION CONTRACT | `INTAKE`+`PLAN` | `validation-contract.md` |
| PLAN | RIGHT-SIZE GATE | `MINIMALITY_GATE` | minimality decision |
| PLAN | PLAN | `PLAN` | `plan.md` |
| EXECUTE | IMPLEMENT IN SMALL SLICES | `IMPLEMENT_SLICE` | diff + progress bullets |
| EXECUTE | VERIFY | `VERIFY` | command evidence |
| REVIEW | INDEPENDENT REVIEW | `REVIEW` | review verdict |
| REVIEW | SHIP / HANDOFF | `PACKAGE` | `completion-record.md` |
| REVIEW | RETROSPECTIVE / SKILL UPDATE | `RETROSPECT` | durable harness change |

The **right-size gate runs twice**: before PLAN (pick the smallest approach) and before
INDEPENDENT REVIEW (confirm nothing crept in) — both inside the PLAN and REVIEW phases
respectively. Minimal diff is not minimal architecture.

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
  -> RETROSPECT
  -> done | iterating | escalated
```

The three terminals are record `status` values from the schema enum
(`assets/agent-record.schema.json`): `done` closes the loop, `iterating` returns to an earlier
step for another slice or repair, and `escalated` is the human-input valve (requires a
non-empty `escalation_reason`).

## Task Classes

Default to the smallest class that safely satisfies the goal. The canonical class table
(Tiny / Small / Medium / Mission and the process each requires) is **SKILL.md §Task Classes**;
the per-state exit criteria below apply within whichever class you pick.

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
Machine form: at medium+ (or `security_sensitive`) each `acceptance_criteria` entry in the
record must be an object `{"criterion": ..., "proving_command": ...}` whose `proving_command`
matches a pass-labeled `commands_run` entry — `verify-gates` blocks bare string criteria there;
strings stay valid at low risk.

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

Exit when the agent has chosen and justified one rung (canonical ladder and its rationale:
SKILL.md §Right-Size Gate). Machine values for the record:

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

**Teardown.** PACKAGE archives the record to `docs/records/vX.Y.Z-agent-record.json` and removes
the live file, so the working tree carries no in-flight record between tasks. A record left
identical to its content at the resolved base ref (nothing locally in flight) is treated as
closed: the Stop gate allows the stop and does not re-verify it. Closure requires an explicit
base (`QUALITY_LOOP_BASE` or the config `base` key) or an `origin/*` ref — a solo no-origin repo
is never "closed", so the full gate still runs there. Phantom-completion detection stays CI's job.

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
| Refactor | behavior-preserving tests pass unchanged, diff shows no behavior change, right-size gate confirms net simplification |
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
