# Improvement plan: coding-quality-loop v6.0.1 → v6.1

Date: 2026-07-20 (same-day follow-up to the v6.0.0/v6.0.1 trust-chain release).
Method: 50 fresh-context agents — 6 codebase subsystem maps, 5 external research sweeps over
2025–26 primary sources, 6 adversarial critics (complexity, trust-chain, first-contact,
adaptability, philosophy-gap, eval-validity), consolidation of 43 raw findings into 16 majors,
then two independent verification lenses per major (fact-check against the repo on disk,
worth-check against the simplicity goal). **13 of 16 majors survived both lenses**; the 3
rejections are recorded below with the slivers that survived. Every reproduction claim in
Part 2 was re-executed by a verifier, not quoted from a critic.

Theme of this cycle: v6.0 made the trust chain *honest in design*. The confirmed findings
show it is not yet *true in the field* — the gates fail exactly where a real repo differs
from CQL's own (record path, default branch, OS, language, team size, day one). The next
cycle makes the loop survive contact with repos that are not this repo, and buys the first
real measurement at the lowest possible price. Nothing below adds a subsystem; the largest
additions are ~15 regex lines and three config keys, and several items are pure deletion.

---

## Part 1 — Where CQL stands (mid-2026 landscape, researched today)

**The core bets keep being validated.**
- Anthropic's harness guidance (Mar 2026) moved to Planner/Generator/Evaluator with "sprint
  contracts" — done-criteria agreed before implementation — and names separating the doing
  agent from the judging agent as the strongest empirical lever. That is CQL's validation
  contract + fresh-context reviewer, independently converged on.
- The self-review literature hardened: models miss ~64.5% of errors in their own output while
  catching the same errors from external sources (NeurIPS 2025 WS); cross-context review beats
  same-session review (arXiv 2603.12123). One correction to absorb: **"More Rounds, More
  Noise" (arXiv 2603.16244) finds iterated multi-round review *degrades* verification —
  single-pass with complete context wins.** CQL's single attest-then-done shape is right;
  never add review rounds.
- Deterministic gates outperform bigger reviewer models ("Reason Less, Verify More", arXiv
  2607.07405: +12.4pp task success from a four-gate deterministic suite; practitioner
  consensus: deterministic checks catch 60–70% of structured failures before any LLM looks).
- Reward-hacking research converged on CQL's stance: prompt-level defenses fail (METR: "do
  not hack" cut o3's rate 80%→70%), any agent-writable checker breaks (UC Berkeley, Apr 2026:
  8 major benchmarks broken at ~100% via conftest interception and patched test runners), and
  environment-level separation is what holds. Cursor's June 2026 finding that 63% of one
  model's SWE-bench Pro "successes" were retrieval, discovered only after sealing git history,
  is the field-scale version of CQL's phantom-completion lesson.

**The field moved toward CQL's stated goal — and past its current weight.**
- Every heavyweight process framework shed ceremony or died: agent-os v3 deleted its own
  implementation/orchestration phases; BMAD survives via a Quick Flow bypass (task classes,
  in effect); Tessl pivoted away from spec-as-source; the canonical adoption story is
  OpenSpec's "a 3-command/250-line workflow gets used for everything, an 800-line one
  doesn't." Kiro-style spec-sync is the documented fatigue point.
- SkillsBench (arXiv 2602.12670): skills lift pass rates +16.2pp on average, but **software
  engineering shows the smallest gain (+4.5pp), and focused skills with ≤3 modules beat
  larger bundles**. The margin CQL plays in is real but thin — every token of process
  overhead is competing against a +4.5pp domain prior.
- Adoption post-mortems are unanimous on two points CQL should take personally: hooks beat
  prompt rules ("fire every time regardless of phrasing"), and **fake machinery kills trust
  permanently** (claude-flow's cosmetic swarm ops and fabricated metrics are the cautionary
  tale). CQL's candor discipline is its moat; every place a shipped claim overstates the
  enforced reality is a direct hit to the one asset that differentiates it.

**Verification-market datapoint worth stealing from:** OpenAI's production reviewer (Dec
2025; 100k+ external PRs/day, 52.7% of comments produce a code change) is built on
precision-over-recall, execution grounding, and separate contexts — not more prose. The
146-PR bot comparison (May 2026) shows the same: precision is what practitioners keep.

---

## Part 2 — Verified findings

### A. Coherence: places where CQL ships two truths (all reproduced)

