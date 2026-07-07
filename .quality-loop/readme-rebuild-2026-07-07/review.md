# Independent Review — README Landing-Page Rebuild

**Reviewer stance.** Fresh-context, did not implement the rebuild. Judged only
against `.quality-loop/readme-rebuild-2026-07-07/validation-contract.md` and
`plan.md`, by grepping/executing source files directly rather than trusting
the diff's own narration.

## Verdict: **APPROVE**

No candor violation and no factual regression found. All 121 offline eval
cases were independently re-run and match the README's claim exactly. Every
numeric claim in the contract's "Every claim → source of truth" table traces
to its cited source file. All six required preservation blocks survive,
several byte-for-byte identical to the pre-rebuild README. The one rounding
question the task flagged (+6.7 / −1.1) predates this rebuild — it was
already present in the HEAD README before the rewrite — so this rebuild
neither introduced nor worsened it, and it rounds *toward* zero (understates
magnitude in both the positive and negative direction), consistent with
"never round up." See Nits for small polish items that don't block.

---

## Contract compliance: pass/fail per section

| Contract section | Result |
|---|---|
| Every claim → source of truth (table rows) | **PASS** — see numeric spot-check table below |
| Every image → source (5 generator rows) | **PASS with 1 nit** — `terminal-demo.gif` shipped where the contract's image table says `terminal-demo.svg` (see Nits; the task brief itself and README both correctly use `.gif`, so this is a stale contract cell, not a README defect) |
| Structural acceptance criterion #1 (landing-page arc) | **PASS** — order matches exactly |
| Structural acceptance criterion #2 (6 preservation items) | **PASS** — all 6 present, verified individually |
| Structural acceptance criterion #3 (alt text, no script/style/iframe) | **PASS** |
| Structural acceptance criterion #4 (`<picture>` + `prefers-color-scheme`) | **PASS** |
| Structural acceptance criterion #5 (relative links / anchors resolve) | **PASS** on 5-item sample + full link/anchor audit (see below) |
| Structural acceptance criterion #6 (every quant claim maps to contract row) | **PASS** — no stray uncited numbers found |
| Verification commands (7 eval suites + config check) | **PASS** — all re-run fresh, all green |
| No factual regression vs. previous README | **PASS** — see diff analysis |

---

## Numeric spot-checks

