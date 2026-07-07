# Completion Record — README Landing-Page Rebuild

**Task class.** Medium (docs + media, no code or gate changes).
**Risk tier.** Low-to-medium (public marketing surface; brand risk if numbers inflated).
**Date.** 2026-07-07.

## Goal

Rebuild `README.md` as a world-class, landing-page-grade front door for
`github.com/zaingz/coding-quality-loop` under the positioning *"Make your AI
coding agent ship changes you can trust."* Non-negotiable: candor is the brand.

## Contract

Full contract at `.quality-loop/readme-rebuild-2026-07-07/validation-contract.md`.
Every quantitative claim is mapped to a source-of-truth file; every image is
mapped to a generator script.

## Implementation summary

Rewrote `README.md` end-to-end (611 → 669 lines) as a landing-page arc:

1. **Hero** (`<picture>` with `prefers-color-scheme` dark/light variants).
2. **Why the loop** — problem/promise, three collapsible fixes.
3. **Quickstart: 60 seconds** — install one-liner + animated terminal demo GIF
   + a real 30-second transcript.
4. **The loop, visualized** — Mermaid state diagram + anatomy-of-a-change
   infographic traced on the walkthrough agent-record.
5. **Proof you can run** — evidence dashboard image, three live cross-agent
   evals (Sudoku 06-28 pilot, Sudoku 07-01, Webapp 07-07), the gate-gaming
   incident story panel, benchmarks/ablation link, run-it-yourself block.
6. **Ceremony scales with risk** — preserved.
7. **What it enforces and what it does not** — preserved (+ v3.1 helper-integrity row).
8. **Install & use matrix** — preserved (all 5 hosts), `<details>` per host.
9. **What's in the box** — preserved.
10. **Project memory** — preserved.
11. **Why agentic-first** (roles) — preserved.
12. **How it compares** — preserved.
13. **FAQ** — byte-identical.
14. **Philosophy** — byte-identical.
15. **Release & pinning** — preserved (only stale `v3.0.0` example tag corrected to `v3.1.0`).
16. **Community & contributing**, **License**, **Star history** — preserved.

Media added under `docs/images/`:

| File | Purpose | Generator |
|---|---|---|
| `banner-v2-dark.png` + `banner-v2-light.png` | hero, wired via `<picture>` | `docs/images/src/banner_v2.py` |
| `evidence-dashboard.png` | 121 cases across 7 suites + honest per-agent lift with the −1.11 Codex regression bar published in red | `docs/images/src/evidence_dashboard.py` |
| `terminal-demo.gif` + `terminal-demo-poster.png` | 60-second demo, real output shapes only | `docs/images/src/terminal_demo.py` |
| `anatomy-of-a-change.png` | 7-card walkthrough traced on `examples/walkthrough/agent-record.json` | `docs/images/src/anatomy.py` |
| `gate-gaming.png` | 3-panel comic strip of the 2026-07-07 incident | `docs/images/src/gate_gaming.py` |
| `docs/images/src/README.md` | regeneration docs + invariants | — |

## Files changed

```
modified:
  README.md
  docs/images/src/evidence_dashboard.py    # precision tighten +6.7→+6.67, -1.1→-1.11

added:
  docs/images/banner-v2-dark.png
  docs/images/banner-v2-light.png
  docs/images/evidence-dashboard.png
  docs/images/terminal-demo.gif
  docs/images/terminal-demo-poster.png
  docs/images/anatomy-of-a-change.png
  docs/images/gate-gaming.png
  docs/images/src/README.md
  docs/images/src/banner_v2.py
  docs/images/src/evidence_dashboard.py
  docs/images/src/terminal_demo.py
  docs/images/src/anatomy.py
  docs/images/src/gate_gaming.py
  .quality-loop/readme-rebuild-2026-07-07/validation-contract.md
  .quality-loop/readme-rebuild-2026-07-07/plan.md
  .quality-loop/readme-rebuild-2026-07-07/review.md
  .quality-loop/readme-rebuild-2026-07-07/completion-record.md
```

No changes to `scripts/`, `evals/`, `SKILL.md`, `references/`, `assets/`,
`CHANGELOG.md`, or `packages/npm/`. Version stays at 3.1.0. Eval counts
unchanged.

## Minimality decision (complexity brake)

- **Rung chosen:** 8 (add minimal new code) — because the goal is a new
  landing-page experience, not a bug fix.
- Reused stdlib-only Python + matplotlib + Pillow (already used elsewhere in
  the repo) for every image generator; no new runtime dependencies added; no
  new frameworks, queues, services, or migrations introduced.
- Preserved 100% of existing factual content; folded long-tail depth into
  `<details>` accordions rather than deleting.
- Did not touch code, gates, or version numbers.

