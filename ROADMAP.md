# Roadmap

> Working notes on what is next, ordered by decreasing certainty. Nothing here is a
> commitment; the loop's non-negotiable is that we ship the smallest correct change,
> and that includes the roadmap itself.

Last updated: 2026-07-21 (v6.3.0).

## Now — landed in v6.3.0 (measured)

The §6.2 micro-task cell **ran**: six live cells, {baseline, full} ×
claude-code × 3 seeds, committed at
[`bench/results/micro-bugfix-live-2026-07-21.json`](bench/results/micro-bugfix-live-2026-07-21.json)
and validated in CI. Every cell was objectively perfect in both arms; the
full path cost **8.1× output tokens / 7.65× dollars / ~10× wall time**
(medians) — ~5× past the §6.2 threshold, yet the pre-registered outcome is
**not claimed**: §6.0's letter forbids any §6 outcome when every arm passes
the objective battery, and every arm did. The results file records
`fires: false` verbatim; §6.0 is amended for future runs only. See
`CHANGELOG.md` §6.3.0.

- ✅ **Cut candidate opened (operator decision, not a fired rule).** The
  always-loaded ladder/class text in SKILL.md is now a documented cut
  candidate, justified by the measured 6–8× overhead but explicitly not
  claimed as a pre-registered outcome (§6.0). The cut itself is deliberately
  NOT taken in the same release that produced the number — it lands (or is
  rejected with reasons) next release, so the measurement and the reaction
  stay separately reviewable.
- ✅ **Measurement integrity.** review-yield dedupe; every archived record
  passes check-record (lint-pinned); void judge numbers annotated where
  quoted; measured cost figures replace the token estimate.
- ✅ **Defaults match claims.** Gate-config-aware `check-config`; loud
  NOT-ENFORCED line for dormant reviewer heterogeneity; CI-anchor +
  `model_routing.host` in installer next steps; `record outcome` in the
  lifecycle text.
- ✅ **Bench tooling.** Protocol recipe rot fixed (`--safe-mode` is gone from
  claude ≥2.x); `bench/runner.py --materialize` makes a §6.2 cell two
  commands.

**Field observations recorded with the data (for the next releases to act
on):** in all three live full arms, the pristine gate failed the finished
record (proving-command mismatches; no bugfix-test waiver for a task whose
failing test is pre-committed), the "independent review" resolved to a
same-family Claude subagent with `ran_checks: false`, and risk tiering for
the same billing task was inconsistent (low ×1, medium ×2).

## Landed in v6.2.0 (prove it, smooth it, learn from it)

v6.1.0 made the trust chain true in the field; v6.2.0 wraps three loops around
it — measure the yield, remove the friction that pushes agents off the honest
path, and feed the shipped outcome back. No new gate: the blocking surface is
unchanged. See `CHANGELOG.md` §6.2.0. The six live `§6.2` benchmark runs are
still deliberately **not** claimed done — they are an operator action, now one
CLI call away rather than a dashboard hand-copy; they remain the named next
milestone below.

- ✅ **Measurement is a query, not a chore.** `control-report --review-yield`
  tables per-record finding counts, resolved `review_findings[]`, and the
  outcome verdict from the records already in git; with the existing
  `--arm-costs` bench-cost query, the numbers a pilot needs are one command
  away. Both are queries — no gate reads them.
- ✅ **Friction removed from the honest path.** A structured `record` CLI
  (`set-status` / `add-evidence` / `add-ac` / `outcome`) does atomic,
  schema-validated writes so the agent advances the lifecycle without heredocs;
  a smart Stop gate skips the `verify` re-execution when a `last-verified`
  marker proves the same diff + status already passed (fails safe to the full
  umbrella on any mismatch); and the canonical gate-case count is derived from
  the suites at runtime, so the badges cannot drift from a hand-set literal.
- ✅ **Outcome feedback closes the loop.** `record outcome
  <clean|regressed|reverted>` records post-merge truth on the record and appends
  to `.quality-loop/outcomes.jsonl`; the next session's `brief` tallies it. The
  field is optional — absence is valid, no gate requires it.

## Landed in v6.1.0 (the field-truth release)

