# Changelog

## 3.0.0

Outcome-grounded, model-adaptive, 40% smaller. The biggest refactor since v1.0:
the harness now optimizes for code quality (not artifact production), adapts
ceremony to model strength, and uses a single `verify` command as the primary
gate. Built on evidence from three live cross-agent evals and external research
(Anthropic Mar 2026, Cognition Apr 2026).

### Cut and archived (surface −40%)

- **Archived** to `archive/`: Honcho memory adapter (`quality_loop_honcho.py`),
  driven-mode orchestrator (`quality_loop_run.py`, `quality_loop_hosts.py`),
  v2.4 ceremony subcommands (`context-check`, `verify-phases`, `trace-audit`),
  telemetry/stats, Honcho and Graphify eval suites, memory reference docs for
  those backends, and v2.4 eval cases (12-14).
- **Scripts**: 4,600 → 3,300 lines. **Eval suites**: 9 → 7 (in CI). **Eval
  cases**: 129 → 116. **CLI subcommands**: 20 → 16. **SKILL.md**: 477 → 172 lines.
- **Config/schema**: removed `memory.honcho`, `memory.graphify`, `hosts`,
  `execution` blocks; removed `context_budget` and `phase_verifications` from
  the record schema (kept `phase` for backward compat).
- **Memory**: files backend is the only backend. `memory-recall` and
  `memory-commit` no longer accept `--config` (Honcho selection).

### Rewritten SKILL.md (model-adaptive calibration)

- **New Calibration section**: strong models skip ceremony on tiny/small; weaker
  models get full scaffolding; review is paid only when the task exceeds what the
  model does reliably solo. Cites own eval data (GLM +8.0, Claude +4.5, Codex +1.0
  on Sudoku; Codex −9.0 on ts-search).
- **Complexity Brake → Right-Size Gate**: "minimal diff is not minimal
  architecture" promoted to the rule itself. Fixes the Codex −9.0 failure class
  where the gate pushed GPT-5 into a 60x-slower monolith.
- **Enforcement matrix** moved to `references/enforcement-matrix.md`; 5-line
  summary in SKILL.md.

### Outcome-grounded gate path

- **New `verify` umbrella command**: runs record-shape gates, diff-grounded
  reality checks, evidence re-execution, and AC-to-command coverage in one pass.
  One command to remember instead of four.
- **AC-to-command coverage check**: each acceptance criterion with a
  `proving_command` must have that command in `commands_run` with `result=pass`.
- **Reviewer card v2**: reviewer must **execute** tests/benchmarks when
  available (tool-using evaluator), not just read the diff. Verdict records
  `ran_checks: true|false`. Skeptical-evaluator guidance: penalize stubs,
  verify end-to-end.
- **Communication-bridge rule**: implementer filters reviewer findings against
  the contract; in-scope findings become fix tasks, out-of-scope findings become
  follow-ups. Prevents review loops.

### Capability routing

- **Reviewer heterogeneity**: `check-config` now hard-fails when implementer and
  fresh_reviewer resolve to the same model on medium+ tasks. Checks both profile
  models and model-class resolution via `model_routing.host_models`.
- **Capability annotations**: model classes annotated (cheap_fast = map/package/
  summarize; strong_reasoning = plan/review/debug; code_specialized = implement/
  test) in the config description.
- **Smart Friend pattern**: optional role where the implementer consults a
  stronger model on defined triggers (2 failed repairs, merge conflicts,
  architecture uncertainty). Documented in `references/agentic-orchestration.md`
  with per-host wiring.

### Ablation eval program

- **`bench/ablation-protocol.md`**: 3 tasks × 2-3 model families × 3 seeds × 4
  arms (baseline, v3-full, v3-no-review, v3-no-contract). Headline metric
  excludes D7 (artifact production) — code-quality lift only.
- **New web-app task** (`bench/tasks/13-webapp-task-manager.json`): browser-based
  task manager with localStorage persistence and browser-automation verification.
- **Pruning rule**: a component whose ablation shows no code-quality lift across
  ≥2 families is a v3.1 cut candidate.
- **Bench runner** updated with `--ablation` flag and ablation arms.

### Docs and packaging

- **ROADMAP.md** updated for v3.0.
- **npm package** bumped to 3.0.0.
- **CI workflow** updated to remove archived eval suites and keep the v3 routing,
  trigger, hook, and ablation smoke checks.
- All 116 eval cases pass (11 static + 32 behavioral + 26 memory + 16 reality +
  12 routing + 10 trigger + 9 hook).

## 2.4.0

Three-phase lifecycle: PLAN → EXECUTE → REVIEW.

