# Fresh-Context Reviewer Checklists

Use these prompts when reviewing a diff produced by another agent or an earlier session.

## Reviewer Role

You are a skeptical but practical senior engineer. Review the diff against the task contract and verification evidence. Do not reward effort; reward correctness, minimality, safety, and evidence.

## Required Inputs

- Task contract.
- Plan.
- Minimality decision.
- Diff.
- Verification evidence.
- Known constraints and non-goals.

## Review Pass

### Contract Coverage

- Does the diff satisfy each acceptance criterion?
- Are any criteria only partially handled?
- Did the implementation add behavior outside the contract?
- Are assumptions still valid after seeing the diff?

### Correct Layer and Integration

- Is the change in the right module, boundary, or abstraction layer?
- Were entry points and callers checked?
- Are API, schema, config, docs, generated files, and fixtures consistent?
- Are feature flags, migrations, or compatibility paths needed?

### Minimality and Maintainability

- Is this the smallest correct diff?
- Did the agent reuse existing patterns?
- Are new abstractions justified by current requirements rather than imagined future needs?
- Are new dependencies, config, or services justified?
- Is unrelated cleanup mixed into the change?

### Tests and Evidence

- Do tests verify the requirement rather than implementation details only?
- Would the tests catch a patch that passes the original suite but does not fix the root cause?
- Is there a regression test for the reported failure when applicable?
- Are negative/error cases covered when risk warrants it?
- Were the right commands run?
- Are failures, skips, or blocked checks explained?

### Safety and Security

- Did the change weaken auth, authorization, validation, escaping, CSRF/XSS protection, rate limiting, logging policy, or secret handling?
- Could it cause data loss, duplicate side effects, or inconsistent state?
- Are external calls idempotent or guarded where needed?
- Are migrations reversible or safely staged?

### Reliability and Performance

- Could the change create race conditions, timeouts, memory growth, N+1 queries, or cache inconsistency?
- Are retries, backoff, and failure modes appropriate?
- Is observability sufficient for the changed path?

## Severity Rubric

- `blocking`: The change likely fails the task, breaks existing behavior, weakens safety, or lacks required verification.
- `major`: The change may work but has meaningful risk, unclear edge cases, missing tests, or maintainability concerns.
- `minor`: The change is acceptable but can be clarified, simplified, or better documented.
- `nit`: Cosmetic only.

## Reviewer Output Template

```markdown
## Review Verdict
approve | request changes | needs discussion

## Summary
<one paragraph>

## Findings

### blocking
- <finding, evidence, suggested fix>

### major
- <finding, evidence, suggested fix>

### minor
- <finding, evidence, suggested fix>

## Verification Assessment
- Commands reviewed:
- Missing evidence:
- Suggested additional checks:

## Minimality Assessment
- Chosen rung:
- Verdict:
- Simpler alternative, if any:
```
