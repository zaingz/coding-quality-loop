# Roadmap

> Working notes on what is next, ordered by decreasing certainty. Nothing here is a
> commitment; the loop's non-negotiable is that we ship the smallest correct change,
> and that includes the roadmap itself.

Last updated: 2026-07-03.

## Now — landed in v2.4

- ✅ **Three-phase canonical model.** Lifecycle recast as **PLAN → EXECUTE → REVIEW**, each closed by its own verification gate. The nine sub-steps (`INTAKE`, `EXPLORE`, `MINIMALITY_GATE`, `PLAN`, `IMPLEMENT_SLICE`, `VERIFY`, `REVIEW`, `PACKAGE`, `RETROSPECT`) survive as valid machine names mapped onto the phases.
- ✅ **Context as a declared budget.** New `context_budget` schema field and `context-check` subcommand enforce per-phase `{inputs, excluded, output_summary}` envelopes on medium/mission work.
- ✅ **Per-phase verification gate.** New `phase_verifications` schema field and `verify-phases` subcommand require a `passed` entry for the current phase and every prior phase; reject `review` verified by `same_agent` on medium/mission.
- ✅ **Execution trace substrate.** New `execution-log.jsonl` format plus `trace-audit` subcommand that flags `(tool, args_hash)` repeated ≥3× as a pathological loop and aggregates per-phase steps/duration/cost.
- ✅ **Eval-runner now executes gates.** Cases carrying `gate` + `record_fixture` + `gate_fixture_expectation` fields spawn the gate against the fixture and assert the exit code.
- ✅ 129 offline eval cases across 9 suites (14 static + 31 behavioral + 27 memory + 15 reality + 11 routing + 10 trigger + 9 hook + 7 honcho + 5 orchestrator), re-run on every push.

## Landed earlier — v2.3

- ✅ Config-based model routing (`setup-models`, per-role, per-host, drift detection).
- ✅ Multi-agent role separation with per-role prompt cards.
- ✅ Honcho runnable memory adapter with zero-config local mode + cloud safety rail.
- ✅ Reality layer (`verify-gates --against-diff`) with 15 diff-grounded gates.

## Next — v2.5 (target: Q3 2026)

- **Skills Hub publish.** Validate frontmatter and publish to [agentskills.io](https://agentskills.io) so `gh skill install` works without a manual copy. Blocked only on the publish checklist in [README.md § Release & pinning](README.md#release--pinning).
- **First live cross-agent benchmark.** Run the `bench/` harness with real Claude Code, Codex, and Droid arms — not the fixture smoke result — and commit results with host, model, seed, cost, and null-result artifacts.
- **VS Code / Zed extension.** Thin extension that surfaces the current record, the next gate to satisfy, and a one-click `verify-gates` runner in the IDE status bar.
- **Reviewer diff view.** A read-only web viewer for the state record + diff + evidence bundle, so a human reviewer can approve or block without cloning the repo.
- **Mutation testing (`mutate-lite`).** Explicit non-goal of v2.4 that we still want: check that acceptance-criteria tests would catch the intended root-cause mutation, not just the code path the implementer touched.
- **Reviewer-heterogeneity `check-config` rule.** Reject configs where the same model or identity is routed to both `implementer` and `validator` on medium/mission tasks.

## Later — v2.6 and beyond (exploring, no ETA)

- **Cross-repo memory.** Point multiple repos at the same Honcho workspace and let a
  team-wide lesson (for example, "our secrets live in Vault, never `.env`") propagate.
- **Deterministic mission handoff.** Formal orchestrator adapter that persists mission
  state across days without a running session (currently the `.quality-loop/runs/` journal
  is best-effort).
- **Sandboxed `run-evidence`.** Optional execution inside a rootless container so
  `run-evidence` on an untrusted allowlist is safer. Would remain opt-in and out of the
  default trust model.
- **First-class MCP server.** Wrap the helper CLI as an MCP server so hosts can call
  gates as tools instead of subprocessing Python. Only if it does not require a runtime
  dependency for consumers who do not use MCP.
- **Live benchmark leaderboard.** Public dashboard of `bench/` results across host +
  model + seed combinations, updated on tagged releases only (not on every push, to
  avoid noise).

## Not on the roadmap, on purpose

Every trending project has to keep saying "no" to keep its shape. The following are
explicit non-goals:

- **A hosted service.** The loop stays local files, git, and stdlib Python. If it needs
  a server to work, we did it wrong.
- **A test runner.** `run-evidence` re-executes recorded commands; it does not become
  pytest. Pair the loop with your existing tools.
- **A secret scanner replacement.** `diff-audit` and `scan-text` are coarse guardrails,
  not gitleaks/trufflehog. High-risk work still runs the real scanner.
- **Vendor-specific optimization.** Every feature must work in at least two hosts before
  it lands. The value of the skill is that it moves between hosts.
- **A benchmark to grade a specific model.** `bench/` is a repeatable protocol; it does
  not produce marketing numbers.

## How to influence the roadmap

- **File an issue** with a real task the loop failed on. That is the strongest signal.
- **Ship a PR** for anything in "Next" you want to move to "Now". The
  [CONTRIBUTING guide](CONTRIBUTING.md) has the checklist.
- **Argue with us in public** if we got a priority wrong. The whole point of open source
  is that the roadmap is negotiable.

## Release cadence

No fixed cadence. A release ships when there is a coherent set of changes that pass all
eval suites and the [Skills Hub publish checklist](README.md#release--pinning) — usually
every 3–6 weeks.

See [CHANGELOG.md](CHANGELOG.md) for history.