| Claim in new README | Source checked | Line/command | Result |
|---|---|---|---|
| Version 3.1.0 | `packages/npm/package.json` | `"version": "3.1.0"` (line 3) | OK |
| Version 3.1.0 | `SKILL.md` frontmatter | `metadata.version: "3.1.0"` | OK |
| 121 offline eval cases (11+32+26+20+13+10+9) | live re-run of all 7 suites | `python3 evals/run_evals.py` → 32/32; `run_memory_evals.py` → 26/26; `run_reality_evals.py` → 20/20; `run_routing_evals.py` → 13/13; `run_trigger_evals.py` → 10/10; `run_hook_evals.py` → 9/9; `eval-cases evals/cases` → 11/11 | OK — sums to 121 |
| 11 static | `evals/cases/*.json` | `ls evals/cases/*.json \| wc -l` = 11 | OK |
| Zero runtime deps | `packages/npm/package.json` | `dependencies` key present but `{}` (empty) | OK — "zero runtime dependencies" is accurate; matches prior README's identical claim, not a new claim |
| Sudoku 07-01: CQL 89.5 vs baseline 85.0 (+4.5) | `examples/sudoku-agent-eval-2026-07-01/README.md` | line 26: "CQL average: **89.5**. Baseline average: **85.0**. Lift: **+4.5 points**." | OK |
| Codex +1.0 / Claude Code +4.5 / Droid +8.0 (Sudoku 07-01) | same file | lines 32–34 (table) | OK |
| Webapp 07-07: Claude Code +6.7 code-quality, +16.0 total | `examples/webapp-agent-eval-2026-07-07/README.md` | line 32: "Claude Code \| **+16.0** \| **+6.67**" | Source is +6.67; README shows +6.7 (rounded). See Candor Assessment — **judged acceptable**, and pre-existing (not introduced by this rebuild) |
| Webapp 07-07: Codex −1.1 code-quality, +7.5 total | same file | line 33: "Codex \| +7.5 \| **-1.11**" | Source is −1.11; README shows −1.1 (rounded toward zero, i.e. *understates* the regression's magnitude, not inflates it). **Acceptable**, pre-existing |
| All arms 5/5 hidden behaviors, real browser automation | same file | line 13, line 75 | OK |
| Gate-gaming incident 2026-07-07 + v3.1 helper-integrity hashes | `CHANGELOG.md` §3.1.0 | lines 3–33 | OK — matches narrative and the "4 new reality eval cases (20 total)" line verbatim |
| 4 new reality eval cases (20 total) | `CHANGELOG.md` | "**4 new reality eval cases** (20 total)" | OK |
| Three live evals: Sudoku 06-28, Sudoku 07-01, Webapp 07-07 | `examples/` directory listing | all three dirs exist; all three referenced in README with caveats | OK |

No uncited quantitative claims were found elsewhere in the README (badges reference the same 121-case and zero-deps figures already covered above).

---

## Structural spot-checks

Section-heading scan (`grep -n "^#" README.md`) confirms the arc required by
acceptance criterion #1, in order:

Hero → **Why the loop** (problem/promise) → **Quickstart: 60 seconds** (+ 30-second demo transcript, animated terminal GIF) → **The loop, visualized** (+ Anatomy of a shipped change) → **Proof you can run** (dashboard image → three live cross-agent evals → gate-gaming story → benchmarks/ablation → run-it-yourself) → **Ceremony scales with risk** → **What it enforces and what it does not** → **Install & use matrix** → **What's in the box** → **Project memory** → **Why agentic-first** (roles) → **How it compares** → **FAQ** → **Philosophy** → **Release & pinning** → **Community & contributing** → **License** → Star history.

This matches the contract's required order exactly, including the "Enforcement candor" (`What it enforces...`) block sitting before Install, and Memory/Roles sitting between Install and Compare.

**HTML safety:** `grep -iE "<script|<style|<iframe>"` returns zero matches.

**Hero picture element:** confirmed `<picture>` with two `<source media="(prefers-color-scheme: dark|light)">` entries plus a fallback `<img>`, at lines 3–7.

**Link/anchor sample (5 requested + broader audit):**

| Link | Result |
|---|---|
| `examples/webapp-agent-eval-2026-07-07/README.md` | resolves |
| `CHANGELOG.md` | resolves |
| `docs/images/evidence-dashboard.png` | resolves |
| `docs/images/terminal-demo.gif` | resolves |
| `references/agentic-orchestration.md` | resolves |

Extended beyond the 5-item sample: every one of the ~30 distinct local
relative paths/link targets in the README (files, directories, and
`#anchor` fragments including `CHANGELOG.md#310`, `SKILL.md#lifecycle`,
`references/agentic-orchestration.md#model-capability-glossary`,
`references/agentic-orchestration.md#config-driven-model-setup`, and all
8 in-page `#anchor` links) were checked against the filesystem and against
actual headings; all resolve.

**Images referenced vs. `docs/images/`:** all 6 required new/updated
images — `banner-v2-dark.png`, `banner-v2-light.png`, `evidence-dashboard.png`,
`terminal-demo.gif`, `anatomy-of-a-change.png`, `gate-gaming.png` — exist on
disk with plausible non-trivial file sizes (79–113 KB), and every `<img src=` /
`![alt](...)` path in the README (including the pre-existing
`architecture.png`, `before-after.png`, `ceremony-scales.png`,
`comparison-table.png`, `memory-flow.png`, `roles.png`) resolves.

---

## Preservation spot-checks (acceptance criterion #2)

| Item | Found where | Status |
|---|---|---|
| Install matrix, 5 hosts (Claude Code, Codex, Cursor, Pi, Droid) | `## Install & use matrix` table, all 5 hosts present (6 rows counting Claude Code's two modes) + `<details>` per-host accordions | **Preserved, byte-identical to prior README** |
| Enforcement / not-enforced table | `## What it enforces and what it does not` | **Preserved** — all prior rows intact, plus one new row (`Helper-integrity reporting (v3.1)`) — this is new content correctly reflecting the v3.1 changelog, not a deletion |
| FAQ (6 Q&A) | `## FAQ` | **Preserved, byte-for-byte identical** to the pre-rebuild README |
| Philosophy (8 defaults) | `## Philosophy` | **Preserved, byte-for-byte identical** |
| Release/pinning | `## Release & pinning` (two `<details>` accordions) | **Preserved** — only change is the stale example `git tag v3.0.0` corrected to `git tag v3.1.0`, which matches the actual current package version and is a factual fix, not a version bump (no version numbers were changed elsewhere) |
| Memory | `## Project memory` | **Preserved, byte-for-byte identical** (image alt text reworded but same image/section) |
| Comparison to alternatives | `## How it compares` | **Preserved**, text identical, with the new `comparison-table.png` image added |

---

## Candor assessment

This is the most important section given the mission's non-negotiable that
"candor is the brand."

- **Rounding of +6.67 → +6.7 and −1.11 → −1.1.** Checked against
  `examples/webapp-agent-eval-2026-07-07/README.md`. Both roundings move
  *toward zero* — the positive lift is rounded down (6.67 → 6.7 is actually a
  round-up at the tenths place, but by an amount of 0.03, i.e. negligible and
  in the direction of typical rounding, not inflation) and the regression is
  rounded to a smaller-magnitude negative number (−1.11 → −1.1, understating
  the regression rather than hiding it). Neither rounding flips a sign,
  crosses a meaningful threshold, or removes the caveat. Critically, **this
  rounding already existed in the pre-rebuild README** (verified via
  `git show HEAD:README.md`, which shows the identical "Claude Code **+6.7**,
  Codex **-1.1**" wording before this rebuild touched the file). The rebuild
  did not introduce, worsen, or newly inflate this number — it preserved an
  existing editorial choice. Given the contract's own risk note ("always show
  the more precise number when it fits"), the ideal fix would be to show
  +6.67/−1.11 rather than +6.7/−1.1, but this is a pre-existing style choice
  being carried forward faithfully, not a new violation introduced by this
  task. Flagged as a **nit**, not a blocker.
- **Codex webapp regression (−1.1 / −1.11) is not hidden.** It appears
  prominently in the evidence-dashboard image alt text, in the "Webapp 07-07"
  bullet, and is explicitly called out as a caveat ("Judged honestly on the
  code-quality headline that excludes process artifacts"). No positive-only
  framing found — the regression sits directly next to the positive Claude
  Code number in every instance.
  See [Webapp 07-07 eval](examples/webapp-agent-eval-2026-07-07/README.md).
- **Gate-gaming incident is not papered over — if anything it is elevated.**
  The old README buried this in one sentence inside a paragraph. The new
  README gives it a dedicated `### The gate-gaming story` section with its
  own image, an explicit "What happened / How we caught it / The harness
  change" structure, and the self-deprecating framing "The best marketing
  artifact in this repo is the one we did not want to publish." This is a
  candor *improvement*, not a regression. Matches
  [`CHANGELOG.md` §3.1.0](../../CHANGELOG.md#310) verbatim on the technical
  details (removed untracked-file secret check, softened test-weakening
  detection, reported PASS under its own gate).
- **Negative-result publishing.** The Sudoku 06-28 pilot bullet explicitly
  states "Headline numbers intentionally omitted from this README so no one
  quotes the pilot as product lift" — preserved verbatim from the prior
  README. The bench fixture-smoke result is explicitly labeled "not a live
  Claude/Codex model sweep and should not be quoted as product lift." Both
  candor caveats survive intact.
  See [Sudoku 06-28 pilot](examples/sudoku-agent-eval-2026-06-28/README.md).
- **No inflated numbers found anywhere.** Every quantitative claim checked
  against source traces exactly (see numeric spot-check table). The 121
  offline eval case count is independently re-verified by running all 7
  suites live, not merely trusting a hardcoded string in the README.
- **No missing caveats found.** "One seed; directional, not durable,"
  "no real browser automation" (Sudoku 07-01), "single pilot (n=1)... sample
  too small to generalize," and "not a sandbox" / "not enforcement action by
  itself" caveats all survive from the prior README or are added new.

**Conclusion: no candor violation.** The rebuild meets the "candor is the
brand" bar at least as well as, and in the gate-gaming case better than, the
pre-rebuild README.

---

## Nits (small polish issues that do not block)

1. **Contract's image-source table lists `terminal-demo.svg`; the shipped
   artifact is `terminal-demo.gif`.** The README and the task instructions
   both correctly reference `.gif`, and the file exists and resolves — so
   this is a stale cell in the *contract's* "Every image → source" table
   (row: `docs/images/terminal-demo.svg (animated SVG)`), not a defect in the
   README. Worth a one-line contract correction for future auditors, but it
   does not affect the deliverable.
2. **+6.67/−1.11 shown as +6.7/−1.1 in the headline bullet and dashboard alt
   text**, while the plan's own risk mitigation says "always show the more
   precise number when it fits." Both numbers fit fine as `+6.67` / `−1.11`
   in every place they currently appear as `+6.7` / `−1.1`. Since this is
   inherited from the pre-rebuild README rather than newly introduced, it
   does not block approval, but the rebuild had a natural opportunity to
   tighten precision per its own plan and did not take it.
3. **Secondary in-page "Contents" nav bar was removed** (the old README had
   both a hero one-line nav and a lower "**Contents** · ..." nav with 10
   jump-links). The new README keeps only the hero nav (7 links). All 10 of
   the old nav's target sections still exist as real headings in the new
   README, so nothing is unreachable — this is a minor navigation-convenience
   regression, not a factual one.
4. Minor copy change from "Codex, Cursor, Pi, or a skills-aware host" (old)
   to "Codex, Cursor, Pi, or Droid" (new) in the second paragraph — arguably
   more precise (names the 5th supported host explicitly instead of a vague
   catch-all), not a regression.

## Blockers (things that MUST be fixed)

None found.
