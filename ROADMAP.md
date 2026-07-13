# Roadmap

> Working notes on what is next, ordered by decreasing certainty. Nothing here is a
> commitment; the loop's non-negotiable is that we ship the smallest correct change,
> and that includes the roadmap itself.

Last updated: 2026-07-13.

## Now — landed in v5.0.0

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
- ✅ **Ablation eval program.** `bench/ablation-protocol.md` defines the
  protocol (3 tasks × 2-3 families × 3 seeds × 4 arms). Headline metric excludes
  artifact dimensions.
- ✅ **40% surface reduction.** Archived legacy adapters, local orchestration,
  v2.4 ceremony surfaces, and stats reporting. Scripts 4,600 → 3,300 lines.
  164 gate cases across 7 suites (plus a 10-case trigger smoke fixture).

## Landed earlier — v2.4

- ✅ Three-phase canonical model (PLAN → EXECUTE → REVIEW).
- ✅ Config-based model routing (`setup-models`, per-role, per-host).
- ✅ Reality layer (`verify-gates --against-diff`) with diff-grounded gates.
- ✅ Project memory (files backend, budget-capped recall, secret redaction).

## Next — v3.1 (target: Q4 2026)

### Hardening from the webapp live eval (2026-07-07) — landed

Findings from `examples/webapp-agent-eval-2026-07-07/` (gate-gaming, allowlist
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
  captures the proven isolation + blind-judging mechanics.

Still open from the same findings:

- **Native-path live test.** One live run per host with the installed skill and
  trusted hooks (the 2026-07-07 run used drop-in delivery for isolation).
- **Cost/duration per cell** reported alongside lift in ablation results
  (ceremony overhead was 3-6x wall time in the webapp run).

- **Live ablation results.** Run the `bench/` ablation protocol with real models
  and commit results (use `bench/live-run-recipe.md` for the mechanics). Apply
  the pruning rule: cut components with no code-quality lift across ≥2 families.
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
  attempts, and cost capture in records); the config still waits on replication.

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
- **A cost report subcommand.** The stats surface was archived in v3.0 for a
  reason; `jq` over completion records is the report format. The v4.3.0
  control plane renders token spend in a local UI, but it is an index over
  evidence with no gate consumers and no shipped prices — the deliberate line
  is: dashboards may visualize, only records and gates decide.
