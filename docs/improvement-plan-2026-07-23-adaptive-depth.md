# Adaptive depth — right process, right intelligence, per task (2026-07-23, v2 post-validation)

> Status: ADOPTED for Wave 1 + items 3.1/3.2 (operator requested implementation 2026-07-23);
> Waves 2 and 4 remain staged. As-built deltas from this text, each forced by review or
> evidence during implementation: 1.2 ships markers + recalled lessons only (`init-record`
> takes no file args, so path-hit preview was dropped); 1.3 landed as `hosts/` only —
> `scripts/quality_loop*` was rejected because it would force high tier on essentially every
> release of this repo, the exact ceremony inflation this plan fights (revisit on evidence);
> the lexicon gained compound money-math terms after the cross-family security review
> reproduced a bypass (static cases 21 + 23 pin both wording classes), with the
> bare-"invoice totals" residual disclosed and staged;
> 2.2 (non-release teardown naming) was reverted out of the Wave-1 slice by the cross-family
> functional review as scope creep and stays a Wave-2 item; 3.1 landed as count + newest
> names (semantic-version order), not the drafted “shipped N days ago” age line — a git
> checkout has no reliable ship-date source without tag parsing, so age was dropped.
> v1 of this plan was validated before being offered for adoption: deterministic backtests
> against the repo's own records/evals/bench data, two mechanism reproductions, 35
> fresh-context classification trials, and 4 independent critics (3 Claude lenses + 1
> cross-family Codex pass, verdict `request_changes`). v2 is what survived. Three v1
> mechanisms were killed by that evidence; the plan got smaller.
> Evidence: `bench/results/micro-bugfix-live-2026-07-21.json`, `.quality-loop/outcomes.jsonl`,
> ROADMAP §Next, and the validation summary below.

## Thesis (validated, with one correction)

The loop already *scales* — task classes, risk tiers, per-tier evidence rules, routing
variants, progressive disclosure, the smart Stop marker. What it lacks is decision quality at
the **depth decision itself**: task class and risk tier are prose judgments, made cold at
INTAKE, ratcheting only upward, informed by none of the recorded history.

The correction the trials forced: the fix is **not** a recommendation engine, and not even an
advisory recommendation — it is (a) settling the boundary doctrine so the contested judgment
disappears, and (b) surfacing the deterministic floor at intake instead of at verify.
**Anchors don't create consistency; floors do.** (35-trial result, §Validation.)

Evidence base, all in-repo:
- Same billing micro-task tiered `low`×1/`medium`×2 across bench seeds; replicated here 1/4
  low/medium split at n=5 unassisted. Root cause validated: the task's natural wording
  ("invoice", "money", "tax") hits **zero** `BOUNDARY_KEYWORDS`, so the deterministic floor
  never anchored anything — and the doctrine itself is underdetermined (is money-math without
  a payment-processing surface "the payments boundary"? five thoughtful rationales split).
- Full-vs-baseline on the micro task: 8.1× out-tokens / 7.65× cost / ~10× wall, identical
  objective quality. The overhead is **behavioral** (lifecycle machinery), not the always-loaded
  text: the cut-candidate prose measures ~356 tokens, noise against a 1.14M in-token delta.
- 2 of 3 recorded outcomes are regressions in the loop's own process machinery.
- A LOW record with a README-only diff whose goal mentions "payments" draws **11 blocking
  errors** (reproduced), including a demanded security-review object — and the documented
  "security … or blocked rationale" satisfaction path is not honored by the code
  (`_tier_check_fails` counts pass-labeled rows only; candidate defect at validation time — fixed and eval-pinned in the Wave-1 as-built, static case 22).
- Record-less dirty stops are blocked in any loop-active repo (reproduced both directions).
- The dogfood store holds 0 lessons; the dogfood `high_risk_paths` is empty even though the
  v6.1.0 record's `high` tier (hook-wiring risk) had no deterministic signal to stand on.

## Design rules (inherited, unchanged)

Queries not engines; config after evidence; floors never lower; advisory vs enforced labeled;
every mechanism §6.3-prunable — including everything below.

## Wave 1 — settle the boundary doctrine; surface the floor early (accuracy)

