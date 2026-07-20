# Image generators

Every programmatic image in `docs/images/` (charts, diagrams, terminal
captures) has a matching generator source in this folder. This keeps the
media regenerable, reviewable in `git diff`, and grounded — no hidden Figma
or external tool is required to re-render or tweak them.

The dark-theme art assets in `docs/images/art/` (`hero-art.png`,
`orchestrator-layer.png`, `loop-phases.png`, `gates.png`) are the v5.0.0
visual identity and are **not** generated here — they are illustrated
assets, checked in as-is.

## Regenerate all

```bash
python3 docs/images/src/evidence_dashboard.py  # evidence-dashboard.png
python3 docs/images/src/terminal_demo.py       # terminal-demo.gif, terminal-demo-poster.png
python3 docs/images/src/anatomy.py             # anatomy-of-a-change.png
python3 docs/images/src/gate_gaming.py         # gate-gaming.png
```

Requires: Python 3.10+, `matplotlib`, `Pillow`. No other dependencies.

## Source-of-truth invariants

- `evidence_dashboard.py` — the gate-case count and suite breakdown must be
  the same numbers `README.md` publishes and `evals/run_evals.py` pins
  (`CANONICAL_GATE_CASES` / `CONTROL_ADDON_CASES`; the trigger smoke fixture is
  excluded). The committed PNG was rendered with 171 gate cases as of v5.1.0 and
  needs a re-render for the current counts. Per-agent lift values come from
  `archive/eval-runs/sudoku-agent-eval-2026-07-01/README.md` and
  `archive/eval-runs/webapp-agent-eval-2026-07-07/README.md`. Every number in the
  chart is traceable to a repo file.
- `terminal_demo.py` — line prefixes (`[ok]`, `Overall: PASS`,
  `VERIFY — unified gate report`) match the actual `scripts/quality_loop.py
  verify` output; `helper-integrity: sha256(...)` matches the v3.1.0
  addition in `CHANGELOG.md`.
- `anatomy.py` — every card references a real field in
  `examples/walkthrough/agent-record.json`.
- `gate_gaming.py` — story paraphrased from `CHANGELOG.md` §3.1.0 and
  `archive/eval-runs/webapp-agent-eval-2026-07-07/README.md`.

If you change a source-of-truth number in the repo, update the generator
and re-run it — the media should stay in sync with the record.

> Last regenerated 2026-07-13 (171 gate cases as of v5.1.0 / 7 suites / 5
> published eval runs; two routed hosts — Claude Code + Codex). The v6.1.0
> counts (234 core + a 35-case control add-on) are NOT yet rendered: re-run
> `python3 docs/images/src/evidence_dashboard.py` (needs matplotlib) so the PNG
> catches up — the numbers-consistency lint covers this file.
