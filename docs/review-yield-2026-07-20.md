# Review yield of the loop's own pipeline (2026-07-20)

What the Coding Quality Loop's independent-review phase has actually caught on
this repo, computed from the committed evidence — `docs/records/*.json` and
`CHANGELOG.md` — not from memory. This is item 4.3 of the v6.1 plan: aggregate
the outcome data already in git before spending on new gates.

## Denominators (read this first)

- **Only four releases carry a committed agent-record with a review section:**
  v4.1.0, v4.2.0, v5.1.0, v6.0.1. The CHANGELOG spans 40+ tagged versions, so
  the review-yield sample below is **4 releases, not the whole history**. No
  record exists for v6.0.0 itself (the v6.0.1 record's `validation_contract`
  carries the v6.0.0 goal); v6.0.0's yield is visible only as its *escapes*.
- **`review_findings` arrays are human summaries, not one row per finding.**
  Counts below are taken from the most granular field available per record
  (`independent_review.findings` where itemized, the `review_findings` summary
  otherwise) and are labelled with which.
- **Findings mix sources**: quality review, a separate cross-family/Codex
  review, an adversarial fresh-context swarm, and security review. They are not
  a uniform unit across releases; do not divide across releases naively.
- **Fix-attribution is only clean where a finding string names its own
  disposition** (v4.2.0 does; the others summarize). CHANGELOG entries describe
  *shipped* changes but do not map 1:1 back to review findings, so a global
  fix-conversion rate **cannot** be computed from git today. That gap is the
  point of the three tracked numbers at the end.

## Per-release independent-review findings

| Release | Findings (source) | Disposition as recorded | Security review |
|---|---|---|---|
| v4.1.0 | 8 quality (`independent_review.findings`) + 5 cross-family Codex/GPT-5.5 (`review_findings` summary) | "resolved or explicitly accepted"; the 5 Codex "all [resolved]" — resolved-vs-accepted split not itemized | approve, **0 findings**, 6 adversarial probes |
| v4.2.0 | 18 (`review_findings`, itemized) | **16 FIXED/STRENGTHENED, 1 ACCEPTED out-of-scope, 1 REJECTED by adversarial verification** | none (`security_review: null`) |
| v5.1.0 | 3 (`review_findings`) | **0 blocking; all advisory, kept as-is on candor grounds** | none (`security_review: null`) |
| v6.0.1 | 1 note (`independent_review.findings`, collapsed summary) | both v6.0.0 majors reproduced-then-fixed; 2 minors fixed in follow-up | approve, 1 note |

Reading it honestly:

- **v4.2.0 is the one release with a clean fix-conversion figure: 16/18 = 89%**
  (16 shipped diff changes; 1 accepted no-change; 1 correctly rejected as a
  false positive by adversarial verification). This is the strongest evidence
  the review phase converts findings into fixes rather than noise.
- **v5.1.0's 3 findings were all advisory and deliberately not "fixed"** — the
  correct outcome, but it means "findings → fixes" is 0/3 there. A raw
  conversion rate that ignores severity would misread this as review failure.
- **v6.0.1's single "note" is a summary collapse, not one finding.** It stands
  in for reproducing and fixing the two v6.0.0 escapes plus two follow-up
  minors — i.e. it under-counts what that pass did.

## The two strongest data points the repo owns

1. **Four review rounds missed two majors that a fifth (higher-effort) pass
   caught.** CHANGELOG 6.0.1: "a fifth review pass (Fable 5, xhigh) found in the
   shipped v6.0.0 — the higher-effort pass caught what four earlier rounds did
   not." The two escapes were both trust-chain holes: (a) review-freshness read
   an empty post-merge diff as *stale*, and (b) `security_review.diff_sha256`
   was never validated, so a security approval survived later code changes at the
   highest-risk tier. Effort level, not another round, is what moved recall —
   consistent with the "more rounds, more noise" literature the plan cites.

2. **v6.0.0 was tagged while failing its own `verify` umbrella.** On the merge
   commit `origin/main == HEAD`, so the diff was empty and the freshness gate
   marked the honestly-attested review stale: the shipped tag could not pass the
   gate the release exists to enforce. Fixed in v6.0.1 (empty diff → N/A). This
   is the loop's own dogfood catching the loop — the most credible evidence in
   the repo, precisely because it is unflattering.

Both are **post-ship escapes**: defects that cleared review and shipped, then
were caught after the tag. That is the metric a verification tool must watch
about itself, and the repo currently has **2 recorded post-ship majors (both in
v6.0.0, both fixed in v6.0.1)** and 0 recorded escapes from the releases that
carry security review with itemized findings.

## The three numbers a future release should track

Track these per release, recorded in the agent-record so they aggregate without
this manual mining:

1. **Findings/release** — count of *itemized* independent-review findings
   (quality + security + swarm), stored one row per finding, severity-tagged, so
   the denominator stops being a summary string.
2. **Fix-conversion rate** — of blocking/major findings, the fraction that
   produced a shipped diff change (advisory-kept-as-is excluded from the
   denominator, not counted as a miss). Only v4.2.0 supports this today (89%);
   make it computable for every release by tagging each finding's disposition.
3. **Post-ship escapes** — majors found *after* the tag (currently 2, both
   v6.0.0). This is the recall number that matters; everything else is precision
   or volume.
