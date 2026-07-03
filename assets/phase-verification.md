# Phase Verification

For each of PLAN, EXECUTE, REVIEW, record one block below when the phase ends.
Verification is what makes the phase "done"; a phase without verification does not advance.
For medium/mission work, a phase is not complete until its block has
`status: verified` — an unverified phase blocks progress to the next one.

## Phase: {{plan|execute|review}}
- verified_by: [list of check names]
- evidence: [list of evidence handles — file paths, command outputs, links]
- verifier: {{same_agent | different_context | different_model | human}}
- status: {{verified | failed | skipped_with_reason}}
- notes: optional

## Verifier requirements

- **plan**: `same_agent` is acceptable for tiny/small tasks (the implementer
  checking its own plan against the goal before starting). Medium/mission work
  should still prefer `different_context` where practical, but `same_agent` is
  not an automatic failure at this phase.
- **execute**: `same_agent` is acceptable for tiny/small tasks. For
  medium/mission tasks, prefer `different_context` or stronger — the person or
  agent who wrote the code checking its own tests is weaker evidence than a
  second look, but is not blocked outright the way review is.
- **review**: `same_agent` **MUST NOT** be used for medium/mission tasks. The
  reviewer must be `different_context` (a fresh session with no memory of
  writing the diff), `different_model`, or `human`. An implementer grading its
  own review inflates confidence and hides gaps — this is the same principle
  that makes the implementer ineligible as the final validator elsewhere in
  this skill. Tiny/small tasks may still use `same_agent` for review, but
  escalate to `different_context` or better whenever the change touches a risk
  boundary (auth, payments, secrets, migrations, data loss).

## Status semantics

- `verified`: the check(s) in `verified_by` ran (or were reviewed) and passed;
  `evidence` is non-empty and points at something real (file, command output,
  link).
- `failed`: the phase did not pass verification. A failed entry blocks
  advancement regardless of task class — fix the phase and re-verify, or
  escalate.
- `skipped_with_reason`: verification was deliberately skipped (e.g. a `plan`
  phase with no separate plan artifact for a tiny change). Use sparingly and
  only when the skip itself is defensible; still record `notes` explaining why.

## Evidence

`evidence` must not be empty for EXECUTE or REVIEW blocks — a status without a
pointer to a real artifact is a claim, not verification. `evidence` may be
empty for PLAN when the plan itself *is* the artifact being referenced by
`verified_by` (e.g. `verified_by: ["plan.md exists and matches goal"]`), but a
file path, command output, or link is still preferred whenever one exists.
