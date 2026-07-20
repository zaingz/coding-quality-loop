# Critical review: coding-quality-loop v3.1.0

Date: 2026-07-09
Author: Claude Fable 5 (orchestrator), with three independent fresh-context repo audits (architecture/docs, gate scripts, claims-vs-evidence) and primary-source web research
Status: findings verified. R1–R4 and R6–R8 implemented in v3.2.0 (branch v3.2-trust-chain, same day); R5 deferred pending n≥3 live replication. Counts and file:line references in this document describe the pre-v3.2 state they audited.

## Method

- Three parallel fresh-context audits read the full docs layer (SKILL.md + 8 references), the full enforcement layer (4 Python modules, 3,381 lines, plus hooks and eval runners), and the full evidence layer (README, all 5 live-eval directories, bench, ROADMAP, CHANGELOG, comparison.md).
- The orchestrator independently verified: all 121 offline eval cases pass (11 static + 32 behavioral + 26 memory + 20 reality + 13 routing + 10 trigger + 9 hook, re-run 2026-07-09); gate depth is blind to executor model; no token/cost accounting exists anywhere in the loop; `action.yml` executes the user-checkout copy of the gate script; the three ecosystem citations in the Droid spec are real (Anthropic advisor strategy 2026-04-09, Opus 4.8 dynamic workflows 2026-05-28, Cognition smart-friend 2026-04).
- External research: Anthropic advisor-tool docs and blog; Claude Code workflows/agent-teams docs; arXiv:2607.06906 (harness leverage), arXiv:2607.03691 (scaffolding evolution / Agentic QA), arXiv:2604.27891 (in-context vs orchestration), Lita/Agent Complexity Law, Portkey harness-tax measurement, LessWrong/HAL scaffold-model interaction data, Cognition "Multi-Agents: What's Actually Working".

## What is genuinely good (verified, not softened)

- The reality layer (`quality_loop_reality.py`) is real engineering: command re-execution, red/green worktree replay at base, phantom-completion detection, sidecar-not-record discipline, explicit `not_proven` over silent pass.
- The memory module is clean: deterministic recall, atomic writes, budget-capped, secret-redacted.
- `check-config` reviewer heterogeneity and the reasoning-effort ceiling are enforced, not advisory.
- The candor culture is above ecosystem average: the Codex −1.11 regression is on the hero dashboard in red, the gate-gaming incident is published, the "What it does NOT enforce" table is unusually honest.
- The offline eval suite of the harness itself is proto-"Agentic QA" — arXiv:2607.03691 now calls for exactly this practice, and almost nobody else does it.

## Central findings

### F1 — The enforcement inversion (highest severity)

The product's identity is "deterministic gates over advisory text." In the shipped system:

- The automatically enforced path (`stop_gate → verify-gates --against-diff`) validates a JSON document the agent authors about itself. Evidence strings are accepted verbatim (`has_evidence` accepts any non-empty string); the "independent review" is a self-written object (`fresh_context: true`, `verdict: "approve"`, string-compared reviewer name). Nothing in the automatic path proves a second model ever ran.
- The checks with real teeth — `run-evidence`, `--red-green`, the `verify` umbrella — are wired into no hook. They run only if a human invokes them or the CI action is installed.
- The stop gate fires only at `status ∈ {package, done}` (`hosts/claude-code/stop_gate.py:60`) — a self-reported field. An agent that never advances status stops ungated.
- The CI action (`action.yml:30`) runs `scripts/quality_loop.py` from the **user's checkout**, not `${{ github.action_path }}`. The documented gate-softening attack (webapp eval incident) therefore works end-to-end: soften the local script, commit it, and CI executes the softened copy. The v3.1 helper-integrity hash is printed by the same tamperable script and is explicitly non-blocking.
- Hostile count across the 8 Hard Rules: 2 have execution/git grounding (evidence, test-gaming — both bypassable via self-declared waivers and keyword phrasing); 6 reduce to presence/keyword checks on self-reported fields.

The distinctive engineering (reality layer) exists; it is simply not on the enforced path. The lock exists, the key is taped to it, and the lock trusts a mechanism the attacker controls.

### F2 — The evidence base has one real methodology flaw and several framing debts

