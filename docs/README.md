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
| Watch sessions in the local control plane | [`control-plane.md`](control-plane.md) |
| See the whole skill body, task classes, and roles | [`../SKILL.md`](../SKILL.md) |
| Read the manifesto | [`../references/philosophy.md`](../references/philosophy.md) |

## Deep dives (in `references/`)

| Topic | File |
|---|---|
| The step-by-step operating model | [`references/lifecycle.md`](../references/lifecycle.md) |
| Orchestrator/worker topology and model routing | [`references/agentic-orchestration.md`](../references/agentic-orchestration.md) |
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

All images live under `docs/images/`. The v5.0.0 visual identity ships four dark-theme
art assets in [`images/art/`](images/art/) (illustrated, checked in as-is) alongside the
regenerable diagrams whose sources are in [`images/src/`](images/src/README.md).

- `art/hero-art.png` — README hero (PLAN → EXECUTE → REVIEW ring).
- `art/orchestrator-layer.png`, `art/loop-phases.png`, `art/gates.png` — v5 section art (orchestrator topology, loop phases, enforcement gates).
- `terminal-demo.gif` (+ `terminal-demo-poster.png` fallback) — 60-second quickstart demo.
- `anatomy-of-a-change.png` — seven-card walkthrough traced on `examples/walkthrough/agent-record.json`.
- `evidence-dashboard.png` — 171 offline gate cases across 7 suites + honest per-agent lift, with the Codex webapp regression published in red.
- `gate-gaming.png` — three-panel comic of the 2026-07-07 gate-gaming incident and its harness fix.
