# Coding Quality Loop (Codex AGENTS.md)

Follow the Coding Quality Loop: smallest correct change, with evidence to trust, review, revert, or merge.

**The main session is the orchestrator.** Decide task class, map, contract, right-size rung, and plan before touching code. Delegated subagents get a one-screen brief, never full context.

Lifecycle: `PLAN -> EXECUTE -> REVIEW`, each closed by its gate. Sub-steps: `INTAKE`, `EXPLORE`, `MINIMALITY_GATE`, `PLAN` | `IMPLEMENT_SLICE`, `VERIFY` | `REVIEW`, `PACKAGE`, `RETROSPECT`.

1. **PLAN** — contract: goal, acceptance criteria, constraints, risk tier (`low|medium|high`), verification plan. Map only relevant files, callers, tests. Right-size rung: no change > delete > reuse > stdlib > native > installed dependency > one-liner > minimal new code. Never trade away security, validation, authorization, accessibility, or data-loss protection.
2. **EXECUTE** — one small slice in existing conventions. Smallest sufficient checks first; record exact commands and results. Bug fix = RED then GREEN; never weaken tests.
3. **REVIEW** — medium+: independent fresh-context review against the contract (route to a different model family — e.g. Claude via Claude Code — when available). Package: files, right-size decision, evidence, risks, rollback, follow-ups.

Escalate before: destructive migrations, secret exposure, payments/billing, production infra, ambiguous user-facing behavior, or after two failed repair loops.

Per-role models: fill `model_routing` in `quality-loop.config.json`, then `python3 scripts/quality_loop.py setup-models --host codex` (prints the TOML to add to `~/.codex/config.toml`; nothing is written). Optional hooks: `python3 scripts/install.py --host codex`.

Usage: `codex --ask-for-approval never "Follow the Coding Quality Loop in AGENTS.md to fix the failing test and summarize verification evidence."`
