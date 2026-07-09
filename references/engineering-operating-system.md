# The Engineering Operating System

The Coding Quality Loop is not a better prompt. It is an *operating system* for coding agents:
a set of durable, portable artifacts that make agent work consistent, verifiable, and
improvable across sessions, models, and platforms.

## Why "operating system," not "prompt"

The industry trend is unambiguous: ad-hoc prompting is being replaced by reusable process
artifacts and durable instructions. Each converging trend maps to an artifact this skill ships —
prompting → durable instructions, capability → skills, one context → orchestration, vague
verification → validation contract, complexity creep → complexity discipline, advisory text →
deterministic gates, context stuffing → repo maps. The full trend analysis and the prior-art
citations behind each move live in [`philosophy.md`](philosophy.md) (§ Trends we have observed,
§ Inspirations); "The Five Parts" below is how those transitions land as concrete artifacts.

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
5. **Complexity discipline** — the right-size gate (deletion → reuse → stdlib → native →
   existing dependency → one-liner → minimal new code), applied before planning and again
   before review.

## Task Classes

Default to the smallest class that safely satisfies the goal.

| Class | Triggers | Artifacts | Roles |
|---|---|---|---|
| **Tiny** | typo, copy, one-line config, obvious test update | none beyond the handoff | one agent |
| **Small** | local bug, one module, low risk | context map (light), mini spec, targeted test | one agent |
| **Medium** | multiple files, feature, migration, auth/payment/data risk | validation contract, plan, completion record | implementer + independent validator (+ security reviewer at boundaries) |
| **Mission** | multi-day, multi-module, multi-repo, uncertain architecture | all mission artifacts + milestones | orchestrator + context mapper + workers + validators + simplicity/security reviewers |

Scaling rules:

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

The minimum tool set, useful extensions, and the "MCP only when" rule are defined once in
[`tool-contracts.md` § Tool Surface Guidance](tool-contracts.md#tool-surface-guidance).

## The Improvement Loop

The harness is the unit of improvement: instructions, tools, routing, output requirements, and
validation checks ([OpenAI Agent Improvement Loop](https://developers.openai.com/cookbook/examples/agents_sdk/agent_improvement_loop)).

1. Collect signals: traces, validator findings, escaped defects, diff size, evidence rate,
   dependencies added, repeated mistakes.
2. Rank candidate harness changes by impact.
3. Apply the change as a durable artifact — an `AGENTS.md`/`SKILL.md` rule, a test, a hook, a
   review-checklist item, a repo-map entry, or a validation-contract template.
4. Pin a regression eval so the fix sticks.

Every repeated failure becomes a durable harness change, not a repeated chat correction.
