# Coding Quality Loop (Codex AGENTS.md)

Follow the Coding Quality Loop: produce the smallest correct change with enough evidence to
trust, review, revert, or merge it.

Lifecycle: three phases, **PLAN → EXECUTE → REVIEW**, each closed by its own verification
gate. Sub-steps under each phase (unchanged machine names): PLAN groups `INTAKE`, `EXPLORE`, `MINIMALITY_GATE`, `PLAN`
EXECUTE groups `IMPLEMENT_SLICE`, `VERIFY`; REVIEW groups `REVIEW`, `PACKAGE`, `RETROSPECT`.

PLAN:
1. **INTAKE** — goal, acceptance criteria, constraints, assumptions, risk tier
   (`low|medium|high`), verification plan.
2. **EXPLORE / PLAN** — map only relevant files, callers, tests, config; name likely files
   and the checks you will run.
3. **MINIMALITY_GATE** — pick the highest valid rung (no change, delete, reuse, stdlib,
   native, existing dependency, one-liner, minimal new code). Never trade away security,
   validation, authorization, accessibility, or data-loss protection.

EXECUTE:
4. **IMPLEMENT_SLICE** — one small, reviewable slice in existing conventions.
5. **VERIFY** — run the smallest sufficient checks first; record exact commands and results.

REVIEW:
6. **REVIEW** — independent fresh-context review against the contract.
7. **PACKAGE** — goal, files changed, minimality decision, evidence, risks, rollback, follow-ups.

Escalate before destructive migrations, secret exposure, payments/billing, production infra,
ambiguous user-facing behavior, or after two failed repair loops.

## Agentic routing

Use Codex subagents for role separation (planner, implementer, independent reviewer) and back
`verification_runner` / `repo_mapper` with MCP servers
(https://developers.openai.com/codex/concepts/customization). This loop can also ship as a
Codex skill directory (`SKILL.md` + scripts/references) invoked with `$coding-quality-loop`
(https://developers.openai.com/codex/skills). AGENTS.md precedence: global
`~/.codex/AGENTS.md`, then project, then nested overrides
(https://developers.openai.com/codex/guides/agents-md).

To wire per-role models and reasoning levels from your config, fill the
`model_routing` section in `quality-loop.config.json` and run:

```bash
python3 scripts/quality_loop.py setup-models --host codex
```

This prints the `model`, `model_reasoning_effort`, and per-role `config_file`
layer TOML to add to `~/.codex/config.toml` (or a trusted `.codex/config.toml`).
No files are written; copy the output into your Codex config.

## Optional Codex hooks

Copy `hosts/codex/hooks.json` to `.codex/hooks.json` or run:

```bash
python3 scripts/install.py --host codex
```

Codex project hooks are advisory until the project `.codex/` layer is trusted and
the hook definitions are approved in `/hooks`. They call the same core CLI:
`scan-text`, `verify-gates --against-diff`, and the session context shim.

## One-line usage

```bash
codex --ask-for-approval never "Follow the Coding Quality Loop in AGENTS.md to fix the failing test and summarize verification evidence."
codex --cd services/payments --ask-for-approval never "List the instruction sources you loaded, then run the loop on the refund bug."
```