Executed against [`docs/improvement-plan-v6.0.1-2026-07-20.md`](docs/improvement-plan-v6.0.1-2026-07-20.md)
(a same-day second review round: 13 dual-verified majors, then two fresh-context
reviews — Fable xhigh and Codex — whose blocking findings were fixed before
release); see `CHANGELOG.md` §6.1.0. One plan item is deliberately **not** claimed
done: Wave 4.2's six live `§6.2` benchmark runs need `claude -p` over an afternoon
(an operator action, not a code change). Its enabling deliverable — the committed
micro-task spec — landed; the runs themselves are the named next milestone below.

- ✅ **One truth per thing.** One canonical record path
  (`.quality-loop/agent-record.json` — the documented root path structurally
  failed review freshness); the config version pin renamed to what it is
  (schema lineage, with an eval pinning it against drift); the reviewer
  checklist emits the schema's actual 4-value verdict enum; hand-copied
  canonical lists replaced with pointers; one heterogeneity resolver instead
  of three (display can no longer claim "verified" where enforcement bailed).
- ✅ **First contact survives repos that are not this repo.** Onboarding leads
  with a 10-second green walkthrough; demo goals no longer trip the payments
  floor on the word "checkout"; no-origin/develop-default repos diff against
  the best local baseline (merge-base with local main when diverged, else HEAD)
  instead of the empty tree (empty tree kept only under the CI anchor);
  install-manifest paths count as scaffolding; a `git commit` step 0 in every
  printed next-steps block; Windows hooks launch the resolved interpreter
  (npm-smoke now proves a hook fires on all three OSes); a closed record
  (byte-identical to its content at the resolved base ref) no longer blocks every clone at every
  Stop; `action.yml` has a green path for record-less PRs and is dogfooded in
  this repo's CI; and `.claude/settings.json` is committed, so the Stop gate
  and guard fire during CQL's own development for the first time.
- ✅ **Adaptability without a second program.** Exactly three gate-config keys
  (`base`, `tests.path_markers`, `high_risk_paths`); test-weakening/shrinkage
  lexicons extended to Go, Rust, Java, Ruby, C# (Hard Rule 6 was silently
  inert outside Python/JS); waivers must cite a recorded passing command;
  bare-`*` allowlist lines authorize nothing; guard/stop-gate remedies no
  longer contradict each other; claims sharpened to what is enforced
  (merge-base anti-evasion is CI-anchored; Stop auto-executes allowlisted
  commands).
- ✅ **Measurement unblocked at the cheapest price.** `bench/PROTOCOL.md`
  amended before any run (discriminating-power precondition, judges
  cross-family from the arm's model, MDE note, no deletion on judge-noise
  nulls); the §6.2 micro-task spec committed at
  [`bench/tasks/14-micro-bugfix.json`](bench/tasks/14-micro-bugfix.json); the
  cannot-fail trigger fixture deleted; ~1.6 MB of dated eval archives moved to
  `archive/eval-runs/`; first review-yield memo computed from data already in
  git ([`docs/review-yield-2026-07-20.md`](docs/review-yield-2026-07-20.md)).

## Landed in v6.0.0 (the trust-chain release)

Executed against [`docs/improvement-plan-2026-07-20.md`](docs/improvement-plan-2026-07-20.md)
(waves 1–3 plus 4.1/4.2); see `CHANGELOG.md` §6.0.0 for the full item list.

- ✅ **Trust chain (wave 1).** The Stop gate runs the full `verify` umbrella
  (evidence re-execution + AC coverage) at terminal statuses; `--base` defaults
  to the origin/main merge-base so commit-first evasion died; medium+ acceptance
  criteria must carry a `proving_command` matched to a pass-labeled recorded
  command; `blocked` rows are satisfiable with a reason; a net test-shrinkage
  gate blocks deleted/gutted tests at medium+; `protect_harness` makes gate-script
  and record edits tamper-evident; hook failures are truthful (a missing runtime
  is no longer reported as a secret found).
- ✅ **Funnel (wave 2).** Install manifest + real uninstall (`cql remove` /
  `install.py --uninstall`; init → remove leaves `git status` clean); `cql check`
  verifies the manifest; Codex installs ship `AGENTS.md`; one canonical config
  file (root `quality-loop.config.json`); `render-prompt` substitutes
  `{contract}/{diff}/{evidence}` so cross-CLI reviewers stop receiving raw
  placeholders; `docs/quickstart.md` is the single onboarding doc; cursor/pi
  demoted to advisory rules recipes.
