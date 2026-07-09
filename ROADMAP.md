# Roadmap

> Working notes on what is next, ordered by decreasing certainty. Nothing here is a
> commitment; the loop's non-negotiable is that we ship the smallest correct change,
> and that includes the roadmap itself.

Last updated: 2026-07-09.

## Now — landed in v3.0

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
  130 gate cases across 6 suites (plus a 10-case trigger smoke fixture).

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
- **Cross-CLI orchestrator recipe (critical-review R7).** One page of verified
  headless commands (`claude -p --safe-mode`, `codex exec -s workspace-write`,
  `droid exec`) for running the loop's roles across harnesses, with the caveat
  that harness diversity does not guarantee model heterogeneity — `check-config`
  stays the arbiter.

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
- **A test runner.** `run-evidence` re-executes recorded commands; it does not
  become pytest.
- **A secret scanner replacement.** `diff-audit` and `scan-text` are coarse
  guardrails, not gitleaks/trufflehog.
- **Vendor-specific optimization.** Every feature must work in at least two
  hosts before it lands.
- **A benchmark to grade a specific model.** `bench/` is a repeatable protocol;
  it does not produce marketing numbers.
