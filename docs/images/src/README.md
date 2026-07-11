# Image generators

Every image in `docs/images/` that is not a photograph or a screenshot has
a matching generator source in this folder. This keeps the media
regenerable, reviewable in `git diff`, and grounded — no hidden Figma or
external tool is required to re-render or tweak them.

## Regenerate all

```bash
python3 docs/images/src/banner_v2.py           # banner-v2-dark.png, banner-v2-light.png
python3 docs/images/src/evidence_dashboard.py  # evidence-dashboard.png
python3 docs/images/src/terminal_demo.py       # terminal-demo.gif, terminal-demo-poster.png
python3 docs/images/src/anatomy.py             # anatomy-of-a-change.png
python3 docs/images/src/gate_gaming.py         # gate-gaming.png
```

Requires: Python 3.10+, `matplotlib`, `Pillow`. No other dependencies.

## Source-of-truth invariants

- `banner_v2.py` — headline copy sourced from `README.md` value prop; the
  three phases match `SKILL.md` §Lifecycle (PLAN → EXECUTE → REVIEW).
- `evidence_dashboard.py` — 144 offline gate cases and the 6-suite breakdown are
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

> Regenerated 2026-07-12 for v4.2.0 (144 gate cases / 6 suites / 5 published
> eval runs) via a scratch matplotlib venv. If you change a count, re-run
> `python3 docs/images/src/evidence_dashboard.py` so the PNG stays in sync —
> the numbers-consistency lint now covers this file.
