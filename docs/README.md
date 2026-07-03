# Docs index

Extended documentation for the [Coding Quality Loop](../README.md). The top-level
[`README.md`](../README.md) is the tour; this folder is the manual.

## Start here

| If you want to… | Read |
|---|---|
| Try it in 60 seconds | [`quickstart.md`](quickstart.md) |
| Understand how the pieces fit | [`architecture.md`](architecture.md) |
| Compare it to superpowers, addyosmani/agent-skills, or ponytail | [`comparison.md`](comparison.md) |
| Learn how project memory works | [`memory.md`](memory.md) |
| See the whole skill body, task classes, and roles | [`../SKILL.md`](../SKILL.md) |
| Read the manifesto | [`../references/philosophy.md`](../references/philosophy.md) |

## Deep dives (in `references/`)

| Topic | File |
|---|---|
| The step-by-step operating model | [`references/lifecycle.md`](../references/lifecycle.md) |
| Role → host wiring (Claude, Codex, Cursor, Pi, Droid) | [`references/agentic-orchestration.md`](../references/agentic-orchestration.md) |
| The engineering operating system framing | [`references/engineering-operating-system.md`](../references/engineering-operating-system.md) |
| Reviewer checklists (validator, security) | [`references/reviewer-checklists.md`](../references/reviewer-checklists.md) |
| Tool contracts for hosts | [`references/tool-contracts.md`](../references/tool-contracts.md) |
| Memory contract | [`references/memory.md`](../references/memory.md) |
| Honcho backend contract | [`references/memory-honcho.md`](../references/memory-honcho.md) |
| Graphify integration pattern | [`references/memory-graphify.md`](../references/memory-graphify.md) |

## Contributing and releasing

| Topic | File |
|---|---|
| How to contribute | [`../CONTRIBUTING.md`](../CONTRIBUTING.md) |
| Security policy | [`../SECURITY.md`](../SECURITY.md) |
| Roadmap | [`../ROADMAP.md`](../ROADMAP.md) |
| Changelog | [`../CHANGELOG.md`](../CHANGELOG.md) |

## Images used across the docs

All images live under `docs/images/`. Every diagram is generated with the same visual
language: off-white cream background, thin black borders, teal-green accents.

- `banner.png` — README hero. Depicts the seven customer-facing sub-steps of the loop (INTAKE, PLAN, IMPLEMENT, VERIFY, REVIEW, SHIP, LEARN); these map onto the three canonical phases as PLAN = INTAKE + PLAN, EXECUTE = IMPLEMENT + VERIFY, REVIEW = REVIEW + SHIP + LEARN.
- `before-after.png` — README "without vs with the loop"
- `architecture.png` — three-layer architecture. The gate-command lineup shows a representative subset; the full CLI catalogue is in [`architecture.md`](architecture.md).
- `roles.png` — multi-agent role separation
- `memory-flow.png` — project memory recall/commit
- `ceremony-scales.png` — ceremony scaling with risk
- `comparison-table.png` — how it compares to other skills
