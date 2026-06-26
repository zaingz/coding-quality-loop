# Changelog

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