- **Canonical model recast as three phases** (`SKILL.md`) — the operating model is now **PLAN → EXECUTE → REVIEW**, each phase closed by its own verification gate before the next may start. Guiding principle: *"An LM runs a plan-execute-review loop. Context is a budget. Verification terminates each phase."* The previous nine-step lifecycle (`INTAKE -> CONTEXT MAP -> SPEC/VALIDATION CONTRACT -> COMPLEXITY BRAKE -> PLAN -> IMPLEMENT IN SMALL SLICES -> VERIFY -> INDEPENDENT REVIEW -> SHIP/HANDOFF -> RETROSPECTIVE`) is preserved in full as sub-steps, mapped onto the three phases in a table so every older machine name (`INTAKE`, `EXPLORE`, `MINIMALITY_GATE`, `PLAN`, `IMPLEMENT_SLICE`, `VERIFY`, `REVIEW`, `PACKAGE`, `RETROSPECT`) stays valid and unlabeled steps do not exist. Existing records, configs, and automation keep working unchanged.
- **New `context-check` subcommand** (`scripts/quality_loop.py`) — enforces that medium/mission tasks declare a per-phase `context_budget` (`inputs`, `excluded`, `output_summary`) in the state record; flags missing budgets, missing `output_summary`, and overlapping `inputs`/`excluded`.
- **New `verify-phases` subcommand** (`scripts/quality_loop.py`) — checks the state record's `phase_verifications` array so a medium/mission task cannot advance phases without a `verified` block, and fails when the `review` phase is verified by the same agent that ran `plan` or `execute` (`verifier: same_agent` is a hard fail for review on medium/mission).
- **New `trace-audit` subcommand** (`scripts/quality_loop.py`) — reads an `execution-log.jsonl` trace, flags pathological loops (same `tool` + `args_hash` three or more times consecutively), and aggregates per-phase step count, duration, and cost.
- **New assets**: `assets/context-budget.md` (context-budget template), `assets/phase-verification.md` (per-phase verification block template), `assets/execution-log.jsonl.md` (execution-trace format doc).
- **Schema additions** (`assets/agent-record.schema.json`) — `phase` (enum `plan|execute|review|done|escalated`), `context_budget`, and `phase_verifications` are all new, optional fields. The existing `status` field is kept for backward compatibility and silently mapped to `phase`; v2.3.x records with no `phase` field continue to validate unchanged.
- **3 new eval cases** (`evals/cases/12-*.json`, `13-*.json`, `14-*.json`) pin the new gates: a medium task missing `context_budget` (fails `context-check`), a medium task missing `phase_verifications` (fails `verify-phases`), and a medium task where the `review` phase is verified by `same_agent` (fails `verify-phases`). Full suite: 14/14 eval-case runs green.
- **Docs sweep** — `README.md`, `references/lifecycle.md`, `references/agentic-orchestration.md`, and the packaged host quickstarts (`examples/claude-code/CLAUDE.md`, `examples/codex/AGENTS.md`, `examples/cursor/.cursor/rules/coding-quality-loop.mdc`) now lead with the three-phase model; the nine machine-name sub-steps remain documented as the mapping table, not removed.
- **Non-goals, explicitly deferred to v2.5.0+**: mutation testing, environment manifest, phantom-symbol resolution, and a metrics aggregator. None of these are in scope for this release.
- **Packaging** — `packages/npm/package.json` bumped to `2.4.0`; `packages/npm/scripts/prepack.mjs` continues to bundle the new asset files (it globs `assets/` recursively, so no prepack changes were required).

## 2.3.2

Findings from the `ts-search-eval-2026-07-03` eval baked into the harness.

- **New `performance_sensitive` medium signal** (`scripts/quality_loop.py`) — tasks whose brief includes a benchmark harness, or that touch a hot request path, indexing/ranking, rendering, or data-pipeline surface, now classify as **medium** even without other multi-file signals. This triggers the validation contract + independent-review gates that the ts-search Codex+CQL run should have run but did not.
- **New `under-fanned` minimality flag** (`scripts/quality_loop.py`) — the simplicity reviewer now flags multi-feature medium/mission tasks that collapse into a single source file or a single test file. Signaled by `single_source_file` / `single_test_file` + `feature_count >= 3` in the proposed solution. Modularity is a maintainability property; a 700-LOC monolith with one 13-test file for a seven-feature brief is not "minimal."
- **`assets/validation-contract.md`: new Performance / Complexity Targets section** — required for performance-sensitive tasks. Forces the implementer to commit to a worst-case complexity for the hot path, a p50/p95 latency budget, a memory budget, and the exact benchmark command *before* implementing. If the chosen approach cannot hit the target, escalate at PLAN — do not implement and discover the miss at VERIFY.
- **`SKILL.md` COMPLEXITY BRAKE: algorithmic-complexity clause** — explicit rule that "simple linear scan" is not simpler than the required data structure when the brief includes a benchmark. Rewrites the perf blind spot from advisory ambient text into a named brake step. Adds an anti-pattern that separates *minimal code* from *minimal performance* and *minimal modularity*.
- **`references/reviewer-checklists.md`: perf-regression and under-fanned checks** — the fresh-context reviewer now must confirm that the diff’s chosen algorithm honors the contract’s worst-case complexity commitment; a diff that meets correctness but misses the perf target is `blocking`, not `minor`. The simplicity reviewer explicitly flags monolithic multi-feature diffs.
- **New eval cases** (`evals/cases/10-*.json`, `11-*.json`) — pin (a) `performance_sensitive` alone lifting a task to medium with the full medium gate set, and (b) `single_source_file` + `single_test_file` + `feature_count >= 3` producing the `under-fanned` minimality flag. Full suite: 11/11 case runs + 31 + 9 + 5 + 15 + 11 + 10 + 27 + 7 = 115 runner checks green.
- **Reference eval published**: `examples/ts-search-eval-2026-07-03/` contains the full 2×2 blind eval, both judge score files, aggregate JSON, and a report that motivates every change above. Directional finding: CQL lifted Claude Code (Sonnet 5) by **+15.0** blind mean but hurt Codex (GPT-5) by **−9.0** on this task — the harness now closes the specific gap that caused the Codex regression.

