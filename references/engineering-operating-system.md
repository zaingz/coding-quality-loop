# The Engineering Operating System

The Coding Quality Loop is not a better prompt. It is an *operating system* for coding agents:
a set of durable, portable artifacts that make agent work consistent, verifiable, and
improvable across sessions, models, and platforms.

## Why "operating system," not "prompt"

The industry trend is unambiguous: ad-hoc prompting is being replaced by reusable process
artifacts and durable instructions.

- **Prompting → durable instructions.** A clever one-off prompt dies with the session.
  `AGENTS.md`, `CLAUDE.md`, and `.cursor/rules` encode standing behavior that every run
  inherits. Short, accurate guidance beats long, vague guidance
  ([Codex best practices](https://developers.openai.com/codex/learn/best-practices)).
- **Capability → skills.** Skills are becoming the portable unit of agent capability: a
  `SKILL.md` with triggers, steps, and exit criteria, plus optional scripts/resources, loaded
  via progressive disclosure — metadata first, full instructions when relevant, extra files on
  demand ([Anthropic Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills),
  [Codex skills](https://developers.openai.com/codex/skills)).
- **One context → orchestration.** Long-horizon work degrades a single context. Factory's
  Missions architecture splits broad work into focused units with fresh agents, shared state,
  validation contracts, and orchestrator/worker/validator roles
  ([Factory Missions](https://factory.ai/news/missions-architecture)).
- **Vague verification → validation contract.** Verification must be a contract — each
  acceptance criterion paired with the check that proves it — not a hand-wave. A fresh
  validator checks the diff against the contract, not the implementer's confidence.
- **Complexity creep → complexity discipline.** Minimalism is a first-class quality property:
  prefer deletion, reuse, stdlib, and native features before new code.
- **Advisory text → deterministic gates.** When a rule matters, enforce it with a hook or a
  check ([Claude Code hooks](https://docs.anthropic.com/en/docs/claude-code/hooks)).
- **Context stuffing → repo maps.** A concise map of important files, symbols, signatures, and
  relationships lets an agent understand the code and request depth on demand, instead of
  reading everything ([Aider repo map](https://aider.chat/docs/repomap.html)).

## The Five Parts

1. **Durable repo instructions** — `AGENTS.md` (global `~/.codex/AGENTS.md`, project, nested
   overrides — closer instructions win), `CLAUDE.md` (project/user/local, imports, `/init`;
   keep ~200 lines), Cursor rules (`.cursor/rules/*.mdc`: Always / Auto Attached / Agent
   Requested / Manual).
2. **Reusable skills** — focused `SKILL.md` workflows with triggers, steps, and exit criteria;
   the portable capability unit, shareable across Claude, Codex, and Pi.
3. **Mission artifacts** — `context-map.md`, `validation-contract.md`, `plan.md`,
   `execution-log.md`, `decision-log.md`, `completion-record.md`. Shared state that makes
   long-horizon work orchestratable.
4. **Independent verification** — implementer and validator separated for non-trivial work;
   the implementer is never the final validator.
5. **Complexity discipline** — the right-size gate, applied before planning and again before
   review. Canonical rung ladder: SKILL.md §Right-Size Gate.

## Task Classes

Default to the smallest class that safely satisfies the goal. The canonical class definitions
(Tiny / Small / Medium / Mission) and the process each requires live in **SKILL.md §Task
Classes**; per-class role mapping is in `agentic-orchestration.md`. This document adds only the
scaling rules:

- A tiny task must not be forced through mission ceremony.
- A medium task must not ship without a validation contract and an independent review.
- A mission must keep shared state compact and review at milestone boundaries with fresh context.

## Harness Implementation Modes

Adopt the lightest mode that fits; combine as risk grows.

1. **Instruction-only** — the loop lives in `AGENTS.md` / `CLAUDE.md` / `.cursor/rules`.
   Advisory. Cheapest to adopt; relies on the model following text.
2. **Skill-based** — ship as a skill directory so it is portable with progressive disclosure:
   - Claude: a Claude skill / `.claude/` command.
   - Codex: `.agents/skills/coding-quality-loop/` or `$HOME/.agents/skills/...`, invoked
     explicitly or implicitly.
   - Pi: `~/.pi/agent/skills/`, `~/.agents/skills/`, `.pi/skills/`, or `.agents/skills/`;
     registered as `/skill:coding-quality-loop`.
3. **Hook-enforced** — deterministic gates: protected-folder writes, format/test after edit,
   dependency-change approval, destructive-command blocks, and the completion-record shipping
   gate. Hooks enforce; text only advises.
4. **Mission agent** — orchestrator + context mapper + workers + validators + simplicity/security
   reviewers, for medium/mission work only.

## Tool Surface

Canonical tool-surface guidance — the minimum tool set, useful extensions, and the "MCP only
when it removes a real manual loop" rule — lives in `tool-contracts.md §Tool Surface Guidance`.

## The Improvement Loop

The harness is the unit of improvement: instructions, tools, routing, output requirements, and
validation checks ([OpenAI Agent Improvement Loop](https://developers.openai.com/cookbook/examples/agents_sdk/agent_improvement_loop)).

1. Collect signals: traces, validator findings, escaped defects, diff size, evidence rate,
   dependencies added, repeated mistakes.
2. Rank candidate harness changes by impact.
3. Apply the change as a durable artifact — an `AGENTS.md`/`SKILL.md` rule, a test, a hook, a
   review-checklist item, a repo-map entry, or a validation-contract template.
4. Pin a regression eval so the fix sticks.

Every repeated failure becomes a durable harness change (canonical: SKILL.md §RETROSPECTIVE) —
not a repeated chat correction.
