# CQL v2.4.0 — Validation Contract

## Goal (one sentence)

Recast the Coding Quality Loop around three named phases (PLAN → EXECUTE → REVIEW), with context as a scarce resource and per-phase verification as the terminating condition, replacing the current 9-step lifecycle without breaking existing users.

## Guiding principle

An LM runs a plan-execute-review loop. Context is a budget. Verification terminates each phase. Extra sub-steps inherit one of the three roles; nothing is unlabeled.

## Acceptance criteria (each paired with a concrete check)

1. **AC1 — Three phases are canonical.** `SKILL.md` presents PLAN / EXECUTE / REVIEW as the primary lifecycle, with the previous nine steps demoted to sub-artifacts of a phase.
   - **Check:** the `Lifecycle` section in `SKILL.md` names exactly three top-level phases; the previous nine machine names (`INTAKE`, `EXPLORE`, ...) remain as sub-step aliases in a mapping table.

2. **AC2 — State schema carries `phase`.** `assets/agent-record.schema.json` gains a `phase` field with enum `["plan", "execute", "review", "done", "escalated"]`; existing `status` field is kept for backward compatibility and mapped.
   - **Check:** `python scripts/quality_loop.py check-record` on a v2.4.0 record with `phase: "execute"` passes; on a record with an invalid phase, fails.

3. **AC3 — Context budget is a declared, checkable field.** Each phase declares `context_budget = { inputs: [...], excluded: [...], output_summary: "≤N tokens" }` in the state record and/or `assets/context-budget.md`.
   - **Check:** `python scripts/quality_loop.py context-check <record>` flags phases with missing `context_budget` (medium/mission), missing `output_summary`, or overlapping `inputs` and `excluded`.

4. **AC4 — Per-phase verification block terminates each phase.** State record `phase_verifications` array with one entry per phase completed: `{phase, verified_by[], evidence[], verifier, status}`. `status: "verified"` is required to advance to the next phase for medium/mission.
   - **Check:** `python scripts/quality_loop.py verify-phases <record>` fails when a medium/mission record advances phases without a verified block, or when `review` phase has `verifier == plan_or_execute_agent`.

5. **AC5 — Execution trace substrate exists.** `execution-log.jsonl` format is documented; `python scripts/quality_loop.py trace-audit <log>` detects pathological loops (`tool:args_hash` ≥3× consecutive) and reports per-phase cost/duration.
   - **Check:** trace-audit correctly flags a synthetic log with a 3-repeat loop; reports totals grouped by `phase`.

6. **AC6 — Docs are consistent.** `README.md`, `CHANGELOG.md`, `SKILL.md`, `references/lifecycle.md`, `references/agentic-orchestration.md`, `examples/`, `hosts/`, and the minimal drop-in prompt all refer to the three-phase model. No orphan reference to the old lifecycle order remains.
   - **Check:** `grep -rn "INTAKE -> CONTEXT MAP -> SPEC" .` outside historical / CHANGELOG contexts returns nothing.

7. **AC7 — Eval cases pin the new gates.** At least 3 new eval cases: (12) missing `context_budget` on medium fails; (13) missing `phase_verifications` on medium fails; (14) review verified by same agent as execute fails.
   - **Check:** `python scripts/quality_loop.py eval-cases evals/cases --config assets/quality-loop.config.example.json` reports all cases (11 + 3 new = 14) pass with expected pass/fail split.

8. **AC8 — Backward compatibility.** Existing v2.3.x records (no `phase` field, old `status` values) still validate as long as they were valid before; a mapping `status → phase` is applied silently.
   - **Check:** All 11 previous eval cases still pass without modification.

9. **AC9 — Package builds and prepack bundles new assets.** `packages/npm/scripts/prepack.mjs` copies new asset files; version bumped to 2.4.0.
   - **Check:** `node packages/npm/scripts/prepack.mjs` produces `dist/skill/` containing the new assets; `packages/npm/package.json` reports `2.4.0`.

## Regression risks

- **R1: Breaking v2.3.x records.** Mitigated by AC8 and by leaving `status` in the schema.
- **R2: Doc drift.** Mitigated by a dedicated docs slice (S5) that touches every doc surface in one PR-equivalent slice.
- **R3: Sub-agent context confusion.** Each sub-agent gets a scoped brief, must not read the audit doc, must implement only its slice.
- **R4: Over-scoping.** Explicitly deferred to v2.5.0+: mutate-lite, environment manifest, phantom-symbol resolution, metrics aggregator, AI-authorship covariate, reviewer-heterogeneity check-config rule. Not in this contract.

