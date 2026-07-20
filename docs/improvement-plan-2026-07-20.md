# Improvement plan: coding-quality-loop v5.1.0

Date: 2026-07-20
Method: deep research + adversarial critique. 16 parallel fresh-context analyses (9 codebase
subsystem maps, 7 external-landscape research sweeps over 2025–26 primary sources), followed by
7 adversarial critics (self-contradiction, red-team, complexity, adoption UX, efficacy,
future-proofing, result quality), a consolidation pass, and a 3-judge scoring panel
(maintainer / skeptical adopter / empiricist). Every finding below was verified against the
current repo (post-v3.2 fixes, post-v5.1); none of the 28 surviving candidates was
premise-false on spot-check. This document supersedes nothing; it picks up where
`docs/critical-review-2026-07-09.md` left off and covers the three releases that landed after it.

---

## Part 1 — Where CQL actually stands (against the 2025–26 landscape)

### Validated leads — keep, sharpen, publicize

1. **Deterministic gates + evidence re-execution is the right bet, now with citations.**
   The reward-hacking literature (METR, ImpossibleBench, Anthropic's Nov-2025
   emergent-misalignment result) converged on: prompt-only mitigation is dead, LLM monitors
   degrade under pressure (~63% hack-trajectory detection), and layered *deterministic*
   verification is what works (measured 28.6%→0.6% hacked-resolved in benchmark studies).
   "Deterministic gates over vibes" is no longer philosophy; it is the documented failure mode
   of the alternative.
2. **Cross-family fresh-context review is ahead of the field.** Self-preference bias is now
   quantified (EMNLP 2025); practitioner data shows ~2× catch rates for cross-model review.
   Almost nobody else enforces family heterogeneity *in config*. One caveat to measure rather
   than assume: one controlled study found review benefit is asymmetric (GPT reviewing Claude
   drafts measured worse) — CQL's default direction deserves an ablation arm, not faith.
3. **Task classes / ceremony-scales-with-risk is the #1 hard-won field lesson.** BMAD-class
   uniform ceremony is what practitioners abandon; right-sizing is the consensus. CQL had it
   first.
4. **The right-size ladder is genuinely novel** — no surveyed tool asks "should this change
   exist at all." It is also an underappreciated hack detector (hardcoding/special-casing
   hacks systematically inflate diff size).
5. **The memory design matches the strongest evidence** (write-time distillation, budget-capped
   recall, prune/dedup — the ACE/Memp lineage), and "memory is advisory, gates are
   deterministic" is exactly the defense-in-depth the poisoning literature recommends.
6. **Agentic QA of the harness itself** (~171 offline gate cases) is a practice the literature
   now explicitly calls for and almost nobody does.
7. **The layer bet is right.** 2026's "thin harness, fat skills" consensus: execution
   scaffolding is depreciating tech debt; *verification* scaffolding, evals, and audit
   infrastructure are the durable assets. CQL's durable assets are its gates, eval cases,
   bench protocol, and memory — its orchestration choreography is the part models will absorb.

### The uncomfortable mirror

- CQL's own live evidence shows a **model-specific interaction, not a uniform lift**: of six
  family-cells across the live evals, only two (both Claude) show positive code-quality lift;
  Codex is flat-to-negative in every measured run (−1.11, −9.0). The README's "same agent, same
  model — the difference is the process" framing oversells what the project's own data supports.
- The field's measurement crisis (METR's RCT: felt +20%, measured −19%) makes CQL's ablation
  infrastructure rare and valuable — **and it has never been run**. `bench/results/` contains
  one synthetic fixture. The single highest-credibility move available to this project is also
  the one it keeps deferring.

---

## Part 2 — Contradictions, gaps, and blind spots (verified, current)

### C1. The central contradiction: "every gate must earn its tokens" — zero gates ever measured
`philosophy.md:75-77` and `README.md:82,298` state retention requires measured eval delta.
Reality: no live ablation has ever been committed; the "15–22k tokens of process scaffolding"
figure presented as measurement is the prior review's *estimate*; the 3.6–5.7× wall-time
overhead measured in the webapp eval has no token/cost companion anywhere — in a repo that
ships a 2,256-line dashboard whose specialty is counting exact tokens.

