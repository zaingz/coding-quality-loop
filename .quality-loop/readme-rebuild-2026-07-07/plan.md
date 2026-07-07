# Plan — README Landing-Page Rebuild

## Files touched

- **Edit:** `README.md` (rewrite, preserve all facts)
- **Add:** `docs/images/banner-v2-dark.png`, `banner-v2-light.png`,
  `evidence-dashboard.png`, `terminal-demo.svg`, `anatomy-of-a-change.png`,
  `gate-gaming.png`
- **Add:** `docs/images/src/banner_v2.py`, `evidence_dashboard.py`,
  `terminal_demo.py`, `anatomy.py`, `gate_gaming.py`, `README.md` (generator index)
- **Add:** `.quality-loop/readme-rebuild-2026-07-07/{validation-contract,plan,execution-log,review,completion-record}.md`

## Slices

1. **Slice 1: media generators.** Author 5 Python generators + 1 SVG demo;
   produce PNG/SVG outputs at 1600–1800px width; keep file sizes reasonable.
2. **Slice 2: README rewrite.** Rebuild the file structure with the
   landing-page arc; keep every factual block (fold long-tail into
   `<details>`); wire `<picture>` for light/dark hero.
3. **Slice 3: verification.** Grep every relative link/anchor/image path
   against the repo; run all 7 eval suites + `check-config`; render preview
   locally by scanning for orphaned refs.
4. **Slice 4: independent review.** Fresh-context reviewer (this agent
   opening a new mental context, no shortcuts) walks the contract row by row.
5. **Slice 5: completion record + commits.** Stage a clean commit series.

## Verification commands

```
python3 -m py_compile scripts/*.py evals/*.py
python3 scripts/quality_loop.py check-config assets/quality-loop.config.example.json
python3 scripts/quality_loop.py eval-cases evals/cases --config assets/quality-loop.config.example.json
python3 evals/run_evals.py
python3 evals/run_memory_evals.py
python3 evals/run_reality_evals.py
python3 evals/run_hook_evals.py
python3 evals/run_trigger_evals.py
python3 evals/run_routing_evals.py
```

## Risks & rollback

- **Risk:** Numeric drift (round +6.67 to +6.7 loses precision). **Mitigation:**
  always show the more precise number when it fits; call out that
  −1.1 is a code-quality-only bar; keep both totals visible.
- **Risk:** Broken image path silently fails in GitHub render. **Mitigation:**
  grep every `<img src=` and `![alt](` against filesystem before finishing.
- **Rollback:** `git checkout HEAD -- README.md docs/images/`.

## Non-goals

No code changes. No SKILL.md changes. No CHANGELOG changes. No version
bumps. No changes to eval counts.