- **Methodology contradiction:** `archive/eval-runs/rust-procmon-eval-2026-07-03/README.md:85` states its arms were built by Perplexity model-proxy subagents, "same pattern as the existing sudoku-agent-eval-2026-07-01" — yet the README headlines Sudoku 07-01 as one of "three live cross-agent evals" and its results.json records no CLI versions or invocation method. Only webapp 07-07 is unambiguously real-CLI (exact versions, browser-verified). This is the single most quotable weakness if the repo hits a skeptical audience.
- **Selective headlining:** five eval directories exist; the README references three. The omitted ts-search eval contains the largest effect in the corpus — Codex/GPT-5 **−9.0**, a 60× runtime regression caused by the Right-Size Gate pushing a monolith.
- **D7 dominance:** in three of five evals the lift is largely the process-artifact dimension — the tool is graded up for producing the artifacts the tool mandates. The README's excl-D7 headline is honest; the general "CQL improves quality" takeaway is not supported for strong models.
- **Own rules violated:** README:269 mandates recording cost per live sweep; neither live results.json has any cost/token field. ROADMAP concedes 3–6× wall-time overhead; the token cost is unmeasured.
- **Doc drift:** ROADMAP.md, docs/comparison.md, and docs/launch-kit.md still say 116 cases; README says 121. For a project whose brand is checkable numbers, internal inconsistency is disproportionately damaging.
- **Every cell is n=1**, judges are same-family LLMs, and webapp judges swapped ranks 2/3 at deltas of 0.24 points.

### F3 — The harness-model effect is a model-specific interaction, not a strength gradient

Assembled per-agent results (code-quality framing where separated):

| Agent | Sudoku 07-01 | Webapp 07-07 | ts-search 07-03 | procmon 07-03 |
|---|---:|---:|---:|---:|
| Droid/GLM-5.2 | +8.0 | — | — | — |
| Claude Code | +4.5 | +6.67 | +15.0 | ~flat |
| Codex/GPT-5 | +1.0 | −1.11 | −9.0 | ~flat |

SKILL.md philosophy #8 ("the same scaffolding helps weaker models and can hurt stronger ones") is an oversimplification of this data: Claude Code is a frontier model and gets the *largest* lifts, while Codex is flat-to-negative in every eval with identified mechanisms (monolith collapse, product decisions). The correct reading is **scaffold–model interaction** — which matches external evidence (HAL leaderboard data shows the same scaffold helping some models and hurting others; arXiv:2607.06906 shows harness quality gains are capability-dependent and features carry per-model floors; Cognition found cross-frontier delegation works as capability routing, not difficulty escalation).

Implication: CQL applies one uniform process to every model and cannot detect when it is hurting the model in front of it. The routing config already knows the model per role; gate depth ignores it. The −9.0 regressions were caused by advisory scaffolding and were fixed with more advisory scaffolding — there is still no mechanism.

### F4 — Context scarcity is preached, not practiced

- Realistic process overhead for a diligent medium loop: **~15,000–22,000 tokens** of scaffolding text (SKILL body ~3.5k + references pulled ~12k + prompt cards + subcommand output + record) before reading a line of the codebase.
- Duplication across the docs: the right-size ladder appears ~7 times; the task-class table 3 times; the phase prose 4 times; model-selection heuristics twice *within* agentic-orchestration.md. The class "medium" is defined three different ways (SKILL.md:23 vs engineering-operating-system.md:61 vs lifecycle.md:70).
- The Cursor rule sets `alwaysApply: true` — the full loop loads on every trivial edit, the exact process theater the skill disclaims.
- Dead machinery: `resolve_phase` is called by nothing; no gate consumes the `phase` field; the v2.4 "three-phase model" is presentation, not mechanism. Version markers span four universes (1.4.x, 2.3.x, 2.4.0, 3.1.0).

### F5 — The orchestration story is inverted, and the ground has moved

The largest reference doc (agentic-orchestration.md, ~4,900 tokens) gives most of its weight to features the package cannot execute (mission fan-out, worktree isolation, smart friend — self-labeled an "open problem"), while its genuinely working surface (routing config, setup-models, heterogeneity check, effort ceiling) is a fraction of the page count.

Meanwhile the hosts have commoditized same-vendor orchestration in 2026: Claude Code ships subagents, agent teams, and dynamic workflows natively; Anthropic ships the advisor tool as an API primitive. A harness-agnostic *orchestration* layer is now swimming against the current. What no host ships, and what CQL uniquely has pieces of:

