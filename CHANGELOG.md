# Changelog

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