- ✅ **Shrink (wave 3).** Medium paper trail 8–9 → 4 artifacts (eval-pinned);
  SKILL.md at 89 lines with zero vendor model ids; one 4-value reviewer verdict
  enum + `ran_checks`; control plane demoted to an opt-in add-on
  (`--with-control-plane`, out of the npm tarball and the headline case count)
  and dieted (session_id joins replace the fuzzy time-window join, droid runs
  are events, drift canaries); memory recall is read-only with one ranked pool,
  provenance, staleness flags, and `--outcome` feedback.
- ✅ **Measurement scaffolding (4.1/4.2).** One pre-registered
  [`bench/PROTOCOL.md`](bench/PROTOCOL.md) (version-neutral arms, committed
  decision rules) replacing three drifting bench docs; CI validates cost fields
  on every committed results file; `control-report --arm-costs` bridges indexed
  sessions to the bench cost schema.

## Landed in v5.0.0

- ✅ **Orchestrator layer (the token-diet release).** The main session owns every
  decision — task class, context map, contract, right-size rung, plan, routing,
  verdicts, stop-if-unsafe — and workers receive a one-screen brief (goal, contract
  slice, files, commands, done-check), never the skill text or a repository tour. The
  always-loaded agent surface is cut roughly in half (`SKILL.md` ~56% smaller); role
  and advisor detail moved to `references/agentic-orchestration.md` on demand.
- ✅ **Two hosts, two vendors.** All shipped routing variants route exclusively to the
  latest Anthropic (Fable 5, Opus 4.8, Sonnet 5, Haiku 4.5) and OpenAI (GPT-5.6
  Sol/Terra) models: Claude Code implements, Codex reviews cross-family. All floors
  unchanged (reviewer family heterogeneity, strong_reasoning on plan/orchestrate,
  effort ceiling at high). Cursor, Droid, and Pi remain supported install targets
  outside the routed kernel. No gate, schema, or runtime behavior changed.

## Landed in v4.3.0

- ✅ **Control plane (local observability).** One dashboard for sessions, model
  calls with exact token usage, tool calls, token spend, routing, hook events,
  and every loop artifact (records, reviews, decisions, plans, escalations,
  memory). `control-index` builds a disposable SQLite cache under
  `.quality-loop/control/` from sources of truth (Claude Code transcripts + CQL
  artifacts); `control-serve` renders a self-contained HTML dashboard on a
  GET-only 127.0.0.1 server; opt-in `SessionStart`/`SessionEnd` hooks
  (claude-code + codex wiring) record events and autostart the server. Stdlib
  only, no message bodies stored, no vendor prices shipped (USD only from a
  user-supplied `control_plane.prices`). 20 new gate cases. See
  [docs/control-plane.md](docs/control-plane.md).

## Landed in v4.2.0

- ✅ **Multi-host model routing.** `agents: {name: {host, class}}` + `main_session`
  express a multi-harness topology (e.g. Claude Code plans, Droid/GLM implements,
  Codex reviews); one `setup-models` run applies every host, with an explicit
  PRINT-ONLY banner for hosts CQL cannot verify (codex, pi) — no fake "applied ✓",
  no pretend drift detection for print hosts.
- ✅ **Family-aware reviewer heterogeneity.** `check-config` compares resolved model
  families across hosts (`family` field or well-known prefix; unknown ids skip).
  Closes the alias hole (`sonnet` vs `claude-sonnet-4-5`) and the cross-host hole;
  `allow_same_family` is the explicit escape hatch.
- ✅ **Routing variants (the intelligence↔cost knob).** Three pre-validated
  `model_routing` blocks in `assets/routing/` + a dated model-menu README with no
  machine consumers. Eval-pinned floors: strong-reasoning tier for plan/review
  classes, different-family review, effort ≤ high.
- ✅ **Escalation as evidence (the R5 evidence base).** Optional `models_used` and
  `escalations` record fields; `verify-gates` requires escalations to cite recorded
  failing commands (self-report is not evidence); RED→GREEN-resolved failures no
  longer block. Cost per accepted record stays a documented `jq` recipe.
- ✅ **Cross-CLI orchestrator recipe (critical-review R7).** `docs/cross-cli-recipe.md`:
  live-verified `claude -p` / `codex exec` / `droid exec` commands per role, with
  the caveat that harness diversity ≠ model heterogeneity.

## Landed in v3.0

