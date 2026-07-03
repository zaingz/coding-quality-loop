# Full evaluation report — Rust `procmon` A/B, 2026-07-03

## 1. Headline numbers

Per-variant totals (0-100, average of two blind judges, D7 corrected):

| Variant | Judge 1 (GPT-5) | Judge 2 (Gemini) | Average |
|---|---:|---:|---:|
| codex-baseline | 70.5 | 73.0 | **71.75** |
| codex-cql | 73.0 | 78.5 | **75.75** |
| claude-baseline | 56.5 | 82.0 | **69.25** |
| claude-cql | 68.0 | 85.5 | **76.75** |

Family lift (+CQL vs baseline):

| Family | Baseline | +CQL | Lift |
|---|---:|---:|---:|
| Codex (GPT-5) | 71.75 | 75.75 | +4.00 |
| Claude Code (Sonnet 4.6) | 69.25 | 76.75 | +7.50 |
| **Overall** | 70.50 | 76.25 | **+5.75** |

## 2. Per-dimension breakdown (averaged across both judges)

| Dimension (weight) | codex-baseline | codex-cql | claude-baseline | claude-cql |
|---|---:|---:|---:|---:|
| D1 Correctness (20) | 8.5 | 8.0 | 7.5 | 6.5 |
| D2 Test evidence (15) | 6.5 | 6.0 | 8.5 | 8.0 |
| D3 Code minimality (10) | 8.0 | 9.0 | 7.5 | 7.0 |
| D4 Safety/robustness (10) | 8.0 | 8.0 | 7.0 | 7.0 |
| D5 Idiomatic Rust (10) | 8.0 | 7.5 | 7.0 | 8.0 |
| D6 README (5) | 8.5 | 8.5 | 8.5 | 8.5 |
| **D7 Verification artifacts (10)** | **0.0** | **7.0** | **0.0** | **10.0** |
| D8 Reviewability (10) | 8.0 | 7.0 | 8.0 | 7.5 |
| D9 Scope creep (5) | 9.5 | 9.5 | 8.5 | 9.5 |
| D10 Judge gestalt (5) | 8.0 | 6.5 | 7.0 | 6.5 |

**Reading the table**:
- CQL variants **lost or tied** on D1, D2, D4, D5, D8, D10 in most comparisons.
- CQL variants **won or tied** on D3 (minimality), D6 (README), D7 (artifacts), D9 (no scope creep).
- The +5.75 overall lift is almost entirely D7. On code-quality dimensions the signal is flat.

## 3. Objective machine checks

