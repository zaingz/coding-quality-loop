# Validation Contract

Write this **before** implementing. Verification is a contract, not a vague instruction.
Each acceptance criterion must be paired with the concrete check that proves it.

## Goal

<one sentence>

## Done When (Acceptance Criteria → Proof)

| # | Acceptance criterion | Check that proves it | Type |
|---|---|---|---|
| 1 |  |  | unit / integration / e2e / manual / typecheck |
| 2 |  |  |  |

## Must Not Change (Non-Goals / Invariants)

- 

## Regression Risks

- What existing behavior could this break, and which check guards it?

## Required Evidence Before Ship

- Commands to run and the expected result:
- Artifacts to capture (logs, screenshots, migration dry-run output):

## Performance / Complexity Targets

Fill this in **only** when the task is performance-sensitive (search/indexing/ranking,
rendering, hot request paths, data pipelines, batch jobs, or anything with an explicit
benchmark harness in the brief). Skip it otherwise — do not manufacture targets.

- Hot path(s):
- Worst-case complexity target for the chosen algorithm (e.g. `O(k log n)` where
  `k = matched postings`, `n = corpus size`):
- p50 / p95 latency budget on the reference input:
- Memory / footprint budget:
- Benchmark command and expected numbers:

If the chosen approach cannot meet these targets, escalate at PLAN — do not implement,
benchmark, and discover the miss at VERIFY.

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
