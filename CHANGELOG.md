# Changelog

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
