# Completion Record — v2.4.0 (plan-execute-review architecture)

**Task class:** medium
**Risk tier:** medium
**Version shipped:** 2.4.0
**Committed by:** Coding Quality Loop harness (self-hosted)

## Goal

Recast the Coding Quality Loop around a canonical **PLAN → EXECUTE → REVIEW** loop where context is a scarce declared budget and each phase is closed by its own verification gate before the next may start. The previous nine-step lifecycle survives as sub-steps mapped onto the three phases, so no existing record, machine name, config, or automation breaks.

## Contract

`v240-validation-contract.md` (9 acceptance criteria, AC1-AC9). Kept in-repo alongside this record because it is the definitive statement of intent for this release.

## Implementation summary

Five slices, four executed by parallel sub-agents (S1 lifecycle, S2 context budget, S3 phase verification, S4 execution trace, S5 docs sweep) and one integration pass by the parent to reconcile shared-file edits (schema, `quality_loop.py`).

### Canonical lifecycle (S1)

- `SKILL.md` — `## Lifecycle` block replaced with three phases (`PLAN → EXECUTE → REVIEW`) and a sub-step mapping table so every previous machine name (`INTAKE`, `EXPLORE`, `MINIMALITY_GATE`, `PLAN`, `IMPLEMENT_SLICE`, `VERIFY`, `REVIEW`, `PACKAGE`, `RETROSPECT`) still resolves.
- `scripts/quality_loop.py` — added `PHASE` constant, `resolve_phase(step)` helper, and `--phase {plan,execute,review}` on `init-record` that pins the initial phase.
- `assets/agent-record.schema.json` — added optional top-level `phase: enum["plan","execute","review","done","escalated"]`. `check-record` now validates the value if present.

### Context budget as first-class field (S2)

- `assets/context-budget.md` — new asset describing per-phase context envelopes: `inputs`, `excluded`, `output_summary`, `output_summary_max_tokens`.
- `assets/agent-record.schema.json` — added optional top-level `context_budget: {plan?, execute?, review?}`.
- `scripts/quality_loop.py context-check <record>` — new subcommand:
  - requires `output_summary` on every declared phase budget,
  - rejects any overlap between `inputs` and `excluded`,
  - requires that `medium` and `mission` records declare a budget for the currently active phase.

### Per-phase verification gate (S3)

- `assets/phase-verification.md` — new asset describing what closing a phase looks like (verifier, evidence, status).
- `assets/agent-record.schema.json` — added optional `phase_verifications: [{phase, verifier, status, verified_by, evidence, notes}]`.
- `scripts/quality_loop.py verify-phases <record>` — new subcommand:
  - requires a `passed` verification entry for the current phase and for every prior phase (order: `plan → execute → review`),
  - rejects any entry with status `failed`,
  - rejects `review` verified by `same_agent` on `medium` or `mission` tasks (independent-review rule as an executable check),
  - requires evidence commands on `execute` and `review` entries.

### Execution trace substrate (S4)

- `assets/execution-log.jsonl.md` — new asset describing the JSONL trace format.
- `assets/synthetic-log-clean.jsonl`, `assets/synthetic-log-loop.jsonl` — fixtures.
- `scripts/quality_loop.py trace-audit <log.jsonl>` — new subcommand:
  - flags `(tool, args_hash)` repeated ≥3× consecutively as a pathological loop,
  - aggregates per-phase step count, wall-clock duration, and total cost when present.

### Eval-cases gate execution (post-review fix for AC7)

- The `eval-cases` runner now honours a new `record_fixture` field on cases. If a case declares `gate` (a `quality_loop.py` subcommand) and `gate_fixture_expectation` (`pass|fail`), the runner writes the fixture to a temp file, executes the gate against it, and asserts the observed exit-code sign matches. Cases `12`, `13`, `14` were rewritten to actually exercise `context-check` and `verify-phases` end-to-end.

### Docs, examples, packaging (S5)

- `CHANGELOG.md` — v2.4.0 entry with the guiding principle statement, sub-step mapping table reference, and pointers to the new subcommands.
- `README.md` — badge bumped to 2.4.0 and eval count updated to 14.
- `references/lifecycle.md`, `references/agentic-orchestration.md` — three-phase framing threaded through, sub-step names retained as valid.
- `examples/claude-code/CLAUDE.md`, `examples/codex/AGENTS.md`, `examples/cursor/.cursor/rules/coding-quality-loop.mdc`, `examples/standalone/run-quality-loop.md`, `assets/AGENTS.template.md` — arrow-chain lifecycle lines rewritten as prose ("PLAN groups `INTAKE`, `EXPLORE`, `MINIMALITY_GATE`, `PLAN`; EXECUTE groups `IMPLEMENT_SLICE`, `VERIFY`; REVIEW groups `REVIEW`, `PACKAGE`, `RETROSPECT`.") so no orphan reference points at the old nine-step chain.
- `packages/npm/package.json` — `2.3.2 → 2.4.0`.

## Files changed

**Modified** (13): `SKILL.md`, `scripts/quality_loop.py`, `assets/agent-record.schema.json`, `assets/AGENTS.template.md`, `README.md`, `CHANGELOG.md`, `references/lifecycle.md`, `references/agentic-orchestration.md`, `examples/claude-code/CLAUDE.md`, `examples/codex/AGENTS.md`, `examples/cursor/.cursor/rules/coding-quality-loop.mdc`, `examples/standalone/run-quality-loop.md`, `packages/npm/package.json`.

