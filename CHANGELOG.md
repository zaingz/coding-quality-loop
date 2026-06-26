# Changelog

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
