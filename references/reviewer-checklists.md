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
- **If the brief includes a benchmark harness or the task is performance-sensitive:** does the validation contract commit to a worst-case complexity for the hot path, and does the diff’s chosen algorithm honor it? Reject linear-scan-per-term implementations of tasks that require an inverted index, per-request re-tokenization on hot paths, or O(n) fuzzy matching over full corpora when a bounded prefix + edit-distance filter is expected.
- **Benchmark numbers must be captured against the stated target**, not just recorded. A diff that meets correctness but misses the perf target is `blocking`, not `minor`.

## Simplicity Reviewer Pass (Complexity Brake)

Run this before final review. The simplicity reviewer asks whether the change could be smaller:

- **Deletion** — could the goal be met by removing code instead of adding it?
- **Reuse** — does an existing function, component, pattern, or config already do this?
- **Stdlib / native** — is there standard-library or native-platform behavior that replaces
  custom code?
- **Dependency** — is any new dependency justified against every lower rung, with a maintenance cost worth paying?
- **Abstraction** — is each new abstraction required by *current* needs, not imagined future ones?

Flag `overengineering` when a new dependency or abstraction is introduced while a lower rung is
available. Never use minimality to justify dropping a non-negotiable (trust-boundary
validation, data-loss prevention, security, accessibility, required behavior, real-world
calibration).

Also flag `under-fanned` when a medium/mission task with multiple distinct features (parser +
ranker + tokenizer + serializer, etc.) is collapsed into a single source file or a single
test file. Modularity is a maintainability property, not overengineering. A 700-LOC monolith
with one 13-test file is not "minimal" for a task with 7 required feature areas — it is
under-fanned, and future edits will pay for it.

## Security Reviewer Pass (Risk Boundaries Only)

Trigger this pass only when the change touches a risk boundary: auth, permissions, secrets,
payments, PII, migrations, upload/download, network, shell, or dependency changes. Check:

- **AuthN / AuthZ** — is identity verified and is every new path authorized for the right scope/tenant?
- **Secrets** — no credential read from prompts/env/memory/logs/context into code; no secret in the diff.
- **Input / trust boundaries** — validation, escaping, parameterized queries, CSRF/XSS/SSRF protection on untrusted input.
- **Data safety** — migrations reversible or safely staged; no unintended deletion; backfill correct.
- **Side effects** — payment/external calls idempotent and guarded; no duplicate or irreversible effect on retry.
- **Supply chain** — new dependency vetted (source, maintenance, transitive risk); lockfile reviewed.
- **Network / shell** — outbound calls and shell execution are necessary, bounded, and not injectable.

A security finding at a risk boundary should be `blocking` until resolved or explicitly accepted by a human.

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
