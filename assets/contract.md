# Contract

Write this **before** implementing. Verification is a contract, not a vague instruction:
each acceptance criterion is paired with the concrete command that proves it (this is the
shape the AC-coverage gate checks — at medium+ risk every criterion needs a
`proving_command` that matches a pass-labeled `commands_run` entry).

## Goal

<one sentence>

## Acceptance Criteria (criterion → proving command)

| # | Criterion | Proving command | Type |
|---|---|---|---|
| 1 |  |  | unit / integration / e2e / manual / typecheck |
| 2 |  |  |  |

## Constraints

- 

## Non-Goals (must not change)

- 

## Assumptions

- 

## Risk Tier

low | medium | high

## Task Class

tiny | small | medium | mission

## Verification Plan

- Commands to run and the expected result:
- Regression risks: what existing behavior could this break, and which check guards it?
- Performance-sensitive work only: hot path, complexity target, latency/memory budget,
  benchmark command. Skip otherwise — do not manufacture targets. If targets cannot be
  met, escalate at PLAN.

## Rollback

- <how to undo this change if it ships broken>

## Escalation Conditions

- 

## Risk Boundaries Touched

- [ ] auth / authorization
- [ ] secrets / credentials
- [ ] payments / billing
- [ ] PII / data privacy
- [ ] migrations / schema
- [ ] upload / download
- [ ] network calls
- [ ] shell / process execution
- [ ] dependency changes

If any box is checked, a `security_reviewer` pass is required.