## 2.3.1

One-command `npx` installer (first npm-installable release).

- **`npx coding-quality-loop init`** — new zero-prerequisite installer under `packages/npm/`. Auto-detects host (Claude Code, Codex, Cursor, Droid, Pi) by scanning the target directory, invokes bundled `scripts/install.py` under the hood, and prints tailored next-steps. Interactive by default; `--yes` for CI, `--dry-run` for preview, `--host` to skip detection. Also ships `npx cql init` alias, `add <host>` for incremental wiring, and `check` for post-install verification.
- **Real skill install for Claude Code + Pi** — `install.py --host claude-code` copies `SKILL.md`, `references/`, `assets/`, and `scripts/` into `.claude/skills/coding-quality-loop/`. `install.py --host pi` does the equivalent under `.pi/skills/coding-quality-loop/`. Previously only settings/hooks landed and the skill was not discoverable by the host.
- **Zero-dependency Node package** — `node:*` built-ins only, ~1 s cold start, ~114 kB tarball. Node 18+.
- **`scripts/install.py` extensions** — new `--host cursor` and `--host pi` (previously required manual `cp -r`), new `--json` flag for machine-parseable output that the Node CLI consumes, `install_runtime()` now also copies `assets/quality-loop.config.example.json` so `setup-models` works immediately after install, and `install_git()` now resolves Python via `sys.executable` → `python3` → `python` (fixes Windows hosts that only ship `python.exe`).
- **CI** — `.github/workflows/npm-smoke.yml` runs `cql init --dry-run --yes` on Ubuntu + macOS + Windows across Node 18/20/22 for every host; `.github/workflows/publish-npm.yml` publishes to npm on release tag with tag/version check (also enforced for manual dispatch non-dry-runs), `NPM_TOKEN` preflight, and a real `npm pack` + tarball-install smoke step. `packages/npm/test/` has `node --test` coverage for the argv parser, host detection, and CLI end-to-end (22 tests).

## 2.3.0

Config-based model routing (`setup-models`).

- **`model_routing` config section**: `assets/quality-loop.config.example.json` ships a
  pre-filled `model_routing` block with per-host mappings (Claude Code, Droid, Codex, Pi).
  Each model class (`cheap_fast`, `strong_reasoning`, `code_specialized`) maps to a real
  model id and optional thinking level. Copy the example to `quality-loop.config.json` at
  your repo root, set `host`, adjust your block, and run `setup-models`. Schema updated in
  `assets/quality-loop.config.schema.json`; `check-config` validates the section when present
  (backward compatible — configs without it still pass).
- **`setup-models` CLI command**: `python3 scripts/quality_loop.py setup-models --host <host>`
  applies the routing through each host's native mechanism. Claude Code and Droid get their
  agent/droid `.md` frontmatter rewritten (`model:` + `effort:`/`reasoningEffort:`); Codex
  prints the `config.toml` additions (`model`, `model_reasoning_effort`, per-role
  `config_file` layers); Pi prints `/model` commands and thinking levels per role. Supports
  `--dry-run`, `--json`, `--target`, and `--config`. Unsupported thinking levels for a host
  are warned and omitted; the command exits non-zero so CI catches divergence.
- **`brief` shows routing**: the session-start briefing now includes a `## Model routing`
  section (host, per-class models/thinking, drift detection for file-based hosts). New
  `--config` arg; auto-detects `quality-loop.config.json` in the working directory. The
  `model_routing` key is added to `--json` output.
- **Droid installer**: `install.py --host droid` copies the example role droids into
  `.factory/droids/` (consistent with the existing Claude/Codex/git/github installers).
  The wiring report now points to `setup-models` as the next step.
- **Agent files switched to `model: inherit`**: the committed `.claude/agents/*.md` and
  `examples/droid/.factory/droids/*.md` files now ship with `model: inherit` (host-neutral
  at rest) instead of Claude-specific aliases. `setup-models` writes the configured
  identifiers. This also fixes the Droid examples, which used `haiku`/`sonnet` aliases that
  Droid's validator rejects as unknown model ids.
- **New module `scripts/quality_loop_routing.py`**: stdlib-only routing resolver, frontmatter
  rewriter (line-based, no YAML dependency), Codex/Pi renderers, validation, and the
  `setup-models` command. Follows the `quality_loop_memory.py` separate-module pattern.