### C2. The enforcement inversion, round two
v3.2 closed the CI copy-attack and widened the stop gate. What remains, verified:

- **The only local enforcement point never re-executes evidence.** `stop_gate.py:111` runs
  `verify-gates`, not the `verify` umbrella — `run-evidence` and AC-coverage run only if a
  human types them. Fabricated `{result: "pass", evidence: "tests pass"}` rows clear the Stop
  gate today.
- **Commit-first evasion:** default `--base HEAD` means an agent that commits its work makes
  every diff-grounded gate (scope, secrets, risk floor, test-weakening, bugfix co-presence)
  see an empty diff — while the *honest* clean-tree agent gets a false "phantom completion."
- **The flagship AC contract is vacuous for string criteria** (`quality_loop.py:1571-1583`
  branches only on dict ACs) — and the project's own dogfood record has seven all-string ACs,
  so "every criterion paired with the check that proves it" checked nothing at home.
- **Honesty is punished:** any `blocked` command row fails verify-gates with "ensure rationale
  is recorded" — but no rationale field is ever read. The honest agent's only path to green is
  deleting the row or relabeling it `pass`.
- **The harness lives in the agent's writable tree**: nothing stops an edit to
  `quality_loop.py` or `rm .quality-loop/agent-record.json` (record-missing ⇒ stop allowed).
  Research names evaluator immutability the single most effective anti-hack mitigation.
- **Hard rule 6 has no deterministic owner for deletion/gutting**: `test_weakening_hits`
  flags only *added* skip/xfail lines; deleting test functions or gutting assertions passes
  every gate.
- Smaller but real: scope-integrity globs whitelist entire subtrees from one mapped file and
  are case-broken for `Button.tsx`-style paths; the bugfix detector misses the word "fix";
  the `verify` umbrella hardcodes a 30s evidence timeout that reads honest slow suites as
  fabricated; `e2e`/`security` passes don't count as executable evidence; blocking findings
  print as `warning:` and that string is load-bearing (parsed by eval-cases and verify).

### C3. The delivery gap: the moat's own vehicle is shipped broken
- `assets/prompts/reviewer.md` and `security-reviewer.md` contain literal
  `{contract}/{diff}/{evidence}` placeholders that **no code substitutes**;
  `docs/cross-cli-recipe.md:28` pipes them raw — the flagship cross-family reviewer literally
  receives the string `{diff}`.
- `cql check` **permanently fails** after a successful cursor or pi install and tells the user
  to run the command that can never fix it; post-install next steps print commands that error;
  the npm README promises a Codex `AGENTS.md` that `install.py` never writes — the #2 host
  gets no instructions at all.
- A missing `scripts/quality_loop.py` turns every Write/Edit into a **fabricated
  "secret-like text blocked"** deny (any nonzero scan-text exit is treated as a finding);
  hardcoded `python3` makes the Windows stop gate silently never fire.
- Two config files with overlapping authority (`.quality-loop/config.json` vs root
  `quality-loop.config.json`) — a key in the wrong one silently no-ops. No uninstall exists.

### C4. The simplicity gap: the project stopped practicing its own scarcity
- Scripts **doubled** since the review that warned about surface (3,381 → 6,689 lines).
  The largest module is the opt-in, never-a-gate control plane (2,256 lines — bigger than the
  gate engine it observes), which also shipped `control-report`, the exact "report subcommand"
  `ROADMAP.md:171-175` and `docs/control-plane.md:45-47` still explicitly forbid.
- A medium task's paper trail is **8–9 markdown artifacts of which gates read zero** —
  unverified ceremony by the project's own standard, at a measured 3.6–5.7× wall-time cost.
- The always-loaded SKILL.md carries the author's personal `agent-os` paragraph, a dated
  four-model vendor table (in a "vendor-neutral" project whose roadmap bans exactly this),
  and a control-plane section — token-diet violations in the one file every session pays for.