**A1. Two canonical record paths, and the documented one structurally fails.** `init-record`
defaults to root `agent-record.json` (`quality_loop.py:2194`), and README/SKILL.md/
tool-contracts/the CI example all teach that path — but the attestation hash excludes only
`.quality-loop/` (`reality.py:148-161`), so on the documented path, writing the attested
review into the record *changes the hashed diff* and review-freshness fails from that moment
on. The path that works (`.quality-loop/agent-record.json`) is the one the docs never teach;
the CI example uses the one that cannot pass.

**A2. The guard denies the writes the lifecycle mandates.** With default-ON `protect_harness`,
Write/Edit on the record is denied — yet the lifecycle requires continuous record mutation and
no CLI subcommand updates a record. The honest agent is funneled to Bash heredocs, the exact
channel the deny message says must not be used. Worse: `stop_gate.py:205`'s printed remedy
(`git checkout -- .quality-loop/agent-record.json`) is itself matched by the guard's
DESTRUCTIVE regex (reproduced). And the repo has no `.claude/settings.json` — **the hooks and
the guard have never once run together during CQL's own development**; every dogfood record
was cleared without the deterministic layer actually installed.

**A3. Windows gets zero deterministic gates, silently.** All five claude-code hooks are wired
as literal `"command": "python3"` (`hosts/claude-code/settings.json`); `install.py` merges
that JSON verbatim (its own `_resolve_python` ladder serves only git-hook install). The
CHANGELOG claims the hardcoded-`python3` defect fixed — the fix landed in the shims, not the
launcher. npm-smoke's windows job runs only init/check, so the matrix stays green while the
whole deterministic layer no-ops.

**A4. The anti-drift pin drifted.** `EXPECTED_CONFIG_VERSION = "5.1.0"`
(`quality_loop.py:1220`) vs 6.0.1 in SKILL.md/package.json/CHANGELOG — through two releases,
unnoticed, because nothing in evals/ or CI reads the constant. The rejection message tells
users "the skill, config, CHANGELOG, and npm package share one version," which is currently
false; a user who sets 6.0.1 to match reality gets a hard failure.

**A5. Canonical lists are hand-copied and drifting into contract breaks.** The shipped
reviewer checklist instructs verdicts `approve | request changes | needs discussion` — spaced,
three values, no `reject` — while the schema and both reviewer agents require the underscored
four-value enum: a reviewer following the shipped instructions emits a verdict the gate
rejects. Philosophy still lists mission artifacts deleted releases ago; subagent files carry
mutated copies of the risk-boundary list directly under SKILL.md's "canonical" declaration.

**A6. The load-bearing heterogeneity check exists three times (~278 lines) and has already
diverged.** `_reviewer_heterogeneity` (enforcing), `heterogeneity_status` (display), and
`_families_heterogeneity` re-implement the same resolution; the display path applies
default-class fallbacks the enforcing path lacks, so `brief` can report "verified" for a
config the gate never evaluated.

### B. First contact and teardown (all reproduced end-to-end)

**B1. Both canonical demos fail on the word "checkout".** `detect_risk_floor("Fix checkout
retry bug")` → `('high', ['payments'])`. Running README's two-command demo verbatim in a
fresh repo yields **Overall: FAIL with 11 findings**, including a forced high-risk upgrade
and a security-review demand; the quickstart transcript shows a "medium risk" declaration the
shipped gates would reject. The one artifact that verifies green (`examples/walkthrough`)
exists but onboarding never presents it as the first command. A new user cannot distinguish
"the product is working" from "the product is broken."

**B2. Default-base resolution poisons day one.** The ladder tries only
origin/main→origin/master→main→master before the **empty tree**, so a `git init` solo repo or
any develop/trunk-default repo diffs the entire repository forever: 60 unmapped-file scope
errors, risk floors firing on pre-existing `auth/` files the agent never touched, and a
435KB reviewer prompt (~110k tokens) rendered for a one-line change — all reproduced. The
escapes exist (`--base` is documented) but `QUALITY_LOOP_BASE` appears in zero .md files and
config has no `base` key. Separately, the 59-file install stays in every canonical diff until
merged to origin/main, and **no printed next-step anywhere includes the `git add && git
commit` step** — training users into the `scripts/*` repo-map glob workaround that permanently
neuters scope integrity (the dogfood record itself used it).