- **Evals**: new `evals/run_routing_evals.py` — 11 offline cases pinning claude-code/droid
  rewrites, idempotency, thinking write/remove, codex/pi print output, unsupported-thinking
  exit code, check-config validation, brief routing+drift, and dry-run. Full suite:
  9+31+27+15+9+5+10+7+11 = 124 cases.
- **Docs**: `references/agentic-orchestration.md` gains a "Config-Driven Model Setup"
  subsection with the per-host mechanism table and workflow. `examples/droid/README.md`,
  `examples/pi/README.md`, `examples/codex/AGENTS.md`, `SKILL.md`, and `README.md` updated.

## 2.2.0

Harness-agnostic multi-agent routing + longitudinal coding partner + memory hardening.

- **Per-role prompt cards**: add `intake.md`, `context-map.md`, `minimality.md`,
  `implementer.md` to `assets/prompts/` (joining planner/reviewer/security-reviewer/
  package). Any harness or human can now run any role by pasting one card.
- **Claude Code subagent set**: add read-only `quality-loop-context-mapper.md` (model:
  haiku) and `quality-loop-planner.md` (model: sonnet) to `.claude/agents/`, alongside
  the 2 existing reviewers (now model: sonnet).
- **Droid host example**: `examples/droid/` with `.factory/droids/` role droids
  (mapper, planner, reviewer, security-reviewer) and a README explaining the
  single-threaded-writes + clean-context-intelligence pattern.
- **Pi role wiring**: extended `examples/pi/README.md` with provider/model-per-role
  notes and Pi as the documented escalation harness for mission-class work.
- **Harness-agnostic wiring section** in `references/agentic-orchestration.md`: a
  role -> native mechanism table (Claude subagents, Droid droids, Codex, Cursor, Pi),
  with Cognition 2026 and Anthropic 2025 citations confirming the core bet.
- **`brief` command**: `python3 scripts/quality_loop.py brief` prints a session-start
  project briefing — last run summary, open risks, top recalled lessons (project +
  global, split-capped), progress-file tail, and a suggested next step. Wired into
  the Claude Code `SessionStart` hook; one-line "run brief at session start" added
  to `assets/AGENTS.template.md`.
- **Global cross-project memory**: `~/.quality-loop/global/` store for user-level
  conventions/preferences. `memory-commit --global`; recall merges project + global
  under a split-capped budget. `memory-status` reports both stores. `memory-commit`
  now accepts `--lesson` without a record path (for manual global lessons).
- **Session continuity**: `assets/progress.md` template; SKILL.md gains a "Session
  continuity" rule (read brief+progress at session start, update at PACKAGE/RETROSPECT,
  resume from the surfaced next step). Follows Anthropic's long-running-agent harness
  pattern (progress file + incremental sessions + git as memory).
- **Driven mode reframed**: README/SKILL.md now state that `quality_loop_run.py` is an
  optional *reference* orchestrator using a single host for all steps — per-role model
  routing is the host's job via the config profiles and the harness-agnostic role pack.
  The config description clarifies it is routing *data*, not a runtime.
- **Skills Hub publish checklist** added to the Release & pinning section.
- **References updated** with Cognition (Apr 2026, multi-agents-working) and Anthropic
  (Nov 2025, effective-harnesses-for-long-running-agents) citations in philosophy and
  orchestration trend sections.
- **Fix (security):** `redact()` missed OpenAI hyphenated key families
  (`sk-live-*`, `sk-proj-*`, `sk-test-*`, `sk-svcacct-*`) because the fallback
  `sk-[A-Za-z0-9]{20,}` pattern excludes hyphens. Independent review proved a
  raw `sk-live-<hex>` could be persisted verbatim into `.quality-loop/memory/lessons.jsonl`
  and its hex payload leaked into the searchable `keywords` array. New regex
  covers all four variants; keyword tokens are re-scrubbed at Honcho egress.
- **Add (defense in depth):** entropy-based secondary redactor catches
  obfuscated / novel-shape secrets that no regex covers. Uses Shannon entropy
  >= 3.5 bits on tokens >= 28 chars; skips hex-only git SHAs, UUIDs, dotted
  paths, and file paths so prose and identifiers stay intact.