- ✅ **Outcome-grounded harness.** Rewrote SKILL.md (477 → 172 lines) with a
  model-adaptive Calibration section citing own eval data. The Right-Size Gate
  fixes the Codex −9.0 failure class (minimal diff ≠ minimal architecture/perf).
- ✅ **`verify` umbrella command.** One command runs record gates, diff audit,
  evidence re-execution, and AC-to-command coverage. Replaces the need to know
  four separate gate commands.
- ✅ **Tool-using evaluator.** Reviewer card v2 requires executing tests, not
  just reading the diff. Verdict records `ran_checks`. Communication-bridge rule
  prevents review loops.
- ✅ **Reviewer heterogeneity.** `check-config` hard-fails when implementer and
  validator resolve to the same model on medium+.
- ✅ **Smart Friend pattern.** Optional role for implementer-to-stronger-model
  consultation on defined triggers.
- ✅ **Ablation eval program.** `bench/ablation-protocol.md` (since merged into
  `bench/PROTOCOL.md`) defined the protocol (3 tasks × 2-3 families × 3 seeds ×
  4 arms). Headline metric excludes artifact dimensions.
- ✅ **40% surface reduction.** Archived legacy adapters, local orchestration,
  v2.4 ceremony surfaces, and stats reporting. Scripts 4,600 → 3,300 lines.
  121 gate cases (as of v3.1) across 7 suites, plus a 10-case trigger smoke fixture.

## Landed earlier — v2.4

- ✅ Three-phase canonical model (PLAN → EXECUTE → REVIEW).
- ✅ Config-based model routing (`setup-models`, per-role, per-host).
- ✅ Reality layer (`verify-gates --against-diff`) with diff-grounded gates.
- ✅ Project memory (files backend, budget-capped recall, secret redaction).

## Next

**1. Act on the §6.2 measurement and the live field observations.** The cut
candidate (always-loaded ladder/class text) gets cut or rejected-with-reasons.
The three process defects the live runs replicated 3-for-3 get fixes: a
bugfix-test waiver path for tasks whose failing test is pre-committed (the
pristine gate failed every honest full-arm record); an honest degraded mode
for single-CLI contexts where cross-family review is structurally unavailable
(record `same_family_fallback` loudly instead of calling a same-family
subagent "independent"); and a risk-tier consistency check for
billing/payments-adjacent wording (tiering of the same task varied low/medium
across seeds — the floor lexicon gap is documented, not yet recalibrated).

**2. Discriminating objective tasks before Wave 4.3.** The judge-based webapp
ablation is underpowered as designed: the one live run had zero objective
discriminating power (§6.0) and the same-packet judge spread (0.25–3.75) is
the noise floor at n=3. Before paying for ~36 judged runs, commit 3–5
bugfix/feature specs in the `14-micro-bugfix` format, hard enough that a
baseline demonstrably fails part of the held-out suite (30–70% target).
Quality-lift claims then rest on objective pass-rate deltas; judges become
secondary.

**3. Wave 4.3, the full live ablation — or retract.** The protocol is
pre-registered in [`bench/PROTOCOL.md`](bench/PROTOCOL.md) (arms, tasks,
judging, cost capture, and decision rules committed before the data exists; a
completed run forces the stated outcome). Everything the project still argues
about in prose — which gates earn their tokens, the R5 per-model process
depth — is decided by that run. Capped at ~36 runs, and gated on item 2 so it
cannot measure judge noise.

### Hardening from the webapp live eval (2026-07-07) — landed

Findings from `archive/eval-runs/webapp-agent-eval-2026-07-07/` (gate-gaming, allowlist
never created, attested review going stale, ImportError on partial installs):

- ✅ `init-record` scaffolds `.quality-loop/allowed-commands`; the `not_allowed`
  finding tells the agent how to fix it.
- ✅ Attestation hashes exclude `.quality-loop/` so record-only trailing commits
  do not stale a review; scope integrity ignores record artifacts.
- ✅ Partial `scripts/` installs fail with an actionable message instead of an
  ImportError traceback (agents were observed stubbing/softening the helper).
- ✅ `verify` prints helper-integrity hashes so hooks/CI can catch a locally
  modified gate script; SKILL.md forbids repairing the helper in-run.
- ✅ Calibration: product-floor for user-facing tasks (process artifacts alone
  lifted Codex totals while code quality fell); reviewer scores product fitness.
