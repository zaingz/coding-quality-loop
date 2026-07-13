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

- `evidence_dashboard.py` — 164 offline gate cases and the 7-suite breakdown are
  the same numbers `README.md` publishes and `evals/` pins (the trigger smoke
  fixture is excluded). Per-agent lift values come from
  `examples/sudoku-agent-eval-2026-07-01/README.md` and
  `examples/webapp-agent-eval-2026-07-07/README.md`. Every number in the
  chart is traceable to a repo file.
- `terminal_demo.py` — line prefixes (`[ok]`, `Overall: PASS`,
  `VERIFY — unified gate report`) match the actual `scripts/quality_loop.py
  verify` output; `helper-integrity: sha256(...)` matches the v3.1.0
  addition in `CHANGELOG.md`.
- `anatomy.py` — every card references a real field in
  `examples/walkthrough/agent-record.json`.
- `gate_gaming.py` — story paraphrased from `CHANGELOG.md` §3.1.0 and
  `examples/webapp-agent-eval-2026-07-07/README.md`.

If you change a source-of-truth number in the repo, update the generator
and re-run it — the media should stay in sync with the record.

> Regenerated 2026-07-13 for v5.0.0 (164 gate cases / 7 suites / 5 published
> eval runs; two routed hosts — Claude Code + Codex). If you change a count,
> re-run `python3 docs/images/src/evidence_dashboard.py` so the PNG stays in
> sync — the numbers-consistency lint now covers this file.
