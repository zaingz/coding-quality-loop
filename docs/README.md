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

## Contributing and releasing

| Topic | File |
|---|---|
| How to contribute | [`../CONTRIBUTING.md`](../CONTRIBUTING.md) |
| Security policy | [`../SECURITY.md`](../SECURITY.md) |
| Roadmap | [`../ROADMAP.md`](../ROADMAP.md) |
| Changelog | [`../CHANGELOG.md`](../CHANGELOG.md) |

## Images used across the docs

All images live under `docs/images/`. The README currently ships five dark-themed
diagrams; regenerable sources are in [`images/src/`](images/src/README.md).

- `banner-v2-dark.png` + `banner-v2-light.png` — README hero (wired via `<picture>` + `prefers-color-scheme`).
- `terminal-demo.gif` (+ `terminal-demo-poster.png` fallback) — 60-second quickstart demo.
- `anatomy-of-a-change.png` — seven-card walkthrough traced on `examples/walkthrough/agent-record.json`.
- `evidence-dashboard.png` — 144 offline gate cases across 6 suites + honest per-agent lift, with the Codex webapp regression published in red.
- `gate-gaming.png` — three-panel comic of the 2026-07-07 gate-gaming incident and its harness fix.