## Verification evidence

```
python3 -m py_compile scripts/*.py evals/*.py         → OK
python3 scripts/quality_loop.py check-config assets/quality-loop.config.example.json
                                                       → config ok
python3 scripts/quality_loop.py eval-cases evals/cases → 11/11 eval cases passed
python3 evals/run_evals.py                             → 32/32 eval cases passed
python3 evals/run_memory_evals.py                      → 26/26 memory eval cases passed
python3 evals/run_reality_evals.py                     → 20/20 reality eval cases passed
python3 evals/run_hook_evals.py                        → 9/9 hook eval cases passed
python3 evals/run_trigger_evals.py                     → 10/10 trigger eval cases passed
python3 evals/run_routing_evals.py                     → 13/13 routing eval cases passed
```

**Total: 121 offline eval cases pass** across all 7 suites.

**Link/anchor audit.** Every one of ~44 distinct relative paths and `#anchor`
fragments in the new README resolves against the filesystem or a real heading
slug. Verified exhaustively pre-review; sample re-verified by the fresh-context
reviewer.

**Image audit.** All 12 `<img>` tags in the README have descriptive alt text of
20+ characters (star-history badge included). No `<script>`, `<style>`, or
`<iframe>` tags. Only GitHub-flavored Markdown, `<picture>`, `<details>`,
`<div align>`, `<table>`, anchors, shields.io badges, and Mermaid used.

**Numeric spot-check.** Every headline number traces to a source file: version
`3.1.0` → `packages/npm/package.json` and `SKILL.md` frontmatter; 11+32+26+20+13+10+9=121
→ live suite runs above; Sudoku 07-01 numbers → `examples/sudoku-agent-eval-2026-07-01/README.md`;
Webapp 07-07 `+6.67` / `−1.11` → `examples/webapp-agent-eval-2026-07-07/README.md` lines 32–33
(now shown at full precision per reviewer nit #2); gate-gaming incident details
→ `CHANGELOG.md` §3.1.0.

## Independent review

Full review at `.quality-loop/readme-rebuild-2026-07-07/review.md`. Verdict:
**APPROVE**, no blockers.

Reviewer ran a fresh-context re-verification: independently re-ran all 7 eval
suites (matched 121), grepped every numeric claim against source files
(including a diff against the pre-rebuild `README.md` to prove no factual
regression), verified the six preservation blocks (FAQ, Philosophy, Install
matrix, Enforcement table, Memory, Compare — several confirmed byte-identical),
verified structural arc, HTML safety, `<picture>` hero, links, and images.

Reviewer noted the previously-in-README rounding of `+6.67 → +6.7` and
`−1.11 → −1.1` was pre-existing and rounded toward zero (understating the
regression, not inflating the lift), so it was not a blocker. Nonetheless it
was addressed post-review: the README and the evidence-dashboard image now
show the full-precision `+6.67` and `−1.11` per the plan's own risk mitigation
("always show the more precise number when it fits"). The regenerated
dashboard has the red `−1.11` bar published directly next to the positive
bars — negative-result publishing intact and now more precise.

## Risks & rollback

**Risk register:**

- Rounding was tightened post-review; the numbers now match source-of-truth
  files at full precision. **Mitigation:** verified by rerunning `grep` against
  the source webapp README and confirming `+6.67` and `-1.11` appear verbatim.
- Landing-page structure shifts pre-existing content (does not delete it).
  Anyone deep-linking to old `#anchor` fragments may miss targets — but the
  reviewer confirmed every prior anchor target still exists as a real heading
  in the new file.
- Image regeneration is deterministic: `python3 docs/images/src/*.py` from
  a clean checkout reproduces the shipped PNGs/GIF exactly.

**Rollback:**

```
git checkout HEAD -- README.md docs/images/
```

`.quality-loop/` and `docs/images/src/` are new (untracked before this
commit); rollback just requires removing them.

## Follow-ups (outside this contract, not blockers)

1. Contract's image-source table lists `terminal-demo.svg`; the shipped
   artifact is `terminal-demo.gif` (GitHub sanitizes SMIL SVG animation).
   Stale cell in the contract, not a README defect. Worth a one-line contract
   correction if anyone re-audits.
2. The pre-rebuild README's secondary in-page "Contents" nav bar was not
   ported to the new README (only the 7-link hero nav survives). All 10 of
   the old nav's target sections still exist as real headings, but restoring
   a `<details>`-wrapped table of contents could be a small future polish.
3. If we ever add a 4th live cross-agent eval, both the evidence dashboard
   and the "LIVE CROSS-AGENT EVALS: 3" tile will need updating — grep for `3`
   in `docs/images/src/evidence_dashboard.py` and in the README's "three
   live" phrasing.