- **Add:** `scripts/quality_loop_honcho.py` — runnable [Honcho](https://honcho.dev)
  memory adapter. Same recall/commit contract as the files backend; dual-writes
  to files then mirrors to Honcho; transparent fallback to files when the SDK
  is missing, the API key is unset, or the network call fails. Config lives
  under `memory.honcho` with `HONCHO_API_KEY` from env. Runtime dep
  `honcho-ai` is imported lazily so files-backend users never install it.
- **Add (zero-config local):** the Honcho adapter now defaults `base_url` to
  `http://localhost:8000` and connects **without an API key** to any local
  endpoint (`localhost`, `127.0.0.1`, `0.0.0.0`, `host.docker.internal`,
  `.local`, `::1`). Run upstream Honcho with `AUTH_USE_AUTH=false docker
  compose up` and you get reasoning-based memory with zero secrets on disk.
  Cloud URLs (`https://api.honcho.dev`, any non-local host) still require
  `HONCHO_API_KEY` — the adapter refuses to connect keyless as a safety rail.
- **Docs:** `references/memory-honcho.md` rewritten to describe the runnable
  adapter and document the zero-config local mode.
- **Evals**: behavioral 27 -> **31** (4 brief cases: empty repo, record+progress,
  JSON output, run journal); memory 20 -> **27** (global commit+recall, global
  status, budget split, global redaction, OpenAI hyphenated key redaction,
  sk-proj/sk-test variants, entropy redaction); hook 8 -> **9** (SessionStart
  brief); honcho 0 -> **7** (fallback, dual-write, boundary redaction,
  files-only defaults, zero-config local, cloud keyless-refusal). Full suite:
  9+31+27+15+9+5+10+7 = 113 cases.

## 2.1.0

Proof layer.

- Add a tracked live Sudoku eval summary for the 2026-07-01 Codex / Claude Code /
  Droid run, where CQL averaged 89.5 vs 85.0 for baselines under two blind LLM
  judges. The docs state the one-seed and no-browser-automation caveats.
- Add `bench/` with 12 vendored benchmark tasks, objective metrics, a blind
  judge protocol, and a deterministic fixture-mode runner.
- Commit `bench/results/fixture-smoke-2026-07-01.json` as a harness smoke result.
  It validates plumbing only and is explicitly not a live agent benchmark.
- Add `evals/run_trigger_evals.py` for activation/description checks with either
  a heuristic offline judge or a caller-supplied `--judge-command`.
- Wire a benchmark fixture smoke into CI without committing generated CI output.

## 2.0.0

Driven mode core.

- Add `scripts/quality_loop_run.py`: a risk-scaled state machine with pure step
  ordering gates, orchestrator-native VERIFY, fresh-by-construction REVIEW, and
  PACKAGE reasserting the v1 `verify-gates` suite.
- Add `scripts/quality_loop_hosts.py`: `HostAdapter` protocol plus `fake`,
  `manual`, `claude`, and `codex` adapters. Fake host makes the orchestrator eval
  suite fully offline.
- Add prompt templates in `assets/prompts/`.
- Add `.quality-loop/runs/<id>/journal.jsonl` redacted local journals (gitignored).
- Add memory dogfooding: `memory-recall --no-bump` is injected into planner
  prompts; successful PACKAGE attempts a local `memory-commit`.
- Add `evals/run_orchestrator_evals.py` covering step order, transcript isolation,
  VERIFY blocking REVIEW, tiny topology, and v1 gate compatibility.
- Extend config schema/example with optional backward-compatible `hosts` and
  `execution` blocks.

## 1.6.0

Session ring + backstop + install DX.

- Add Claude Code project hook wiring in `hosts/claude-code/settings.json` plus
  stdlib shims for `PreToolUse`, `Stop`, and `SessionStart`.
- Add read-only Claude reviewer subagents:
  `.claude/agents/quality-loop-reviewer.md` and
  `.claude/agents/quality-loop-security-reviewer.md`.
- Add Codex project hook wiring in `hosts/codex/hooks.json` using the current
  Codex hook schema (`hooks.json`, command handlers, trust review via `/hooks`).
- Add git backstop: `hosts/git/install-git-hooks.py` and
  `hosts/git/.pre-commit-config.yaml` run staged `diff-audit`.
- Add `action.yml` composite action and `hosts/github/quality-loop-example.yml`.
- Add `scripts/install.py` idempotent host installer with JSON hook merging,
  backups, and an advisory/enforced wiring report.
- Add `evals/run_hook_evals.py` fixture tests for every host shim and installer
  idempotence; wire it into CI.

## 1.5.0

The "reality layer" — closes the three free lies in v1.4.0 by grounding the record in git.
A new sibling module `scripts/quality_loop_reality.py` (mirroring `quality_loop_memory.py`,
reusing `run_git`/`redact`/`SECRET_PATTERNS`/`has_evidence`/`load_json` from `quality_loop`)
adds record↔reality verification. Stdlib-only, portable, no network, no new dependencies.

- **`verify-gates --against-diff [--base REF]`** reads the real git diff and catches:
  phantom completion (package/done with an empty diff), scope integrity (changed files not
  mapped in repo_map/plan/completion_record, glob-tolerant), a **diff-derived risk floor**
  (changed paths matching auth/, payments/, migrations/, .env, terraform/, lockfiles force
  high-tier gates — grounding `detect_risk_floor` in git, not prose), bugfix-test co-presence
  (a bug/fix goal with no test in the diff and no waiver), review freshness
  (`independent_review.diff_sha256` recomputed; mismatch/missing at medium+ fails), and
  promotes diff-audit secret/test-weakening warnings to blocking at medium+.
- **`attest-review`** embeds a recomputed `git diff | sha256` into the review object — the
  reviewer's last act — so review freshness is checkable, not self-attested.
- **`run-evidence`** re-executes each recorded `commands_run[result=pass]` (allowlist
  `.quality-loop/allowed-commands`, per-command timeout, sidecar `.quality-loop/rerun-<task>.json`,
  never mutates the record). **`--red-green`** replays a `red_green: true` command in a
  `git worktree` at base (expect fail) and HEAD (expect pass) — catches a faked RED→GREEN;
  worktree unavailable → explicit "not proven", never a silent pass.
- **`diff-audit --staged`** + **`scan-text --stdin`**: pre-commit (cached) diff mode +
  secret-scan-as-a-service for host hook shims.
- **Telemetry + `stats`**: verify-gates/diff-audit/run-evidence append
  `{ts, cmd, task_id, risk, findings, pass, overrides}` to `.quality-loop/telemetry.jsonl`
  (local-only, no network; opt out with `QUALITY_LOOP_NO_TELEMETRY=1`). `stats` renders
  SKILL.md's metrics table, printing "not instrumented" for rows it can't compute.
- **Contradiction fixes:** canonicalized complexity-brake-before-PLAN across
  SKILL.md/`references/lifecycle.md`/config step order (MINIMALITY_GATE now precedes PLAN);
  fixed `assets/completion-record.md` trigger (small low-risk ships without it); bumped config
  `version` to 1.5.0; added concurrency/race/data-loss/PII to runtime `BOUNDARY_KEYWORDS`.
- **Enforcement Matrix** section in SKILL.md: every Hard Rule × its deterministic owner or an
  explicit "advisory" label — candor becomes an auditable trust artifact.
- **README claims reframe:** Sudoku presented as an honest pilot (n=1, rubric caveats, headline
  numbers removed until bench v1); Honcho/Graphify downgraded to "documented integration pattern".
- **Schema:** record gains **optional** fields only (`diff_sha256`, `files_changed`, `red_green`)
  — no adopter break; migration is additive.
- **Evals:** new `evals/run_reality_evals.py` (15 temp-git-repo fixtures where record and diff
  disagree); wired into CI. Existing 9/26/20 suites stay green.

## 1.4.0

- Add an optional, advisory **persistent per-project memory** layer: a stdlib-only files
  lessons-store (default, checked-in to `.quality-loop/memory/`) behind a backend-agnostic
  `memory-recall` / `memory-commit` / `memory-prune` / `memory-status` CLI.
- Document two optional loop-integrated backends: `honcho` (reasoning-based lessons recall)
  and `graphify` (code-graph relevance), selectable via the config `memory` block, degrading
  gracefully to the files backend.
- Memory is retrieval-not-stuffing: only a <=40-line `MEMORY.md` index auto-loads; recall is
  budget-capped and relevance-scoped. Writes are advisory (no new hard gate).
- New offline eval harness `evals/run_memory_evals.py` pins recall determinism/budget, commit
  distillation, prune, config validation, and docs presence; wired into CI.

## 1.3.2

Follow-ups from an independent max-effort review — small, in-philosophy fixes (no new subsystems).

- **Resolved a self-contradiction in the shipping gate.** `evaluate_input` (static evals) required
  a completion record for the `small` class while the runtime `verify_gates` did not — two
  definitions of "non-trivial" in one file. Aligned both: the completion-record gate fires for
  medium/mission, medium/high risk, or security-sensitive work; a small low-risk task ships with
  handoff evidence (matching its task-class description). Updated `SKILL.md`/`README.md` to match.
- **Fixed a secret-scan false negative.** The unquoted-assignment placeholder guard treated any
  value starting with `your_` as a stub, so `api_key = your_realProductionKey` was suppressed. The
  guard now anchors on exact stub words only. Added `passwd`/`pwd`/`credential`/`private_key`
  keywords to both the quoted and unquoted patterns (quoted secrets with these keywords were also
  missed).
- **De-noised the detected-risk floor.** Dropped the false-positive-prone bare words
  (`admin`, `grant`, `session`, `token`) that forced full high-risk ceremony onto benign copy/docs
  ("improve the admin dashboard copy") — the exact process theater the skill disclaims. Precise
  multi-word/domain terms are kept (`admin endpoint`, `oauth`, `rbac`, `payout`, …).
- **Right-sized the wording.** "deep validation / never a placeholder" and "shape-only placeholders
  are rejected" now accurately say required fields must be present and non-empty (shape, not
  substance); the README states plainly that `verify-gates` lints the record and `diff-audit` + CI
  are the actual block.