| Metric | codex-baseline | codex-cql | claude-baseline | claude-cql |
|---|---:|---:|---:|---:|
| Source LOC (src/*.rs) | 929 | 932 | 744 | 968 |
| Test LOC (tests/*.rs) | 42 | 33 | 187 | 214 |
| README lines | 49 | 65 | 170 | 147 |
| Runtime deps | 5 | **2** | 5 | 5 |
| `cargo build --release` | ✅ | ✅ | ✅ | ✅ |
| `cargo test` | ✅ (3+3) | ✅ (5+3) | ✅ (12) | ✅ (6+13) |
| `cargo clippy -- -D warnings` | ✅ | ✅ | ✅ | ✅ |
| `cargo clippy --all-targets -- -D warnings` | ✅ | ✅ | ✅ | ❌ (1 unused-import in tests) |
| `.quality-loop/` artifacts | ✗ | ✅ (7 files) | ✗ | ✅ (7 files) |

Notable observations:

- **codex-cql was the leanest**: only 2 runtime deps (regex, libc) vs 5 in every other variant. It hand-rolled arg parsing and JSON emission, which its judge scored well on D3 (9.0) but hurt on D8 (7.0, "custom parsing is denser to review").
- **claude-cql was the most test-heavy** (214 test LOC, 19 total tests) but **shipped a broken stricter clippy check**. The skill's independent-review step didn't catch a dead import in the integration test file. Real signal.
- The Claude variants have significantly more test evidence (D2: 8.5, 8.0) than Codex (6.5, 6.0), independent of CQL.

## 4. Judge disagreement

Cross-judge absolute delta per variant (corrected totals):

| Variant | J1 | J2 | \|J1 − J2\| |
|---|---:|---:|---:|
| codex-baseline | 70.5 | 73.0 | 2.5 |
| codex-cql | 73.0 | 78.5 | 5.5 |
| **claude-baseline** | **56.5** | **82.0** | **25.5** |
| **claude-cql** | **68.0** | **85.5** | **17.5** |

Judge 1 (GPT-5) was systematically harsher on the Claude family, particularly on D1 (correctness). Judge 2 (Gemini) rated the same code higher. This is a **large cross-model gap** — enough that a single-judge study would tell a different story. Directional signal only.

Both judges agreed on the direction (+CQL better than baseline within each family), but the magnitude is judge-dependent.

## 5. What CQL actually changed in this run

Reading the mission artifacts each CQL variant produced:

**codex-cql** (`variants/codex-cql/.quality-loop/`)
- `validation-contract.md`: each of the 6 subcommands paired with a specific check (e.g. "kill 1 without --force returns exit code 2 and prints ...").
- `plan.md`: 6 slices, each with files touched and verification command.
- `execution-log.md`: records the exact acceptance commands run and their tail output.
- `completion-record.md`: broken-pipe fix noted, minimality choice justified (no clap, no serde_json).

**claude-cql** (`variants/claude-cql/.quality-loop/`)
- 7 artifacts, more thorough than codex-cql. Notable: `decision-log.md` records "replaced `partial_cmp().unwrap()` with `total_cmp()` during independent review to prevent NaN panic".
- `completion-record.md` documents the review pass that caught the NaN bug — a real find. It **did not** catch the dead-import that failed `clippy --all-targets`, though.

The judges saw these and weighted them in D7. On the code-quality dimensions themselves, the artifacts didn't obviously translate to visibly better code — CQL's correctness and test scores were slightly *worse* than the corresponding baselines on average.

## 6. What CQL did **not** improve

Being honest about the null results:

- **D1 Correctness**: baselines matched or beat CQL. codex-baseline landed at 8.5, codex-cql at 8.0. claude-baseline at 7.5, claude-cql at 6.5. If CQL's promise is "correctness through discipline", this run doesn't show that.
- **D2 Test evidence**: CQL variants had slightly fewer tests than baselines (mean 7.0 vs 7.5).
- **D8 Reviewability**: CQL variants scored slightly *lower* here on average (7.25 vs 8.0). The extra `.quality-loop/` dir adds surface area a reviewer has to navigate; not all reviewers value that.
- **D10 Judge gestalt**: both judges' "would I merge this as-is?" gut check was slightly *lower* on CQL variants (6.5 vs 7.5 avg). The artifacts didn't buy the emotional "yes, ship it" reaction — if anything they made reviewers more suspicious.
- The `claude-cql` variant **shipped a broken `--all-targets` clippy** despite an "independent review" step. Real process gap.

## 7. What we can and cannot conclude

**Can conclude (weakly, n=1)**:
- Installing CQL via the live npm package works end-to-end. Both CQL variants completed the task and produced the artifacts as expected.
- CQL variants produce substantive process artifacts (task contracts, plans, execution logs, completion records) that a reviewer can use to verify what was done vs what was intended. D7 scored these at 7 (codex) and 10 (claude) out of 10 — not boilerplate.
- The Claude Code family showed a larger lift (+7.5) than the Codex family (+4.0). Consistent with the earlier sudoku eval in this repo (Claude family +4.5, Codex +1.0).

**Cannot conclude**:
- That CQL improves code correctness, test coverage, or safety in a statistically meaningful sense. The dimension-level evidence is flat-to-negative there.
- That the observed lift generalizes beyond process-legibility. It does not.
- Anything about behavior in real Claude Code / Codex CLI sessions vs the subagent proxies used here. That's a real limitation.

## 8. Suggested improvements to the skill

Two concrete follow-ups the data supports:

1. **The independent-review step needs a `cargo clippy --all-targets` (or equivalent stricter check) requirement for Rust projects.** The claude-cql run failed the stricter check despite completing the review step. Add a language-specific verification checklist to the skill.
2. **The lifecycle docs currently make no promise that CQL improves code quality — but it's easy to read them that way.** Retitle the value proposition around **process legibility and handoff quality**, which is what the numbers actually support. Correctness is downstream of the reviewer, not upstream of the artifact.

## 9. Full artifact list

See `/examples/rust-procmon-eval-2026-07-03/README.md` for the file inventory. Judge JSONs and mappings are preserved untouched for auditability; the corrected D7 scores are in `d7-rescoring.json` and aggregated in `aggregated-corrected.json`.
