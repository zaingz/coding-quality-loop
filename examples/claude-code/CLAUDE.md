# Coding Quality Loop (Claude Code)

This repo runs the Coding Quality Loop: smallest correct change, with evidence a human can trust, review, revert, or merge.

**You (main session) are the orchestrator.** Think and decide here: task class (tiny/small/medium/mission), context map, contract, right-size rung, plan, routing, verdicts. Subagents get a one-screen brief — goal, contract slice, files, commands, done-check — never full context.

Lifecycle: `PLAN -> EXECUTE -> REVIEW`, each closed by its gate. Sub-steps: `INTAKE`, `EXPLORE`, `MINIMALITY_GATE`, `PLAN` | `IMPLEMENT_SLICE`, `VERIFY` | `REVIEW`, `PACKAGE`, `RETROSPECT`.

- **PLAN** — contract (acceptance criteria, constraints, risk tier `low|medium|high`, verification plan). Map only relevant files, callers, tests. Right-size rung: no change > delete > reuse > stdlib > native > installed dependency > one-liner > minimal new code. Never drop security, validation, authorization, accessibility, or data-loss protection for minimality.
- **EXECUTE** — one small slice in existing conventions. Smallest sufficient checks first; record exact commands and results. Green tests are necessary, not sufficient. Bug fix = RED then GREEN; never weaken tests.
- **REVIEW** — medium+: fresh-context subagent in a different model family reviews the diff against the contract. The implementer never self-approves. Security review at risk boundaries. Package: files, right-size decision, evidence, risks, rollback, follow-ups.

Routing by capability class: plan/orchestrate on frontier reasoning, implement on strong code-specialized, independent review on strong reasoning in a **different family** (via Codex), map/summarize on fast/cheap. Dated model menu: `assets/routing/README.md`. Apply with `python3 scripts/quality_loop.py setup-models`.

Escalate before: destructive migrations, secrets/credentials, payments/billing, production infra, ambiguous user-facing behavior, or after two failed repair loops.

Hooks (advisory by default): `python3 scripts/install.py --host claude-code`. Set `quality-loop.config.json` (repo root) to `{"enforcement": "required"}` to block medium/high edits before PLAN + MINIMALITY_GATE.

Usage: `claude "Follow the Coding Quality Loop to fix the invoice rounding bug and open a PR."`