1. A **harness-neutral evidence/gate layer** (the state record + reality checks),
2. **Enforced cross-vendor reviewer heterogeneity** (hosts orchestrate their own vendor's models),
3. **Agentic QA of the harness itself** (the offline suites — now legitimized by the literature).

That triad is the moat. Orchestration breadth is not.

### F6 — Eval-suite honesty gaps

- The 10-case **trigger suite is structurally incapable of failing**: its default heuristic grader is a keyword list reverse-engineered from the exact 10 prompts it grades. The real grader (`--judge-command`) is not supplied in CI. Ten of the headline 121 cases are tautological.
- The behavioral suite's expected-PASS fixtures are records full of fabricated evidence strings and self-declared review objects — the suite encodes the gaming vectors as the accepted baseline. This is correct for testing the checker's mechanics but must not be conflated with quality assurance.
- Engineering hygiene: `quality_loop.py` is a god module (17 responsibilities, four functions >100 lines); reviewer-heterogeneity logic is triplicated with divergent guards; status sets are magic literals in ~6 places; four-plus installed copies of the gate scripts can drift.

## Scorecard against the stated principles

| Principle | Verdict |
|---|---|
| Context is the scarce resource | Preached in the model's face, violated in the package's own docs (F4). Metadata-first disclosure is disciplined; the reference layer is not. |
| Right LLM for the right job | Routing + heterogeneity genuinely enforced; but the *process* is model-uniform and the project's own data shows model-specific harm with no mechanism to adapt (F3). |
| Traceable, reviewable, verifiable | The reality layer is the best-in-class piece; the automatically enforced path is self-attestation, and the CI anchor runs a tamperable copy (F1). Largest gap between brand and mechanism. |
| Maintainable, DRY, SOLID | reality/memory modules clean; god module, triplicated logic, ×7 doc duplication, version drift (F6, F4). |
| YAGNI / ponytail | Applied to the user's code (Right-Size Gate); not applied to the process itself — no gate earns its tokens, dead phase machinery ships (F4, R3). |

## Recommendations (prioritized by ROI)

### R1 (P0) — Close the enforcement inversion

The core promise is trustworthy gates; make the trust chain real before adding anything.

- `action.yml`: execute from `${{ github.action_path }}/scripts/` so CI runs the pinned action's pristine copy, not the user checkout. One-line class of fix; closes the published attack end-to-end.
- Stop gate: fire whenever a record exists **and** the working tree/branch diff is non-empty, with tier-appropriate gates — not only at self-reported `package/done`. An agent that never advances status must not stop ungated.
- Wire `verify` (which re-executes evidence) — or minimally `run-evidence` — into the stop path for medium+ risk, with a documented latency budget. If that is too slow locally, state explicitly in README: local = shape checks, CI = ground truth, and ship the CI workflow wired by default in `init-record` scaffolding.
- **Validation:** new reality/hook eval cases: (a) stop-gate fires at `implement` status with a dirty tree; (b) action-path test proves CI uses the pinned copy; (c) red-team replay of the documented gate-softening attack now fails in CI. The attack replay becomes a permanent eval case.

### R2 (P0) — Repair the evidence base (cheap, urgent for the candor brand)

- Resolve the Sudoku 07-01 contradiction: either document real-CLI invocation with versions, or relabel it a model-proxy run and move it out of the "live cross-agent" headline.
- List all five evals in the README table, ts-search −9.0 included. The negative result is the project's most credible asset; hiding it is the least credible move.
- Fix the 116→121 drift (ROADMAP, comparison.md, launch-kit).
- **Validation:** extend the static suite with a numbers-consistency lint (grep the case count across the four docs; fail on mismatch). README eval table row count = 5.

### R3 (P1) — Instrument the process tax

The repo mandates cost recording (README:269) and doesn't do it; the literature (arXiv:2607.03691) shows harnesses silently double token spend while passing all functional checks.

- Add `cost_usd` / `tokens_in` / `tokens_out` / `duration_sec` per arm to the live-eval schema and per-run capture guidance to the record schema; have `bench` print them.
- Publish the measured overhead (currently ~15–22k tokens scaffolding per medium loop, 3–6× wall time) in the README next to the lift numbers. A skeptic's first question should be pre-answered.
- Adopt the rule reflexively: **every gate must earn its tokens** — additions and retentions justified by eval delta per token, deletions celebrated in the changelog (v3.0 already did this once; make it policy).
- **Validation:** eval case asserting cost fields present for medium+ bench records; README shows overhead; next live run's results.json contains cost.

### R4 (P1) — Fix the trigger suite

- Wire a real LLM judge in CI (cheap model, cached), or remove the 10 cases from the headline count and label them a smoke fixture.
- **Validation:** mutation test — changing SKILL.md's description must be able to turn the suite red. An eval that cannot fail is not an eval.

### R5 (P2) — Replicate, then adapt process depth per model

Sequenced after R3 because it needs cost data, and after R2 because the current signal is n=1.

- Rerun the webapp 2×2 at n≥3 seeds with cost capture and a third out-of-family judge (Gemini-class) as tiebreak.
- If the Codex-negative interaction replicates: add `process_depth: full|light` to model profiles in the routing config. Light profile keeps contract + evidence + independent review, drops minimality ceremony and right-size prompting (the identified monolith-collapse mechanism). This turns "calibration" from prose into config the gates consume — the routing layer already knows the model; connect it.
- **Acceptance:** Codex regression eliminated under light profile while GLM/Claude lift is retained, at n≥3.

### R6 (P2) — Practice context scarcity on the package itself

- Single-source the duplicated tables (task-class, ladder, phases) — one canonical location, pointers elsewhere. Target: reference corpus −40–50% tokens.
- Unify the three divergent definitions of "medium."
- Fix Cursor `alwaysApply: true` → scoped/agent-requested.
- Delete the dead phase machinery (`resolve_phase`, the unread `phase` field) or wire a gate to it; one version universe across the package; move `v240-validation-contract.md` to `archive/` and update the three pointers in `assets/completion-record.md` (do not `git rm` — the completion record deliberately keeps it).
- **Validation:** token count of `references/` before/after in the changelog; static lint for the single-source tables; grep shows one definition of medium.

### R7 (P3) — Reposition the orchestration story

- Rewrite agentic-orchestration.md so page-weight matches what runs: the working surface (routing config, setup-models, heterogeneity, effort ceiling) first; mission topology and smart friend compressed to an explicit "host-provided patterns, not shipped" appendix.
- Add a short topology decision note covering the two 2026 patterns: orchestrator-delegates (host-native dynamic workflows / agent teams) vs executor-consults-advisor (Anthropic advisor tool, API-level primitive — not wireable via CLIs), with Cognition's caveat that advisor topology needs a strong executor; with a weak primary (GLM-class), keep orchestrator-delegates.
- One-page cross-CLI review recipe (claude ⇄ codex ⇄ droid headless commands with verified flags: `claude -p --safe-mode`, `codex exec -s workspace-write`, `droid exec`) — this is the useful kernel of the Droid spec's Deliverable 2. Note that harness difference does not guarantee model heterogeneity (Droid can run Claude models); `check-config` remains the arbiter.
- Sharpen the moat framing in README/comparison: evidence layer + cross-vendor heterogeneity + Agentic QA, against Superpowers/Spec Kit/BMAD who do process but none of the three.

### R8 (P3) — Engineering hygiene

- Extract a `quality_loop_core.py` (record I/O, redaction, predicates, status-set constants, atomic write, git wrapper) to break the god module's star coupling and the memory module's lazy circular import.
- Deduplicate the triplicated heterogeneity logic; drive `check_record` from the existing JSON schema instead of a parallel imperative validator.
- Kill dead surface: `brief_routing_lines`, divergent example-tree script variants.
- **Validation:** existing 121 cases stay green (the suites are exactly the safety net this refactor needs); module line counts in changelog.

## Relationship to the Droid spec (docs/spec-2026-07-09-critical-review-and-headless-orchestration.md)

The spec's research citations are real and its hygiene instincts are directionally right, but this review supersedes its assessment in three ways:

1. It scored traceability "already strong"; the audits show the automatically enforced path is self-attestation and the CI anchor runs a tamperable copy (F1). The critical review it planned would likely have found this; this document delivers it.
2. Its centerpiece (Deliverable 2, a broad headless-orchestration docs layer) expands documentation where the evidence says contraction is needed (F4), and duplicates what hosts now ship natively (F5). Keep only the cross-CLI review recipe and the topology decision note (R7).
3. Its hygiene item (`git rm v240-validation-contract.md`) would break three documented links in `assets/completion-record.md`; archive with pointer updates instead (R6).

## Suggested sequence

R1 + R2 first (they defend the product's core promise and brand and are small), R3 + R4 next (instrumentation and eval honesty), then R5 (replication → adaptive depth, the highest-ceiling change), with R6–R8 as the ongoing shrink-and-harden track. Everything lands with eval cases attached; nothing ships on prose alone — that is, hold the harness to its own standard.