- **Evals:** behavioral suite 23 → **26** (small+low ships without a completion record and the two
  halves agree; secret guard flags real keys and skips only stubs; floor ignores benign common
  words). Static unchanged at 9/9.

## 1.3.0

Enforcement hardening — closes reproduced gate bypasses so "deterministic gates beat advisory
text" is actually true. All changes stay stdlib-only with offline, model-free CI.

- **Closed the self-downgrade hole (P0).** `verify-gates` derived every decision from
  agent-declared `risk_tier`/`task_class`/`security_sensitive`, so a record with goal "Disable
  auth check on admin endpoint" declared `low`/`tiny` with no evidence passed clean. New
  `detect_risk_floor` word-boundary-scans the record's own goal/criteria/plan for risk
  boundaries (auth/authz, secrets, crypto, payments, migrations, destructive, infra) and forces
  high-risk + security-review gates regardless of the declared tier. It is a curated text-scan
  heuristic — it catches honest mis-tiering, not an agent that deliberately phrases around it.
- **Fixed the flagship walkthrough (P0).** `examples/walkthrough/agent-record.json` failed the
  `verify-gates` command its own README tells you to run (missing `implementer`,
  `validation_contract`, structured `independent_review`, `completion_record`). It now passes
  both `check-record` and `verify-gates`, and CI runs both on **every** `examples/*` record so
  the showcase can never silently regress.