- ✅ `hosts/codex/README.md` documents sandbox limits; `bench/live-run-recipe.md`
  (since merged into `bench/PROTOCOL.md`) captured the proven isolation +
  blind-judging mechanics.
- ✅ **Cost/duration per cell** (landed in v6.0.0): `bench/runner.py --validate`
  requires `tokens_in`/`tokens_out`/`duration_sec` on live runs and CI runs it on
  every committed results file; `control-report --arm-costs` fills the fields
  from indexed sessions.

Still open from the same findings:

- **Native-path live test.** One live run per host with the installed skill and
  trusted hooks (the 2026-07-07 run used drop-in delivery for isolation).

- **Live ablation results (Wave 4.3 — the milestone).** Run the pre-registered
  [`bench/PROTOCOL.md`](bench/PROTOCOL.md) with real models and commit results.
  Apply the pruning rule: cut components with no code-quality lift across ≥2
  families — and celebrate the deletions in the changelog.
- **Skills Hub publish.** Validate frontmatter and publish to
  [agentskills.io](https://agentskills.io) so `gh skill install` works without a
  manual copy.
- **VS Code / Zed extension.** Thin extension that surfaces the current record,
  the next gate to satisfy, and a one-click `verify` runner in the IDE status bar.
- **Reviewer diff view.** A read-only web viewer for the state record + diff +
  evidence bundle.
- **Mutation testing (`mutate-lite`).** Check that acceptance-criteria tests
  would catch the intended root-cause mutation.
- **Per-model process depth (critical-review R5).** Add `process_depth: full|light`
  to model profiles once the model-specific interaction (Codex flat-to-negative,
  Claude largest lifts) replicates at n≥3 seeds with cost capture. Deliberately
  deferred from v3.2: config before evidence would be calibration theater.
  v4.2.0 shipped the evidence base (`models_used`/`escalations` per-role model,
  attempts, and cost capture in records); the decision rule is now pre-registered
  in `bench/PROTOCOL.md` — Wave 4.3's run forces the outcome either way.

## Later — exploring, no ETA

- **Cross-repo memory.** Point multiple repos at a shared lesson store so
  team-wide conventions propagate.
- **Sandboxed `run-evidence`.** Optional execution inside a rootless container.
- **First-class MCP server.** Wrap the helper CLI as an MCP server so hosts can
  call gates as tools. Only if it does not require a runtime dependency.
- **Live benchmark leaderboard.** Public dashboard of `bench/` results across
  host + model + seed combinations, updated on tagged releases only.

## Not on the roadmap, on purpose

- **A hosted service.** The loop stays local files, git, and stdlib Python.
  The v4.3.0 control plane does not change this: it is a stdlib server
  hard-bound to 127.0.0.1 over a disposable local cache — nothing leaves the
  machine, and no gate depends on it.
- **A test runner.** `run-evidence` re-executes recorded commands; it does not
  become pytest.
- **A secret scanner replacement.** `diff-audit` and `scan-text` are coarse
  guardrails, not gitleaks/trufflehog.
- **Vendor-specific optimization.** Every feature must work in at least two
  hosts before it lands.
- **A benchmark to grade a specific model.** `bench/` is a repeatable protocol;
  it does not produce marketing numbers.
- **A machine-read model catalog.** Prices/tiers/risk flags in a data file that
  gates consume turn third-party staleness into gate wrongness, in a repo whose
  portability story is vendor-neutrality. The dated menu in `assets/routing/README.md`
  is documentation with no machine consumers, on purpose.
- **A dial/pack resolution engine.** With the reasoning floor, security pinning,
  and family heterogeneity enforced, a dial moves ~1.5 real knobs — the three
  pre-validated variants deliver the same choice at zero code.
- **Escalation-chain config or a `next-model` helper.** CQL is routing data, not
  a runtime: it validates recorded escalations against failing-check evidence;
  it never triggers them. Rung ordering is a calibration claim that needs R5's
  evidence first.
- **A cost report engine in the gate path.** The stats surface was archived in
  v3.0 for a reason, and for the core loop `jq` over completion records remains
  the report format. The opt-in control-plane add-on *does* now ship
  `control-report` as its sanctioned local audit/report surface (per-task audit
  bundles and `--arm-costs` for the bench cost bridge) — superseding the v3.0
  "no report subcommand" stance for the add-on only. The deliberate line is
  unchanged: it is an index over evidence with no gate consumers and no shipped
  prices — dashboards and reports may visualize, only records and gates decide.