**B3. No teardown, no team story.** The tracked record at `status=done` on main means: any
hook-installed clone gets `verify` re-executing all 11 committed `commands_run` strings via
`shell=True` at its first Stop, then a block whose printed remedies the guard denies
(nuance: achievable via Bash, and a bare clone without a CQL install carries no hooks — the
trap hits CQL-adopting teams, which is exactly the audience). In CI, `action.yml` hard-fails
any PR without a record once `.quality-loop/` exists (docs/dependabot PRs have no green
path), searches the root record path the stop gate doesn't prefer, ships an example pinned
to a stale tag, and is never dogfooded by this repo's own workflows — which is why none of
this was felt.

### C. Adaptability: the gates assume this repo's shape

**C1. Hard Rule 6 is silently inert outside Python/JS.** The test-weakening/shrinkage
lexicons miss `func TestX`/`t.Errorf`/`t.Skip` (Go), `#[test]`/`assert_eq!` (Rust — the macro
`!` defeats the regex), `@Test`/`@Disabled` (Java) — all reproduced returning zero findings
on gutted tests, while `enforcement-matrix.md` claims the rule unconditionally owned. No gate
reads the config: TEST_PATH_MARKERS, high-risk path lists, boundary keywords, and the base
ladder are all constants — a repo whose auth lives in `identity/` or tests in `evals/` cannot
adapt except by editing scripts the guard denies. CQL itself hits this: `evals/` misses
TEST_PATH_MARKERS, so its own releases ship on a `bugfix_test_waiver` — and `_has_waiver`
accepts **any truthy value**, no shape, no evidence.

