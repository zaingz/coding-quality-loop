# Coding Quality Loop

`coding-quality-loop` is a portable, **agentic-first** Agent Skill for turning high-level
software goals into small, verified code changes — with the right model on each step.

It packages:

- An 8-step lifecycle: intake, exploration, planning, minimality, implementation,
  verification, review, and handoff.
- **Agentic orchestration**: each step is routed to a role-based agent profile so teams use
  cheap/fast models for routing, strong reasoning for architecture, code-specialized models
  for implementation, and an independent reviewer for review.
- Reference checklists for risk tiering and fresh-context review.
- Tool contracts for repo mapping, verification runners, reviewer agents, and policy hooks.
- Templates for task contracts, state records, and PR summaries.
- A lightweight helper script plus an offline eval harness.

## Why agentic-first

One model doing intake, architecture, implementation, and self-review is the common failure
mode: it inflates its own confidence and skips evidence. This skill splits the loop into
role-based profiles (`contract_agent`, `repo_mapper`, `planner`, `minimality_reviewer`,
`implementer`, `verification_runner`, `fresh_reviewer`, `packager`, `policy_guard`) and lets
you map each role to the best available model. Defaults stay simple — **one implementer +
one independent reviewer + deterministic policy hooks** — and you add specialized agents only
when risk justifies it. See `references/agentic-orchestration.md`.

## One-line usage by platform

Drop the skill in, then invoke it. These are starting points; full copy-paste files live in
`examples/`.

**Claude Code** — add the loop to project memory, then run:

```bash
cp examples/claude-code/CLAUDE.md ./CLAUDE.md   # or run /init then paste the loop
claude "Follow the Coding Quality Loop to fix the invoice rounding bug and open a PR."
```

**Codex** — the loop lives in `AGENTS.md`:

```bash
cp examples/codex/AGENTS.md ./AGENTS.md
codex --ask-for-approval never "Follow the Coding Quality Loop in AGENTS.md to fix the failing test."
```

**Cursor** — project rule in `.cursor/rules`:

```bash
cp -r examples/cursor/.cursor ./.cursor
# Then in chat: @coding-quality-loop fix the retry bug with verification evidence
```

**Standalone / custom agent** — drive the steps from config:

```bash
python scripts/quality_loop.py check-config assets/quality-loop.config.example.json
# Then route each step per examples/standalone/run-quality-loop.md
```

## Quick adoption paths

Pick the smallest path that fits your risk and tooling:

1. **Instruction-only** — paste the [Minimal Drop-In Prompt](SKILL.md#minimal-drop-in-prompt)
   into one rule/system prompt. No scripts, no config.
2. **Skill package** — load `SKILL.md` plus `references/` and `assets/` so the agent can pull
   checklists, templates, and the state-record schema on demand.
3. **Orchestrated multi-agent** — adopt `assets/quality-loop.config.example.json` and route
   each lifecycle step to a role-based profile (see `references/agentic-orchestration.md`).
4. **Enforced production mode** — add deterministic `policy_guard` hooks for secrets,
   destructive migrations, auth/billing, and diff-size limits, and require human approval on
   high-risk steps.

## Quick start

1. Load `SKILL.md` into your agent or copy the minimal drop-in prompt.
2. For medium/high-risk work, create a state record:

   ```bash
   python scripts/quality_loop.py init-record --goal "Fix checkout retry bug" --risk-tier medium --output agent-record.json
   ```

3. Follow the lifecycle:

   ```text
   INTAKE -> EXPLORE -> PLAN -> MINIMALITY_GATE -> IMPLEMENT_SLICE -> VERIFY -> REVIEW -> PACKAGE
   ```

4. Audit the diff and verification record before handoff:

   ```bash
   python scripts/quality_loop.py diff-audit --base origin/main
   python scripts/quality_loop.py verify-gates agent-record.json
   ```

5. Validate config and run the offline evals:

   ```bash
   python scripts/quality_loop.py eval-cases evals/cases --config assets/quality-loop.config.example.json
   ```

## A real walkthrough

`examples/walkthrough/` shows a bug fix moving through the full loop — task contract,
minimality decision, verification evidence, and fresh-context review — with the matching
state record in `examples/walkthrough/agent-record.json`.

## How this maps to official docs

The skill is portable but aligns with how today's agent platforms load instructions and
enforce policy:

- **Claude Code memory** — project/user/local `CLAUDE.md`, `.claude/rules/`, `@path` imports,
  and `/init`; keep `CLAUDE.md` concise (~200 lines) and use path-scoped rules as it grows.
  https://docs.anthropic.com/en/docs/claude-code/memory
- **Claude Code hooks** — `PreToolUse` / `PostToolUse` / `Stop` hooks in a shareable
  `.claude/settings.json` are the deterministic `policy_guard`.
  https://docs.anthropic.com/en/docs/claude-code/hooks
- **Codex AGENTS.md** — global `~/.codex/AGENTS.md`, project `AGENTS.md`, and nested
  overrides. https://developers.openai.com/codex/guides/agents-md
- **Codex skills** — `SKILL.md` directories with optional scripts/references/assets, invoked
  with `$skill` or implicitly; progressive disclosure keeps context small.
  https://developers.openai.com/codex/skills
- **Codex customization** — `AGENTS.md`, memories, skills, MCP, and role-specialized
  subagents pair workflow definitions with external systems.
  https://developers.openai.com/codex/concepts/customization
- **Cursor rules** — `.cursor/rules` in `.mdc` format with Always / Auto Attached /
  Agent Requested / Manual rule types, referenced via `@ruleName`.
  https://docs.cursor.com/en/context/rules

## Philosophy

The goal is bounded autonomy: small diffs, explicit contracts, deterministic evidence, and
fresh-context review by an independent agent. The loop should not overcomplicate by default,
and it should never claim success without verification evidence or a clear explanation of
blocked checks.