- `tool-contracts.md` ships 7 speculative tool interfaces no code consumes — the precise
  "abstraction justified by imagined future needs" its own reviewer checklist flags.
- Docs drift recurred one release after the drift lint shipped: the README "proof you can run"
  block produces 144 cases against a claimed 171; the lint *rewrote history* (ROADMAP's v3.0
  entry now claims today's count) and skips CONTRIBUTING.md, the one doc that drifted.

### C5. Blind spots (things no current mechanism sees)
- **Test strength**: research shows agent-written tests are largely theater; CQL checks test
  *presence*, never *teeth* (mutation-lite is on the roadmap, unbuilt).
- **The −9.0 monolith mechanism** is guarded only by prose in files workers never load.
- **No outcome feedback**: nothing records whether shipped work was clean, regressed, or
  reverted — the lessons store learns from process, never from consequences.
- **Model-name decay**: heterogeneity checking silently degrades to "skip" on unknown model
  ids; the moat gate dies quietly at every model generation.
- **Memory defects**: recall *writes* (bumps hit counters, dirtying two git-tracked files and
  merge-conflicting by design); one global lesson permanently taxes every project's recall
  budget 40%; no coordination story with Claude Code's native auto-memory; no lesson
  provenance or staleness check.

---

## Part 3 — The plan

Guiding rules, in order: (1) make existing promises true before making new ones; (2) each wave
nets *negative* lines and docs; (3) every fix lands with an eval case; (4) anything not
measurable gets an honest label until it is.

### Wave 1 — Make the promise true (robustness; mostly S/M, net-simpler)

| # | Change | Core move |
|---|--------|-----------|
| 1.1 | **Unify local enforcement** | Stop gate calls the `verify` umbrella (not `verify-gates`); default base becomes resolved merge-base (reuse `_resolve_base()` seeded with `origin/main`) in stop_gate + verify/verify-gates argparse; replace the hardcoded 30s evidence timeout with `QUALITY_LOOP_TIMEOUT`. Kills both fabricated-evidence pass-through and commit-first evasion, and stops punishing honest committers with false phantom-completion. Top-ranked item (4.58, triple-endorse). |
| 1.2 | **Harden AC coverage** | At medium+ risk, string ACs produce a finding (dicts with `proving_command` required); advisory warning when ≥3 ACs share one umbrella command. Call site moves into the Stop path via 1.1. |
| 1.3 | **Make `blocked` rows satisfiable** | Only flag blocked rows lacking a non-empty `reason`; document the field. Removes the perverse incentive against sandbox honesty. |
| 1.4 | **Protect the harness and the record** | PreToolUse deny on Write/Edit targeting `quality_loop*.py`/the active record/config; add record-deletion patterns to the Bash checks. ~5 lines on the existing deny path. Label honestly: tamper-evidence, not immutability. |
| 1.5 | **Close hard-rule-6's gap + mechanize the monolith lesson** | ~30-line net-assertion-loss / removed-test-declaration counter (blocking at medium+); advisory-only under-fanning warning (medium+ AND added LOC >~300 AND ≥90% in one new file). The historical ts-search monolith diff must fire it; a modular baseline must not. |
| 1.6 | **Fix the small gate bugs in one pass** | Scope-integrity case bug + `**` glob over-matching; add "fix" to bugfix keywords (and stop over-matching "debugging"); count `e2e`/`security`/`format` as executable evidence; print blocking findings as `error:` (return structured findings instead of parsing the `warning:` prefix). |
| 1.7 | **Honesty rewording (interim)** | Until Wave 4 runs: `README.md:82/298` and `philosophy.md:76` change from "we measure it" to "the retention standard we have not yet met"; add the ImpossibleBench-backed escalation sentence to SKILL.md ("if an AC and its check conflict, stop and report — never work around"). |

### Wave 2 — Fix first contact (usability)

| # | Change | Core move |
|---|--------|-----------|
| 2.1 | **Fix the npm funnel** | Install manifest per host (installer emits what it wrote; `cql check` verifies the manifest, deleting its hand-maintained array); demote cursor/pi from the picker to documented recipes (surface parity without capability parity is a trap); next-step commands must all exit 0; ship `AGENTS.md` on codex install; drop `evals/` from the tarball. |
| 2.2 | **Fix cross-CLI review delivery** | ~30-line `render-prompt --role reviewer\|security-reviewer --record …` subcommand substituting contract/diff/evidence; recipe pipes its output. Inline the 7 security bullets into the security card (one screen); blocking findings require a taint path or reproduction — evidence-free findings are advisory (the 82–86% security-scan FP literature demands this). |
| 2.3 | **Truthful hook failures** | scan-text failure ≠ secret found (distinguish missing/broken runtime, allow + warn with the fix); `sys.executable` everywhere; remedy text on the terminal-status block branch. New hook evals: missing-script, missing-python3. |
| 2.4 | **One config file + uninstall** | Root `quality-loop.config.json` canonical; one-release fallback read + misplaced-key warning; `--uninstall`/`cql remove` driven by the 2.1 manifest; `init → remove → git status` clean as the integration test. |
| 2.5 | **One quickstart, a truthful proof block** | `docs/quickstart.md` becomes the single onboarding path (drop-in prompt → npx → manual, ordered by commitment); README links instead of duplicating; proof block gains the missing step so it actually prints 171; lint covers CONTRIBUTING.md and stops rewriting history (exempt `as of vX` annotations; restore the true v3.0 count). |
| 2.6 | **Fix or scope the destructive-command regexes** | Order-insensitive flag matching, anchored to command position, with FP/FN eval pins (`rm -fr` denied; `grep "git reset --hard"` allowed) — keeping the list because 1.4 extends it. |

### Wave 3 — Shrink (simplicity; every item net-negative)

| # | Change | Core move |
|---|--------|-----------|
| 3.1 | **Collapse the medium paper trail 8–9 → 4** | Merge task-contract + validation-contract into one `contract.md`; delete pr-summary (subset of completion record), standalone decision-log and execution-log (fold one-line guidance into progress.md + the record); replace the stale v2.4 completion-record with a ~30-line blank template. Zero gate coverage lost — no deleted template is machine-checked. |
| 3.2 | **Strip SKILL.md residue** | Delete the agent-os paragraph (→ cross-cli-recipe, labeled as one user's setup); collapse the control-plane section to a pointer; replace named vendor models with capability-class rows pointing at `assets/routing/` (the location the roadmap itself designates for dated menus); lint pins zero vendor ids / personal config in SKILL.md. |
| 3.3 | **SKILL.md accuracy + single-sourcing pass** | "Rules 1–8 each have a deterministic owner"; add the missing sentence **"risk trumps size — any risk-boundary change is medium+ regardless of diff size"** (the highest-stakes ambiguity in the file); add the pre-review right-size re-run; render machine enums inline in the ladder (`1 no change (skip) · 2 delete (delete) …`); fix the three dangling `§Roles` pointers; replace duplicated lists with pointers; document `.quality-loop/allowed-commands` format where agents can find it. |
| 3.4 | **Delete speculative/dead surface** | The 7 unconsumed tool shapes (~170 lines), the deprecated advisor-history section, duplicate citations, the validated-but-never-read `recall_budget_chars` key (wire it or delete it); lint: every documented tool shape maps to a registered subcommand. |
| 3.5 | **Control plane: diet in place, demote from default** | Judges' consensus (lighter form of extraction): move to an in-repo optional subtree; remove from the default install copy-set and npm prepack; drop its 27 cases from the headline count. In place: record the worker session id at hand-off and **delete** the ~60-line fuzzy time-window join (making its two attribution bugs structurally impossible); one shared incremental reader; droid runs become events, not 0-token pseudo model-calls; zero-usage drift canaries so a vendor format rename turns the dashboard yellow instead of confidently wrong. Resolve the doctrine contradiction by naming `control-report` the sanctioned audit surface (or deleting it) and documenting the 3 missing subcommands in tool-contracts. |
| 3.6 | **Memory: read-only recall + one pool + outcome feedback** | Recall stops writing (hit-bump becomes opt-in at RETROSPECT) — no more dirty working trees and designed merge conflicts; merge the 60/40 global/project split into one ranked pool; rewrite docs/memory.md against the real schema; document coexistence with Claude Code auto-memory (scope split + combined budget); add `--outcome clean\|regressed\|reverted` to `memory-commit` — the loop's first-ever signal from consequences, riding an existing subcommand. |
| 3.7 | **Single-source the reviewer contract** | `assets/prompts/reviewer.md` canonical; `setup-models` (which already rewrites agent frontmatter) stamps the body into host copies; one verdict enum (`approve\|request_changes\|needs_discussion\|reject`, down from 9 accepted variants); `ran_checks` becomes a schema field verify-gates warns on at medium+; reviewer agent allowlist gains `run-evidence` so executing checks is actually possible on the flagship host. |

### Wave 4 — Measure, then decide (evidence; unlocks the deferred decisions)

| # | Change | Core move |
|---|--------|-----------|
| 4.1 | **One pre-registered protocol** | Merge the three drifting bench docs into `bench/PROTOCOL.md`: version-neutral arms {baseline, full, no-review, light}; delete the fictional mutation-metric claims; delete unexecutable task stubs 01–12; regenerate the stale fixture. Pre-registered decision rules so a run *forces* an outcome — including the R5 branch (Codex excl-D7 ≤ 0 at n=3 ⇒ ship `process_depth: full\|light`; else close R5 and delete the hedge) and a small-task-tax rule (tiny path >1.5× baseline tokens ⇒ the always-loaded ladder text becomes a cut candidate). |
| 4.2 | **Close the cost loop with the instrument already shipped** | `control-report` query emitting tokens/duration per eval arm from indexed sessions; one CI line running `--validate` on every committed results file (both current ones fail it today); README's estimate replaced by the measured figure. |
| 4.3 | **Run the ablation (capped ~36 runs) — or retract** | Stage 1: webapp × {baseline, v5-full} × {Claude, Codex} × 3 seeds (satisfies the R5 replication gate). Stage 2: add {no-review} — the highest-information arm, since independent review is the most expensive component. Stage 3 optional second task for the ≥2-tasks pruning rule. Commit results; apply the pruning rule; celebrate the deletions in the changelog. |

**Decisions deliberately deferred until 4.3's data exists** (the judges rejected doing these now):
- Collapsing task classes 4 → 2 (3.3's one-sentence precedence fix covers the acute problem; structural churn awaits evidence the split buys nothing).
- Binding reviewer identity to model family in the record (self-reported model id is as fakeable as a self-reported name; revisit as a warn-only cross-check when control-plane session data can corroborate it).
- A second cross-family reviewer, EARS-style AC grammar, procedural-memory promotion, worktree-per-worker lanes — each is one ablation arm or one optional template away, and none earns surface before the measurement discipline exists.

### What this plan does *not* do
No new subsystems. No hosted anything. No orchestration breadth (hosts are commoditizing it).
No mutation-testing engine yet (1.5's assertion-loss counter is the 30-line version; `mutate-lite`
stays a roadmap item until Wave 4 proves cheaper gates first). Waves 1–3 are net-negative in
lines and docs; Wave 4 is the only place new machinery (one protocol doc, one CI line) appears,
and its purpose is to *delete* whatever the data says doesn't pay.

---

## The one-paragraph version

CQL's core bets — deterministic verification, cross-family review, ceremony scaled to risk —
are now the measured consensus of the field; its problem is that it stopped holding itself to
them. The enforced path still trusts self-reported JSON at the exact points that matter, the
funnel breaks on first contact for half its advertised hosts, the surface doubled against its
own scarcity doctrine, and the retention rule it sells ("every gate must earn its tokens") has
never once been exercised. The next cycle is therefore not about adding capability: make the
existing promises mechanically true (Wave 1), make first contact work (Wave 2), shrink to what
gates actually read (Wave 3), then run the measurement that decides everything still argued
about in prose (Wave 4).