**C2. The merge-base defense holds only against agents that don't write refs.** `git
update-ref refs/remotes/origin/main HEAD` is allowed by the guard, moves the resolved base,
and blinds every diff-derived gate (risk floor, secrets, scope, shrinkage) — reproduced. The
reflog records the move but no gate reads it. "Kills commit-first evasion" is a CI-anchored
guarantee being sold as a local one.

### D. Measurement: the standing contradiction, now with a cheap exit

**D1. The bench, as pre-registered, would measure judge noise.** In the one live run, all
four arms passed the anchor task's entire objective battery (npm tests, 0 deps, 5/5 hidden
behaviors) — every reported lift came from LLM judges whose same-packet spreads (0.25–3.75)
swallow the Codex delta (−1.11), with two verdict-level judge disagreements. PROTOCOL §4
requires the judges differ only from each other, not from the arm's model (the cited run had
same-family judging). §6.3 deletes components on nulls that the noise band guarantees. The
committed fixture itself shows n=3 RNG inverting hard-coded true strengths.

**D2. The cheapest real datum is six judge-free runs away.** philosophy.md still asserts the
15–22k token figure README admits is unmeasured. PROTOCOL §6.2 ({baseline, full} × Claude ×
3 seeds on a micro bugfix, tokens only, no judges, no blinding) is blocked solely by a
~30-line task spec §2 deliberately left uncommitted. Meanwhile outcome data already in git
has never been aggregated: per-release review findings (8/3/3/1), the fifth-round-catch
record, delegations.jsonl, rerun sidecars — a computable defect-escape rate for the loop's
own pipeline, sitting unread while the shipped `loop_metrics` reports compliance KPIs.

### Rejected majors (kept for the record)

- **"verify passes on `echo ok` + a self-attested review"** — mechanics confirmed by live
  repro, but SECURITY.md/README already document the self-attestation boundary; the charge of
  overclaiming failed. Surviving slivers: README:279's "fabricated pass rows no longer clear
  the local gate" should note that truthful-but-vacuous rows still do; ≥3 ACs sharing one
  proving command stays warn-only even at medium+.
- **"allowed-commands + shell=True at Stop is auto-RCE"** — mechanics confirmed, but this is
  SECURITY.md's documented "not a sandbox / same trust model as CI" boundary. Surviving
  slivers: reject a bare `*`/overbroad glob in `_command_allowed`; say explicitly that Stop
  *auto-executes* allowlisted strings.
- **"extract the control plane to a sibling repo"** — re-litigates a decision v6.0.0 settled;
  two of the three "dead limbs" are documented, eval-covered exports. Surviving sliver: the
  standalone `_main` is expired by its own shipped fold-and-delete note (the gate CLI now
  registers `--arm-costs`), and `docs/control-plane.md:146` states the opposite of reality.

---

## Part 3 — The plan

Guiding rules, in order: (1) one truth per thing — every fix below deletes a second truth
rather than adding a mechanism; (2) the loop must pass first contact on a repo that is not
this repo; (3) configuration is three keys, not a second program; (4) buy data at the lowest
price before any further gate spend. Waves 1–3 are net-negative-to-neutral in lines; Wave 4
is six runs and a memo.

### Wave 1 — One truth per thing (coherence; net-negative)

| # | Change | Core move |
|---|--------|-----------|
| 1.1 | **One record path** | `.quality-loop/agent-record.json` becomes the `init-record` default; README/SKILL/tool-contracts/action example all updated; root-path fallback in stop_gate/guard kept one deprecation release, then deleted. Kills A1 as a class. |
| 1.2 | **Guard coherence** | Remove the record (and keep `allowed-commands`) out of the Edit-deny set — integrity already comes from the layer that holds (freshness hash, verify recomputation, CI anchor); keep denies only for files agents never legitimately edit (gate scripts, hook wiring, config). Stop-gate remedy becomes `git restore --source=HEAD --`. Deny message rewritten to claim only what is enforced. Add the bare-`*` allowlist rejection (rejected-major sliver). |
| 1.3 | **Version pin tells the truth** | Rename to `CONFIG_SCHEMA_VERSION` (the schema didn't change in 6.0.x — it is one), delete the "share one version" parenthetical, add one eval case comparing the pin against package.json so it can never drift silently again. |
| 1.4 | **De-drift the canonical lists by deletion** | Paste the 4-value verdict enum verbatim into reviewer-checklists.md; replace copied lists in `.claude/agents/*.md` with pointers to SKILL.md; fix philosophy's artifact list to the four that ship; drop the unchecked duplicate `validation_contract.acceptance_criteria`; extend the existing candor lint to verbatim-diff the canonical lists it currently only counts. |
| 1.5 | **One heterogeneity resolver** | Single resolver in `quality_loop_routing` returning structured results (resolved ids, families, skip reasons); check-config renders errors, brief renders status. Deletes ~120–150 lines and the display/enforce divergence. |
| 1.6 | **Small deletions** | Fold the control module's expired `_main`; fix `docs/control-plane.md:146`; merge the byte-identical `_is_scaffolding_*` predicates; single-source the 4-site next-steps block. |

### Wave 2 — Survive first contact (ease of use)

| # | Change | Core move |
|---|--------|-----------|
| 2.1 | **A green hello-world** | Quickstart's first runnable command becomes the walkthrough green path (`verify-gates examples/walkthrough/agent-record.json` → exit 0, ~10 seconds). The README demo goal changes to non-boundary wording ("Fix invoice total rounding") **or** keeps "checkout" and prints the expected FAIL as the demo's explicit punchline — never an unexplained 11-error wall. |
| 2.2 | **Day-one base sanity** | One config key `base` seeding the existing ladder; when no `origin/*` exists, default the *local* base to HEAD with a one-line warning (commit-first evasion is CI's job, per the repo's own doctrine) and keep the empty-tree fallback only under `--require-terminal`; document `QUALITY_LOOP_BASE`; add `git add -A && git commit` as step 0 of every printed next-steps block; treat install-manifest-listed, byte-identical paths as scaffolding in diff gates (reuses the manifest that already ships). |
| 2.3 | **Teardown + team story** | One predicate: at Stop, a record unchanged versus the merge-base (nothing locally in flight) is **closed** — allow the stop, skip re-execution; phantom-completion stays CI's job. Document teardown as the already-half-practiced convention: PACKAGE archives the record to `docs/records/` and removes the live file. `action.yml`: align record search with the stop gate's, soften the no-record branch to diff-audit + loud warning, dogfood the action in this repo's CI, release process bumps the example pin. |
| 2.4 | **Windows actually gets gates** | Installer writes the resolved absolute interpreter into hook JSON (the `_resolve_python` ladder already exists, applied at the layer that was missed); one hook-fires smoke case in npm-smoke on all three OSes. Codex install into a non-git target warns at install time. |
| 2.5 | **Dogfood the deterministic layer** | Commit `.claude/settings.json` wiring the hooks in this repo, so the next release is the first developed with the Stop gate and guard actually firing. Cheapest possible end-to-end test of the entire layer — and it would have caught A2, B1, and B3 before shipping. |

### Wave 3 — Adapt without a second program (adaptability + honest claims)

| # | Change | Core move |
|---|--------|-----------|
| 3.1 | **Multi-language test lexicon** | One line per family in the two existing regex tables (`func Test\w+`, `t.Skip/t.Errorf/t.Fatalf`, `#[test]`, `assert_eq!/assert!`, `@Test/@Disabled`, RSpec `it/expect`); a language-coverage candor sentence in enforcement-matrix.md for what stays uncovered. Un-inerts Hard Rule 6 for the majority of real repos. |
| 3.2 | **Exactly three gate config keys** | `base` (2.2), `tests` (path markers), `high_risk_paths` — read by the existing constants' consumers, with an explicit doc sentence that everything else is deliberately not configurable. Fixes CQL's own `evals/`-miss so its releases stop shipping on a waiver. |
| 3.3 | **Waivers cite evidence** | `_has_waiver` requires the waiver to name a pass-labeled `commands_run` cmd (the pattern escalations already obey). Free text stops disarming a gate. |
| 3.4 | **Claim-sharpening pass (pure wording)** | Merge-base defense: local guarantee vs CI anchor stated plainly (C2); "fabricated pass rows" sentence gains the vacuous-rows caveat; Stop's auto-execution of allowlisted commands stated explicitly; the two unowned SKILL.md imperatives (pre-attestation right-size re-run, product floor) get enforcement-matrix rows marked *advisory*. |
| 3.5 | **Generality filter at RETROSPECT** | The n=1 ts-search rules baked into reviewer-checklists.md ("reject linear-scan-per-term…") move to a lessons entry; the checklist keeps only rules that generalize. One sentence added to RETROSPECT: a lesson ships in the checklist only after recurring across ≥2 tasks. |

### Wave 4 — Buy the first datum at the lowest price (measurement)

| # | Change | Core move |
|---|--------|-----------|
| 4.1 | **Amend PROTOCOL before running (~10 lines)** | Anchor task's hidden suite must fail the committed baseline run (objective discriminating power) or the headline switches to bugfix tasks with committed failing held-out tests; judges must be cross-family *from the arm's model*; add a minimum-detectable-effect note; §6.3 deletion requires the null on objective metrics — judge-delta nulls downgrade to "unproven," never auto-delete. |
| 4.2 | **Run §6.2 now** | Commit the ~30-line micro-task spec and run the six judge-free token-only runs ({baseline, full} × Claude × 3 seeds). Either outcome is a win: a measured overhead figure replaces the philosophy.md estimate, or the >1.5× rule fires and the always-loaded ladder text becomes the pre-registered cut candidate. This is the entire "every gate must earn its tokens" promise, exercised for the price of an afternoon. |
| 4.3 | **Aggregate the outcome data already in git** | One memo: per-release review yield (% findings → diff change) and post-ship escapes, computed from `docs/records/*.json` + CHANGELOG — including the strongest datum the repo owns (rounds 1–4 missed what round 5 caught; v6.0.0 tagged failing its own verify). Next dogfood cycle runs with the control plane on; the measured token figure replaces the estimate. |
| 4.4 | **Retire the theater** | Delete the trigger suite that "structurally cannot fail" (its own docstring's words) or replace with an honest judge-path smoke; move the ~1.6MB of dated eval archives out of `examples/` (to `archive/` or a release asset) so examples/ is host recipes again. |

### What this plan does *not* do

No record-signing or sandboxing (documented out-of-scope; SECURITY.md's trust model stands).
No control-plane extraction (settled in v6.0.0; only the expired `_main` goes). No new review
rounds (the literature says they make verification worse). No config surface beyond three
keys. No gate additions anywhere — Wave 4 exists to decide *deletions*, and 4.1 ensures the
bench cannot be gamed into deleting things by noise.

---

## The one-paragraph version

v6.0 made the trust chain honest; this cycle makes it true outside its home repo. The
confirmed findings are not new gate holes — they are places where CQL ships two truths (two
record paths, a drifted version pin, a checklist that contradicts its schema, three copies of
one check) or assumes its own shape (its default branch, its OS, its languages, its
one-agent-one-repo life, its own demo tripping its own risk floor). The plan is therefore
deletion-shaped: one record path, one resolver, one truth per claim, three config keys, a
green hello-world, a teardown predicate, hooks finally dogfooded in-tree — and then the six
cheapest runs in the protocol to finally put a measured number under the sentence the whole
project leads with.