- **`diff-audit` sees ground truth (P0).** Untracked files (the common new-module case) were
  invisible to `git diff`, so a brand-new file with a secret returned a clean pass. They are now
  enumerated and scanned. Secret patterns broadened to the unquoted `KEY=value` shape
  (placeholder-guarded) and mainstream prefixes (`sk_live_`, `gh*_`, `github_pat_`, `ASIA`,
  `xoxb-`, `AIza`). Added a test-weakening warning (added `skip`/`xfail`/`.only` in test files).
- **Gated the UNDERSTAND verb.** Non-trivial work now requires a substantive `repo_map`
  (entry points/likely files plus callers or tests) by implementation — previously the only
  Hard Rule with no record-level enforcement.
- **Hardened artifact and command evidence.** A string artifact path must now satisfy the same
  content contract as an inline object (any existing file such as `LICENSE` no longer passes);
  command `class` is constrained to a known set; every `pass`-labeled command needs a verifiable
  evidence handle.
- **Test integrity** named as a first-class concept: a new Hard Rule and Anti-Pattern for
  RED→GREEN reproduction and not weakening/deleting tests to reach green.
- **Docs/adoption:** added a native Claude Code `.claude/skills/` install row (instruction-only
  path relabeled); normalized all documented invocations to `python3`; documented the
  `gh skill publish/install --pin` provenance path (publishing remains a maintainer step,
  provenance is not hand-faked); inlined the role→config-profile mapping in `SKILL.md`; added a
  worktree-isolation principle to mission topology; relabeled the eval suites honestly (static =
  intake-classification regression, behavioral = the gates; evidence is attested, not
  re-executed).
- **Evals:** behavioral harness grew from 15 to **23** cases (self-downgrade block + boundary-
  phrasing coverage + compliant-high pass, untracked secret, empty context map, wrong-content
  artifact, unknown command class, missing command evidence). Static suite unchanged at 9/9.
  Added opt-in trigger-eval data
  (`evals/triggers/cases.json`, should/should-NOT-trigger) kept out of offline CI by design.

## 1.2.3

- Added `references/philosophy.md` — a manifesto covering the mantra (bounded autonomy, smallest
  correct change, evidence over confidence, deterministic gates over vibes, repo maps over context
  stuffing, durable harness changes over repeated chat corrections), the problem framing (agents
  overbuild, self-attest, lose context, skip evidence, repeat mistakes), trends observed,
  inspirations (cited as influences, not endorsements or adoption claims), how the loop packages
  those ideas, and explicit non-goals.
- Rewrote the README `Philosophy` section as the seven-line mantra with a link to the full
  manifesto and the existing engineering-OS rationale.
- Docs-only change: no behavior change to `scripts/quality_loop.py`, the gates, or any asset; all
  prior validation fixes intact (9/9 static eval cases and 15/15 behavioral gate cases still pass).

## 1.2.2

- Added a root `LICENSE` file (MIT) to match the `license: MIT` declared in `SKILL.md`
  frontmatter, closing a credibility gap (claim without file).
- Rewrote `README.md` for adoption: bounded-autonomy hero/positioning, a 30-second start
  (no-install / install / orchestrated), an install-&-use matrix for Claude Code, Codex,
  Cursor, Pi, `gh skill`/generic `.agents/skills`, and standalone agents, a before/after
  example, a packaging/structure map with progressive disclosure, a runnable proof/evidence
  section, and release/pinning + trust guidance. Marketplace/`gh skill install` framed as
  conditional on a published release (no overclaiming).
- Added a lightweight, dependency-free CI workflow (`.github/workflows/evals.yml`) running
  `py_compile`, `check-config`, `eval-cases`, and `run_evals.py` on push and PR, so the
  "evals pass" claim is continuously verifiable.
- No behavior change to `scripts/quality_loop.py` or the gates; all prior validation fixes
  intact (9/9 static eval cases and 15/15 behavioral gate cases still pass).

## 1.2.1

- **Deep artifact validation** in `verify-gates`: the validation contract and completion record
  are now accepted only as a string path to a file that exists, or a complete inline object
  (goal + acceptance criteria + evidence). Shape-only placeholders (e.g. `{"placeholder":"yes"}`),
  empty strings, bare booleans/numbers, and nonexistent paths are rejected.
- **Repeated-failure → durable harness change** is now machine-checkable: new record fields
  `repeated_failure`, `repair_attempts`, and `harness_update`. When a failure recurs
  (`repeated_failure: true` or `repair_attempts >= 2`), `verify-gates` requires `harness_update`
  evidence so a clean final record cannot hide a repeated mistake corrected only in chat.
