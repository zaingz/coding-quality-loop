# Validation Contract — README Landing-Page Rebuild

**Goal.** Rebuild `README.md` as a landing-page-grade front door: bold hero,
progressive proof, honest numbers, zero factual regressions.

**Task class.** Medium (docs + media, no code changes).
**Risk tier.** Low-to-medium (public-facing marketing surface; brand-damage
risk if numbers are inflated).
**Non-goals.** Edit code, edit gates, edit `SKILL.md` frontmatter, change
version numbers, change eval counts, delete existing factual content.

## Every claim → source of truth

| Claim in new README | Source file |
|---|---|
| Version 3.1.0 | `packages/npm/package.json` line 3; `SKILL.md` frontmatter |
| 121 offline eval cases | `README.md` current line 267; verified by suite counts below |
| 11 static | `evals/cases/*.json` count = 11 |
| 32 behavioral | `evals/run_evals.py` current README line 267 |
| 26 memory | `evals/run_memory_evals.py` current README line 267 |
| 20 reality | `evals/run_reality_evals.py` + CHANGELOG "4 new reality eval cases (20 total)" |
| 13 routing | `evals/run_routing_evals.py` current README line 267 |
| 10 trigger | `evals/run_trigger_evals.py` — verified: `10/10 trigger eval cases passed` |
| 9 hook | `evals/run_hook_evals.py` current README line 267 |
| Zero runtime deps | `packages/npm/package.json` (no `dependencies` field / stdlib-only helper) |
| Signed npm provenance | current README badge; Sigstore search link |
| Works on 5 hosts | current install matrix rows: Claude Code, Codex, Cursor, Pi, Droid |
| Sudoku 07-01: CQL 89.5 vs baseline 85.0 (+4.5) | `examples/sudoku-agent-eval-2026-07-01/README.md` |
| Codex +1.0 / Claude Code +4.5 / Droid +8.0 (Sudoku 07-01) | same |
| Webapp 07-07: Claude Code +6.7 code-quality, +16.0 total | `examples/webapp-agent-eval-2026-07-07/README.md` (source: +6.67 / +16.0) |
| Webapp 07-07: Codex −1.1 code-quality, +7.5 total | same (source: −1.11 / +7.5) |
| All arms 5/5 hidden behaviors (real browser automation) | webapp eval README |
| Gate-gaming incident: 2026-07-07, softened diff-audit, PASS reported; v3.1 helper-integrity hashes | `CHANGELOG.md` §3.1.0 + webapp eval README |
| Three live evals in `examples/` | rust-procmon, sudoku-06-28, sudoku-07-01, ts-search, webapp-07-07 all exist. **The three currently promoted are Sudoku 07-01, Webapp 07-07, Rust procmon (or ts-search)**. Keep the two that mission spec highlights: **07-01 Sudoku, 07-07 Webapp, plus Sudoku 06-28 pilot** — same as current README |

## Every image → source

| Image (new) | Generator source | Alt text pattern |
|---|---|---|
| `docs/images/banner-v2-dark.png` + `banner-v2-light.png` | `docs/images/src/banner_v2.py` | "Coding Quality Loop — PLAN → EXECUTE → REVIEW …" |
| `docs/images/evidence-dashboard.png` | `docs/images/src/evidence_dashboard.py` | numbers-forward summary |
| `docs/images/terminal-demo.svg` (animated SVG) | `docs/images/src/terminal_demo.py` | 60-second quickstart |
| `docs/images/anatomy-of-a-change.png` | `docs/images/src/anatomy.py` | anatomy of a shipped change |
| `docs/images/gate-gaming.png` | `docs/images/src/gate_gaming.py` | gate-gaming incident story |

Existing images are preserved as-is (not deleted) and continue to appear
in-line where they add value.

## Structural acceptance criteria

1. Landing-page arc order: Hero → Problem/promise → 60-second quickstart
   with animated demo → Loop visualized → Proof (dashboard + 3 live evals +
   gate-gaming panel + run-it-yourself commands) → Ceremony scales →
   Enforcement candor → Install matrix → Memory + Roles → Compare → FAQ →
   Philosophy → Release/pinning → Community → License.
2. Every existing factual block survives: install matrix (all 5 hosts),
   enforcement/not-enforced table, FAQ (6 Q&A), philosophy (8 defaults),
   release/pinning, memory, comparison to alternatives. Long-tail depth may
   move into `<details>` accordions.
3. Every image has descriptive alt text. No `<script>`, `<style>`,
   `<iframe>`. Only GitHub-flavored Markdown allowed HTML.
4. `<picture>` + `prefers-color-scheme` used for the hero banner.
5. Every relative link resolves; every anchor points at a real heading.
6. Every quantitative claim in the README maps to a row in this contract.

## Verification commands (must pass)

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

Docs-presence lints inside these suites must remain green.

## Rollback

`git checkout HEAD -- README.md docs/images/` restores the pre-rebuild
state. New generator sources under `docs/images/src/` and new images can be
deleted without touching code.