**Added** (8): `assets/context-budget.md`, `assets/phase-verification.md`, `assets/execution-log.jsonl.md`, `assets/synthetic-log-clean.jsonl`, `assets/synthetic-log-loop.jsonl`, `evals/cases/12-context-budget-missing-medium.json`, `evals/cases/13-phase-verifications-missing-medium.json`, `evals/cases/14-review-same-agent-verifier-medium.json`, plus this completion record.

Also kept in-tree: `v240-validation-contract.md` (the record of intent for this release).

## Minimality decision

Chose to **extend** the existing schema and helper script rather than fork them. Rejected rungs and why:

- *No change* — insufficient: the request is architectural, not cosmetic.
- *Delete/simplify* — insufficient: the new phase envelope and verification gate are additive requirements.
- *Reuse existing helpers* — used for eval-runner extension (`record_fixture` piggybacks on the existing case-file schema and `subprocess.run` path), but new subcommands are genuinely new capability.
- *Standard library* — used throughout (`json`, `pathlib`, `subprocess`, `hashlib`, `argparse`). Zero new dependencies.
- *Native platform behavior* — the trace format is plain JSONL and the log audit is pure stdlib.

Non-negotiables preserved: no security regression (the `review verified_by=same_agent` check is a *tightening*), no data-loss surface (all new fields optional), backward compat verified (AC8).

## Verification evidence

**Eval suite** — `python scripts/quality_loop.py eval-cases evals/cases --config assets/quality-loop.config.example.json`

```
config ok
PASS simple-docs-low-risk
PASS medium-multifile-behavior-change
PASS high-risk-migration-security-escalation
PASS overengineering-trap-minimality
PASS tiny-task-no-mission-artifacts
PASS medium-requires-contract-and-independent-review
PASS security-boundary-triggers-reviewer-and-hard-gate
PASS complexity-brake-catches-unnecessary-dependency
PASS repeated-mistake-becomes-harness-update
PASS performance-sensitive-task-is-medium
PASS under-fanned-monolith-flagged
PASS context-budget-missing-on-medium-fails-context-check
PASS phase-verifications-missing-on-medium-fails-verify-phases
PASS review-verified-by-same-agent-fails-verify-phases

14/14 eval cases passed
```

**Backward-compat spot check** — a v2.3.x record without any of the new fields still validates cleanly with `check-record`.

**Orphan reference sweep** — `grep -rn "INTAKE ->" --include='*.md' --include='*.mdc'` returns only intentional matches: the CHANGELOG history entries and the frozen `examples/ts-search-eval-2026-07-03/variants/claude-cql/` snapshot (a pinned older CQL version used as an eval baseline; must not be edited).

## Independent review

Fresh-context reviewer (`gpt_5_5`, separate session, no read access to my working notes) checked the diff against `v240-validation-contract.md`. Verdict: `request_changes` with four findings:

1. AC2 — `check-record` did not validate the new `phase` enum. **Fixed** — added enum validation.
2. AC4 — `verify-phases` only required an entry for the current phase, not for all prior phases. **Fixed** — now walks the ordered phase list and requires a `passed` entry for each prior phase.
3. AC6 — a loose grep found `INTAKE ->` in four example/template files. **Fixed** — rewrote the arrow-chain lines as prose sub-step groupings in `examples/claude-code/CLAUDE.md`, `examples/codex/AGENTS.md`, `examples/cursor/.cursor/rules/coding-quality-loop.mdc`, and `assets/AGENTS.template.md`.
4. AC7 — eval cases 12/13/14 carried `gate` metadata but the runner did not actually run the gates. **Fixed** — extended the eval-runner to spawn gates against inline `record_fixture` data and assert the exit-code sign.

Reviewer transcript: `/home/user/workspace/cql_v240_independent_review_20260703_0751.md` and `cql_v240_review_command_outputs.txt`.

All four fixes were re-verified end-to-end by re-running the full eval suite (14/14 pass) and re-running the orphan grep (clean).

## Risks and rollback

**Risks:**
- New schema fields are optional and default to absent, so consumers on older CQL versions ignore them. Consumers on 2.4.0 that require the new fields must state so themselves.
- The `verify-phases` rule that rejects `review` verified by `same_agent` on medium/mission is a *policy* — teams that had auto-review disabled will see a new failure. Documented in the CHANGELOG.
- `trace-audit` heuristic (`(tool, args_hash)` repeated ≥3× consecutively) is intentionally coarse. False positives possible on legitimate retry loops. Documented in `assets/execution-log.jsonl.md`.

**Rollback:** `git revert` the release commit. No migrations, no data changes, no external side effects. The npm package on the registry is unaffected because this commit does not publish; the user tags and publishes manually.

## Follow-ups outside the contract (deferred to v2.5.0+)

- Mutation testing (`mutate-lite`).
- Environment manifest.
- Consumer registry / contract testing.
- Phantom-symbol resolution.
- Metrics aggregator.
- AI-authorship covariate.
- Reviewer-heterogeneity rule in `check-config`.
- Prompt-injection labeling.

These were explicit non-goals of v2.4.0 per the validation contract.

## Handoff

Commit is staged locally on `main`. **The commit is not pushed. npm is not published. No release tag is cut.** Those are the user's decisions to make from their own environment.