- Added the three new fields to `agent-record.schema.json` and `init-record` defaults;
  `check-record` validates their types and rejects boolean/number placeholders consistently.
- Added 4 record-gate eval cases (shallow/nonexistent artifacts fail, complete inline artifacts
  pass, existing-file path passes, repeated-failure requires harness update); 15/15 pass.
- README: corrected the lifecycle claim (8 routed machine steps vs. 2 artifact/rule-gate
  phases), added a "What the helper enforces (and does not)" section, and dropped
  `--ask-for-approval never` from the Codex one-liner.

## 1.2.0

- Reframed the skill as an **engineering operating system** (five parts: durable repo
  instructions, reusable skills, mission artifacts, independent verification, complexity
  discipline) rather than just better prompting.
- Exposed a canonical 10-step lifecycle (INTAKE -> CONTEXT MAP -> SPEC/VALIDATION CONTRACT ->
  COMPLEXITY BRAKE -> PLAN -> IMPLEMENT IN SMALL SLICES -> VERIFY -> INDEPENDENT REVIEW ->
  SHIP/HANDOFF -> RETROSPECTIVE) with stable machine-name aliases for backward compatibility.
- Added **task classes** (tiny / small / medium / mission) and scaling rules; default to the
  smallest class that is safe.
- Added a mental-model graph for mapping a change before editing.
- Expanded role architecture: `orchestrator`, `context_mapper`, `implementer`, `validator`,
  `simplicity_reviewer`, `security_reviewer`, `policy_guard`; added mission topology.
- Promoted the **complexity brake** (run before plan and before review) with explicit
  non-negotiables, and added **hard rules** and a **shipping gate** (completion record required
  for non-trivial tasks).
- Added quality gates by task type, harness implementation modes, and tool-surface guidance.
- New mission-artifact templates: `validation-contract.md`, `plan.md`, `completion-record.md`,
  `execution-log.md`, `decision-log.md`, `context-map.md`, plus a baseline `AGENTS.template.md`.
- New reference `engineering-operating-system.md` (trend synthesis, task classes, harness
  modes, tool surface, improvement loop); updated lifecycle, orchestration, reviewer, and
  tool-contract references (simplicity + security reviewer passes, security review and
  completion-record tool contracts).
- Extended the eval engine and added 5 cases: tiny-no-mission-artifacts, medium-requires-
  contract+review, security-hard-gate, complexity-brake-dependency, retrospective-harness-update
  (task_class, validation-contract/independent-review/completion-record, security reviewer,
  hard gate, and harness-update logic).
- Added a **Pi** example (`.pi/settings.json` + skill pointer) and one-line usage; README now
  covers Claude Code, Codex, Cursor, Pi, and standalone, with citations to Anthropic Agent
  Skills, Factory Missions, Aider repo map, OpenAI Agent Improvement Loop, Pi, and Codex docs.
- Bumped routing config to 1.2.0 (added orchestrator + security_reviewer profiles).

Safety hardening (runtime record gates):

- `verify-gates` now enforces the operating-system concepts against an actual agent
  record, not just the static intake derivation: non-trivial work requires a named
  `implementer`, a `validation_contract` with evidence, and an approving
  `independent_review` whose reviewer differs from the implementer; `package`/`done`
  require a `completion_record` with evidence; high-risk / `security_sensitive` work
  requires a distinct approving `security_review` artifact (a self-run `class=security`
  command no longer satisfies the gate).
- `validation_contract` / `completion_record` must be objects or non-empty
  paths/strings with evidence, never bare booleans/numbers (schema + `check-record`).
- `check-record` validates `commands_run` entry shapes and review verdicts;
  `verify-gates` handles malformed `commands_run` defensively (fails cleanly, no crash).
- Added `evals/run_evals.py`: 11 record-gate cases covering the behaviors above,
  complementing the static `eval-cases` intake-derivation suite in `evals/cases/`.

## 1.1.0

- Made the skill agentic-first: each lifecycle step can be routed to a role-based agent
  profile (`contract_agent`, `repo_mapper`, `planner`, `minimality_reviewer`, `implementer`,
  `verification_runner`, `fresh_reviewer`, `packager`, `policy_guard`).
- Added `references/agentic-orchestration.md` with the step-to-agent matrix, model-selection
  heuristics, and per-platform mapping.
- Added `assets/quality-loop.config.example.json` (+ schema) as machine-readable routing
  config, and a `check-config` helper command.
- Added an offline eval harness: `evals/` with 4 cases (low docs, medium multi-file,
  high-risk migration/security, overengineering trap) and a `eval-cases` helper command.
- Added portable examples with one-line usage for Claude Code, Codex, Cursor, and standalone
  agents, plus a real end-to-end walkthrough with a state record.
- Reworked README into adoption paths (instruction-only, skill package, orchestrated
  multi-agent, enforced production) and linked official Claude Code, Codex, and Cursor docs.
- Made agentic orchestration first-class in SKILL.md (kept under 500 lines).

## 1.0.0

- Initial release of the Coding Quality Loop skill.
- Added lifecycle instructions, review checklists, tool contracts, templates, and helper script.