**1.1 One doctrine decision + lexicon recalibration** (the load-bearing item; ROADMAP §Next
item 1 executed). Decide once: does money-math without a payment-processing surface sit inside
the payments boundary? Encode the answer in `BOUNDARY_KEYWORDS` (e.g. "invoice", "money
rounding" in — or an explicit mention-vs-use line documented out), one sentence in SKILL.md,
eval-pinned in both directions against the bench task's real wording. Also reconcile floor
semantics — SKILL says boundary ⇒ "medium+", `detect_risk_floor` forces `high`; one truth.
Per-task ambiguity dies here, not in per-task advice.

**1.2 Early floor preview, one surface, no schema change.** `init-record` prints, at creation
time: the floor markers its goal already trips ("these WILL bind at verify: tier forced
high"), the memory-recall digest, and `high_risk_paths` hits for any named files. A statement
of fact about the gates, not a recommendation. No new subcommand, no `classification` record
object, no divergence field (v1's recorded-recommendation design is **withdrawn**: trials
showed anchors get argued with, not followed, and critics showed the anchor is spoofable
unless verify recomputes it — at which point it is just the floor, which already exists).

**1.3 Dogfood personalization by existing config key.** Set this repo's `high_risk_paths` to
its own enforcement surface (`hosts/`, `scripts/quality_loop`) — the two-line change that
would have made the v6.1.0 `high` tier deterministic — and document the pattern for consumers.

**1.4 Make the high-tier demands satisfiable as documented — no floor lowering.** v1 proposed
downgrading text-floor forcing to advisory on docs-only diffs; **withdrawn** — killed by all
four critics independently (in an agent repo `.md` IS the control surface — SKILL.md/CLAUDE.md
instruction-weakening would ride the downgrade; `docs/` prefixes admit `conftest.py`; and it
lowered a floor this plan's own rules declare untouchable). The reproduced 11-error pain is
addressed without lowering anything: settle the `needs_security` message/code mismatch (honor
a `blocked`-with-reason security row exactly as the finding text already promises, or fix the
message — either way eval-pinned), and rely on 1.1's doctrine line plus 1.2's preview so the
wording is honest before work starts, not litigated after.

## Wave 2 — flatten the cliff on the honest path (complexity; separate reviewable slices)

**2.1 The open cut candidate, decided honestly.** Operator decision as ROADMAP already owes:
cut the always-loaded ladder/class prose (~356 tokens) or reject with reasons. Framing
corrected per validation: this is always-loaded hygiene, **not** the 8× fix. If cut, every
canonical pointer that names SKILL.md as home (risk-boundary list, rung ladder, task classes)
is repointed in the same change — one-truth-per-thing is not optional here. Own PR.

**2.2 Small-lane teardown naming.** Non-release records archive to
`docs/records/<task-id>-agent-record.json`; task_id sanitized at archive time (no separators,
no `vX.Y.Z` mimicry); explicitly subject to the same check-record lint and review-yield
surfaces as release records. Convention + validation only.

**2.3 The two field defects, tightened per critics.**
- *Pre-committed failing test waiver:* machine-checkable only — the waiver is a `red_green`
  row whose base-RED is proven by the existing `run-evidence --red-green` replay (RED at base
  ⇒ the failing test predates the task). Free text never disarms the gate (existing waiver
  doctrine, kept).
- *`same_family_fallback`:* descriptive-only degraded mode. It changes no gate outcome and is
  never a pass-path; it makes `verify` print a loud NOT-INDEPENDENT-FAMILY banner instead of
  letting a same-family review masquerade as independent. The heterogeneity floor stays
  exactly as enforced today.

**2.4 Cliff evidence before cliff changes.** `_loop_was_active` stays as-is (it guards the
untracked-record-deletion hole; confirmed by reproduction). The stop gate itself appends a
one-line JSONL counter row on each missing-record block (stdlib, no control-plane dependency —
v1's control-plane counter is corrected). Relaxation is a future decision on that evidence.
Documented residual (pre-existing, unchanged): diff-splitting across *records* is not unioned
by any gate; noted, not mechanized.

## Wave 3 — feed history honestly (personalized/up-to-date)

**3.1 `brief` freshness line:** archived records missing an outcome ("v6.5.0 shipped N days
ago, outcome unrecorded") beside the existing 90-day `as_of` staleness warning. This is the
actual unlock for any future history use: outcomes exist for only 3 of 9 archived records.

**3.2 Dogfood memory via the existing override.** Set `memory.location: "local"`
(`~/.quality-loop/<project-slug>/` — already shipped) and start committing lessons. v1's
global-store idea is **withdrawn** (cross-repo advisory-injection channel; global is for
cross-project conventions) and a gitignored in-repo store is ruled out (the memory eval reads
the live tree and would fail on every local run). Zero mechanism; an operator config line.

**3.3 The outcomes×paths join is cut.** v1 proposed it as an intake signal; backtests showed
release-granularity joins have zero discriminating power (every release touches the same core
files; a README typo got bumped to medium before the display-only demotion), critics showed
the inputs are agent-writable and outcome rows are release-scoped, n=3. Revisit only if
task-scoped records with recorded outcomes ever become dense; not scheduled.

## Wave 4 — settle depth and intelligence by measurement (right intelligence)

**4.0 Amend the protocol first — the v1 "pre-registered" claim was wrong.** The two candidates
(executor-delegation topology; review-leg effort `high` vs `xhigh`) exist only as follow-ups
in the v6.5.0 record — `bench/PROTOCOL.md` has no such arms, metrics, or decision rules, and
§6.1's R5 rule is scoped to the webapp task. Before any run: a dated protocol amendment adds
the treatments, tasks, metrics, and forced outcomes, and reconciles the R5 scoping. Then the
discriminating-tasks precondition and the runs proceed per ROADMAP §Next items 2–3 (pointer,
not a restatement). §6.3 pruning applies to every Wave 1–3 addition here.

## Validation results (2026-07-23) — what was run, what it changed

Protocol pre-registered before running (scratchpad `validation-protocol.md`); instruments: a
prototype of v1's classify assist backtested on all 9 archived records, the 20-case eval
corpus, and the bench task's real wording; two scratch-repo reproductions; 35 schema-forced
fresh-context trials (5 scenarios × bare/assisted/wrong-anchor arms, Sonnet, no tools); 3
Claude critic lenses + 1 cross-family Codex review of the plan itself (~0.9M subagent tokens).

- **H1 inconsistency replicates: CONFIRMED.** S1 bare: 4× small/medium, 1× small/low — same
  split shape as the bench seeds. Class was consistent; the variance lives in tier.
- **H2 anchor collapses variance: REFUTED.** S1 assisted still split (3× medium, 2× low);
  agents explicitly argued the "payments" marker was a false positive rather than following
  it. Anchoring aligned answers only on uncontested scenarios. Consequence: v1's
  recommendation/divergence design withdrawn; consistency must come from doctrine + floor
  (Wave 1.1) surfaced early (1.2).
- **H3 no rubber-stamping: CONFIRMED.** A deliberately wrong low anchor on a migration+authz
  task was overridden 3/3 with correct reasoning — advisory signals are safe in the dangerous
  direction.
- **H4 lexicon gap: CONFIRMED.** Bench prompt verbatim and plausible agent goals trip zero
  markers; only docstring-quoting wording ("billing service") fires. The floor also fires at
  verify, after the ceremony decision — hence 1.2's intake preview.
- **H5 docs-only pain: CONFIRMED** (11 blocking errors on a 2-line README edit) — but the v1
  remedy was killed as a floor-lowering with three independent smuggling vectors; replaced by
  1.4's satisfiability fix. Side-finding: `needs_security` promises "or blocked rationale" and
  did not honor it (blocked-with-reason security row failed; fixed and eval-pinned as-built, case 22).
- **H6 cliff mechanism: CONFIRMED** both directions (block with progress.md, allow without).
- **H7 path history: paths 9/9, outcomes 3/9** — outcome-starved, not path-starved; join cut
  (3.3), outcome nag kept (3.1). Prototype v0 also produced a README-typo→medium bump from
  release-granularity noise before being demoted — the failure mode the critics then
  generalized.
- **H8 backtest sanity: v0 FAILED then passed redesigned.** Always-recommend under-tiered
  11/19 eval cases (systematic-down = floor erosion, pre-registered fail); abstain-mode fixed
  it (firm recommendations: 0 below-declared; the 2 above-declared are the floor-evasion eval
  cases where forcing is the expected result). The surviving firm signals are exactly the
  deterministic floors — which is why v2 ships the floor preview and no recommender.
- **H9 determinism: PASS** (byte-identical reruns) — with the Codex scoping accepted: this
  proves implementation repeatability over given inputs, not consistency over agent-chosen
  wording; the wording problem is solved by 1.1, not by determinism claims.
- **Critic round:** Codex `request_changes` (1 blocker, 6 major) + three Claude lenses
  (`needs_changes` ×3, 24 findings). Every blocker/major is either fixed above (1.4 reshape,
  Wave 4.0 pre-registration correction, 3.2 store correction, 2.3 tightening, surface
  collapse to 1.2, join cut, cut-candidate reframing + unbundling) or was already fixed by the
  backtests before the critics confirmed it (history auto-bump). No finding was rebutted
  without a stated reason; the adjudications live in this section and the wave texts.

## Non-goals (unchanged)

No dial engine, no machine-readable model catalog, no escalation runtime, no auto-class
enforcement, no new subsystems. Class count (4→2) stays behind Wave 4 evidence.

## Sequencing

Wave 1 items 1.1–1.4 are one small release (gate scripts + evals + one SKILL sentence). Wave
2's items land as separate reviewable slices (2.1 is its own operator-decision PR). Wave 3 is
config + one brief line. Wave 4 starts with the protocol amendment, not with runs.