## Non-goals for v2.4.0

- No mutation testing.
- No environment manifest.
- No consumer registry / contract testing.
- No prompt-injection labeling.
- No new mandatory dependencies.
- No breaking changes to public `quality_loop.py` subcommand signatures already in v2.3.x.

## Verification plan

Run in order after all slices merge:

1. `python scripts/quality_loop.py check-record` on a fresh v2.4.0 record → pass.
2. `python scripts/quality_loop.py context-check` on the same → pass.
3. `python scripts/quality_loop.py verify-phases` on the same → pass.
4. `python scripts/quality_loop.py trace-audit` on synthetic log → detects loop.
5. `python scripts/quality_loop.py eval-cases evals/cases --config assets/quality-loop.config.example.json` → 14/14 as expected.
6. `python scripts/quality_loop.py --help` → all new subcommands listed.
7. `grep -rn "INTAKE -> CONTEXT MAP -> SPEC" .` outside `CHANGELOG.md` and `docs/history/` → empty.
8. `node packages/npm/scripts/prepack.mjs` → `dist/skill/` contains new assets, `package.json` at 2.4.0.

## Slices

- **S1** — three-phase lifecycle: `SKILL.md`, schema, `quality_loop.py` phase field + `verify-phases` subcommand, status↔phase mapping.
- **S2** — context budget: `assets/context-budget.md`, schema fields, `context-check` subcommand.
- **S3** — per-phase verification: schema `phase_verifications`, `verify-phases` implementation, `assets/phase-verification.md`.
- **S4** — execution trace substrate: `assets/execution-log.jsonl` example, `trace-audit` subcommand, docs.
- **S5** — docs sweep + eval cases + prepack + version bump.

Slices S1-S4 run in parallel (each owns disjoint files, with clear ownership below). S5 runs last, in main context, once S1-S4 have merged.

## File-level ownership (no overlap between parallel slices)

| Slice | Owns (writes/edits) | Reads (context) |
|---|---|---|
| S1 | `SKILL.md`, `assets/agent-record.schema.json` (add `phase`, keep `status`), `scripts/quality_loop.py` (add `phase` param to `init-record`, `verify-phases` subcommand stub, status↔phase mapping helper) | this contract; existing SKILL.md; schema |
| S2 | `assets/context-budget.md` (new), `assets/agent-record.schema.json` (add `context_budget` sub-property under a new top-level field — coordinate boundary noted below), `scripts/quality_loop.py` (add `context-check` subcommand) | this contract |
| S3 | `assets/phase-verification.md` (new), `scripts/quality_loop.py` (implement `verify-phases`), `assets/agent-record.schema.json` (add `phase_verifications` array) | this contract |
| S4 | `assets/execution-log.jsonl.md` (new — format doc), `scripts/quality_loop.py` (add `trace-audit` subcommand) | this contract |
| S5 | `README.md`, `CHANGELOG.md`, `references/lifecycle.md`, `references/agentic-orchestration.md`, `examples/*`, `hosts/*`, `evals/cases/12-*.json`, `13-*.json`, `14-*.json`, `packages/npm/package.json`, `packages/npm/scripts/prepack.mjs`, `packages/npm/CHANGELOG.md` (if present) | all merged S1-S4 output |

**Schema coordination:** S1, S2, S3 all edit `assets/agent-record.schema.json`. To avoid conflicts, each slice adds **only its named property** at the top level and does not touch others. Merge order: S1 → S2 → S3. I (the parent) will apply their edits sequentially with `edit`, not by having them race on the file. Sub-agents will therefore produce their schema edits as **explicit diff proposals in their final message**, not by writing the schema themselves.

## Complexity brake

Highest valid rung chosen: **rung 7 — add minimal new code**. We are adding new subcommands and schema fields, but no new dependencies (stdlib only), no new frameworks, no new services. Rejected lower rungs:
- rung 6 (reuse existing dep): no existing dep provides phase-tracking or trace-audit; would need one.
- rung 3 (reuse existing function): existing `check-record` cannot be repurposed without gutting it.
- rung 2 (delete): the missing capability is real; deletion isn't the answer.

Safety non-negotiables checked: backward compat (AC8), no secrets/auth surface, no destructive migration.
