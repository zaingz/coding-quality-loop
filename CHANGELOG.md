# Changelog

## 6.5.0

The activation release: the routed topology the repo has shipped since v5.0.0
is now switched on for its own development, the persistent-worker (sidekick)
pattern gets first-class guidance and honest ledger semantics, and the
control plane stops misreporting the two workflows that pattern creates.
Suites: 19 static + 63 behavioral + 32 memory + 51 reality + 30 routing +
56 hook = **251 core gate cases** (+40 control add-on).

- **Dogfood routing activated.** `quality-loop.config.json` graduates from
  the gate-config-only shape to the full orchestration config consumers run,
  carrying the `max-intelligence` variant (`assets/routing/`): Sonnet 5
  context mapper (`effort: low`), Fable 5 planner (`effort: high`), Fable 5
  main-session implementer (declared), GPT-5.6 Sol cross-family review via
  Codex — `check-config` now enforces reviewer heterogeneity on this repo
  (`verified (claude vs gpt)`), and CI validates the dogfood config alongside
  the example. The two file-host agent frontmatters are committed with their
  pins; the installer **neutralizes agent `model:`/`effort:` pins on copy**
  (`copy_agent_neutral`) and `prepack` neutralizes the vendored tarball
  copies the same way (npm test pins the packed artifact), so the pins never
  exist at rest anywhere consumers receive them. New behavioral gate:
  release surfaces share one version (npm == SKILL == README badge ==
  shipped GitHub example ref) — version drift is a repeated mistake, now a
  gate. The dogfood `$schema` pointer resolves from the repo root.
- **Persistent workers (sidekicks), honestly accounted.** SKILL.md
  §Orchestrator Layer and `references/agentic-orchestration.md` §Persistent
  workers: an implementer worker may persist across fix rounds of one slice
  (follow-ups return to its cached session at cache-read rates); reviewers
  never persist; escalation ends persistence; one ledger row per round with
  the same `session_id`. The control plane's delegation join now treats
  later rows naming a claimed session as `follow_up` rounds — linked for the
  audit trail, carrying no token figures, so a session's tokens are
  attributed exactly once (replaces the `duplicate_session_id` unmatched
  flag; `task_timeline` lists a persistent worker's session once). Rounds
  follow **numeric** ledger order — lexicographic artifact-key order put row
  #10 before #9, handing the token-carrying first claim to the wrong round
  (pinned at eleven rounds).
- **Worktree sessions attribute to the repo.** All three adapters (claude
  transcript, codex rollout, droid wrapper) now accept sessions whose cwd is
  a linked git worktree of the repo **or any subdirectory of one** —
  `repo_roots()` resolves `git worktree list --porcelain` (refreshed every
  index pass, symlink-tolerant on both sides, degrades to `[root]` without
  git; `git_capture` grows an optional `timeout`), the codex adapter moves
  from exact-root matching to descendant containment, and a roots-change
  resets codex rollout offsets so a rollout consumed as foreign before its
  worktree was linked is resurrected on the next pass. Prefix-slug decoys
  keep failing the per-file cwd check. The mission topology's
  isolated-worktree workers were previously invisible to the per-repo index.
- **Spend per accepted completion record.** `loop_metrics` (and the
  dashboard Metrics view) expose the routing doctrine metric — per accepted
  record (every review verdict approving), the delegation-linked session
  tokens (input/output/cache read/cache write) and priced spend; rejected
  records excluded, live/archive twins canonicalized with **archives winning
  in both directions** (the review-yield twin rule), follow-up rows never
  double-counted. A query, never a gate. The count lint additionally checks
  the add-on suite's own table row, and historical CHANGELOG entries are now
  checked for internal arithmetic consistency (their addends must sum to
  their own stated total) — history is verified, never rewritten.
- **Post-ship outcomes recorded** for v6.3.0 (`regressed` — the teardown
  Stop-gate escape v6.3.1 fixed) and v6.4.0 (`clean` — 24h field window).

## 6.4.0

Subtraction pass: net-negative cleanup — dead surface deleted, duplicate
implementations collapsed, docs realigned with the code. No behavior change
except the deletions themselves. Suites: 19 static + 62 behavioral +
32 memory + 51 reality + 30 routing + 55 hook = **249 core gate cases**
(+37 control add-on).

- **Dead surface removed.** `brief`'s "Last run" section read
  `.quality-loop/runs/` journals whose writer was archived in v3.0 — a
  reader with no writer for four major versions; `STRONG_REASONING_STEPS`
  carried an `ORCHESTRATE` entry no valid config can reach (the step enum
  rejects it first); `bench/metrics.py` shipped a CLI entry point nothing
  invoked; the npm package carried a dead `step` helper, an orphaned
  `smoke` script, and two exports nothing imported; `install.py` had a
  condition argparse guarantees false and a one-caller quoting wrapper.
- **One copy per concept.** `stop_gate.py` and `sessionstart_context.py`
  import hooklib's `json_input`/`project_root` instead of private copies —
  sessionstart's had drifted (no OSError guard: a missing git binary
  crashed the SessionStart hook); `run_evals.py`'s four verbatim
  git-repo-init blocks collapsed into one helper; static case 01 deleted
  (expect-identical to case 05, which pins the same surface).
- **Docs match the code again.** `docs/architecture.md` no longer claims
  `protect_harness` denies record edits (the guard deliberately does not)
  and its invented record example is now a pointer to the real walkthrough
  record; the config schema gains the two real root keys it omitted
  (`protect_harness`, `enforcement`) and the example config drops the
  retired v3–v4 advisor block; `docs/control-plane.md`'s stale add-on
  count is fixed and the file joins the doc-count lint's watch list;
  `references/tool-contracts.md`'s executable-evidence list gains the
  missing `lint` class; the orphaned memory-hooks example and the
  never-displayed terminal-demo poster are deleted.
- **CI newly runs the npm package's 33 unit/integration tests**
  (previously executed by no workflow) — the one addition in the pass.

## 6.3.1

- **Stop gate: committed PACKAGE teardown closes freely.** SKILL.md's teardown
  archives the record and removes the live file, but the gate's missing-record
  predicate flagged exactly that state as "deleted mid-loop" — releases were
  forced to leave the live record behind (the source of the review-yield
  double-count fixed in 6.3.0). The record's absence now closes the stop when
  git affirmatively shows HEAD without the record path AND a clean tree; any
  dirt or git failure keeps the block (fail-closed). Found live at the first
  post-teardown stop after v6.3.0. Suites: 20 static + 63 behavioral +
  32 memory + 51 reality + 30 routing + 55 hook = **251 core gate cases**
  (+37 control add-on).
- **Outcome ledger anchored at the repo root** (landed on main post-6.3.0,
  rides this release): `record outcome` on an archived record nested a stray
  `docs/records/.quality-loop/` ledger that `brief` never read; the ledger now
  resolves via git toplevel with a record-adjacent fallback outside git.

## 6.3.0

The measured release. Three versions in a row shipped measurement
*infrastructure*; this one ships **measurements** — the first live,
pre-registered benchmark numbers in the repo's history — plus the integrity
fixes an outside auditor found in a day of poking, so the numbers the repo
already publishes are self-consistent. Suites: 20 static + 63 behavioral +
32 memory + 51 reality + 30 routing + 54 hook = **250 core gate cases**
(+37 control add-on).

### The first live §6.2 numbers (and the outcome honestly not claimed)

- **`bench/results/micro-bugfix-live-2026-07-21.json`** — six live cells,
  {baseline, full} × claude-code × 3 seeds, on the committed micro-task
  (`bench/tasks/14-micro-bugfix.json`), run under the pre-registered protocol
  with pristine v6.2.0 drop-ins and validated cost/provenance
  (`bench/runner.py --validate` gates it in CI like every committed results
  file). Every cell was objectively perfect: committed test green, 3/3 hidden
  cases, ≤28 LOC, zero new dependencies — in both arms.
- **The §6.2 threshold was exceeded ~5-fold — and the pre-registered outcome
  is deliberately NOT claimed.** Median full/baseline ratios: **8.1× output
  tokens, 6.3× input tokens, 7.65× cost, ~10× wall time**, far past the 1.5×
  threshold. But §6.0's letter ("before any §6 rule may fire… if every arm
  passes the entire objective battery… no §6 outcome may be claimed") binds
  the run: every arm passed everything. The cross-family reviewer caught the
  conflict, and the release honors the pre-registration as written — the
  results file records `fires: false` with the reasoning verbatim. The
  always-loaded ladder/class text becomes a cut candidate as an **ordinary
  operator decision informed by the data**, not a fired rule; a dated
  amendment scopes §6.0 to the quality-delta rules for **future runs only**.
  Quality was identical across arms on this cell's objective battery — so on
  this micro-task, the full path bought no measured quality and cost 6–8×,
  which is what "ceremony scales with risk" predicts for tiny tasks.
- **Field truth recorded, not hidden.** The results file records what the three
  full arms actually did: the pristine gate failed all three finished records,
  all three "independent reviews" were same-family Claude subagents with
  `ran_checks: false` (cross-family review is structurally unavailable in a
  single-CLI drop-in), and risk tiering for the same billing task was
  inconsistent (low ×1, medium ×2). These are now tracked observations with
  the data to act on them, not anecdotes.
- **Protocol recipe rot fixed.** The committed isolation recipe cited
  `--safe-mode`, which no longer exists in claude CLI ≥2.x. `PROTOCOL.md` §4/§5
  and the task spec now carry the working recipe
  (`--setting-sources project --permission-mode acceptEdits --output-format
  json`) and an exact usage→cost-field mapping (cache split recorded as
  `tokens_in_*` components). A dated Amendments note marks the change; the §6
  decision rules are byte-for-byte untouched.
- **`bench/runner.py --materialize`** — writes a task workspace from the spec
  (seed files, git init/commits, pristine drop-in for full arms) and prints the
  exact per-arm claude command plus the scoring checklist. The §6.2 cell went
  from "hand-assemble everything" to two commands per cell.

### Measurement integrity: the published numbers are now self-consistent

- **`--review-yield` no longer double-counts the latest release.** The live
  record and its archived twin used to both produce rows (the v6.2.0 release
  appeared twice on the feature's first real invocation). Archives win now;
  an eval case pins it.
- **Every archived record passes `check-record`, forever.** The
  v6.1.0 archive carried two unrecognized `commands_run[].class` values and a
  malformed `models_used` — repaired, and a new behavioral lint fails the suite
  if any `docs/records/*.json` ever regresses.
- **Void numbers say so where they appear.** The README's webapp judge-lift
  figures were declared void by `bench/PROTOCOL.md` §4 (judge-family
  independence violated) while the README still quoted them as headline
  results. The table now carries the void annotation inline; the objective
  browser checks stand.
- **The cost paragraph cites measurements.** "Estimated 15,000–22,000 tokens"
  is replaced by the measured §6.2 medians above, with the estimate retired.

### Defaults that match the claims

- **`check-config` understands the gate-config shape.** The three-key
  gate-config (`base` / `tests.path_markers` / `high_risk_paths`, the shape
  this repo's own root config uses) now validates and exits 0 with an explicit
  "orchestration checks skipped" note instead of failing on missing `profiles`.
  Malformed gate-configs still fail; full configs are unchanged.
- **Dormant heterogeneity is loud.** When reviewer-heterogeneity enforcement
  cannot resolve (no `model_routing.host` — the out-of-box state), `brief` and
  the `verify` umbrella now print one prominent NOT-ENFORCED line naming the
  fix. The flagship guarantee can still be off, but it can no longer be
  silently off.
- **Onboarding points at the CI anchor.** The installer's printed next steps
  (npm CLI and `install.py`) now include wiring the GitHub Action — because
  merge-base anti-evasion and helper integrity are CI-anchored guarantees, and
  a default install previously never mentioned the layer the guarantees lean
  on — and tell the user to set `model_routing.host` so cross-family review
  enforcement activates.
- **The outcome loop is in the lifecycle.** SKILL.md's PACKAGE step now names
  `record outcome <clean|regressed|reverted>` so the ledger shipped in v6.2.0
  actually accrues data.


## 6.2.0

The prove-it, smooth-it, learn-from-it release. v6.1.0 made the trust chain
true in the field; v6.2.0 closes the loop around it in three stages —
**measure** the yield, **remove** the friction that stops agents using the
loop honestly, and **learn** from what shipped. Nothing here is a new gate: the
blocking surface is unchanged. Suites: 20 static + 61 behavioral + 32 memory +
50 reality + 30 routing + 54 hook = **247 core gate cases** (+36 control
add-on).

### Measurement: what is the loop actually catching?

- **Review yield in one query.** `control-report --review-yield` reads the live
  record + `docs/records/*.json` straight from disk (never the index) and prints
  a per-record table: how many findings each review channel raised
  (`independent_review` / `security_review`), how many `review_findings[]`
  entries carry a non-empty `resolution` (the finding→fix proxy), and the
  recorded `outcome` verdict. It is a query, never a gate — the first honest
  answer to "is the review step earning its cost?"
- **A benchmark is one command away.** Between `--review-yield` (finding→fix→
  outcome yield) and the existing `--arm-costs` (per-session tokens/duration for
  a bench arm), the measurement a real pilot needs is now a single CLI call, not
  a hand-copy from a dashboard.

### Friction: make the honest path the easy path

- **A structured `record` CLI.** `record set-status`, `record add-evidence`,
  `record add-ac`, and `record outcome` each do an atomic, schema-validated
  write that preserves unknown fields. The agent advances the lifecycle without
  hand-editing JSON or shelling a heredoc; malformed input exits non-zero with a
  clear message, never a traceback. The record stays deliberately **outside**
  the edit-deny set — structured writes are the sanctioned path, not a new
  restriction.
- **A smart Stop gate.** When the `verify` umbrella passes it writes
  `.quality-loop/last-verified.json` (`diff_sha256`, `record_sha256`, `base`,
  `status`, `verified_at`). On the next terminal Stop, if that marker's canonical
  diff hash (the same one attest-review and review-freshness use), the record
  content hash, and status all still match, the umbrella is skipped with a
  one-line stderr note instead of re-executing every recorded command. It is a
  latency optimization that fails safe: any mismatch, missing/unreadable marker,
  or hashing failure runs the full umbrella exactly as before. The
  `record_sha256` is load-bearing — the umbrella verdict depends on the record,
  which lives under `.quality-loop/` (excluded from the canonical *diff*), so a
  post-verify `record add-evidence` correctly re-runs the umbrella rather than
  riding a stale skip (caught by this release's own cross-family review). Scope,
  honestly: the marker skips re-execution only when nothing changed since a
  passing verify; it is a plain file, so like every local gate input it is
  tamper-evident, not a boundary against a forging agent (which could rewrite
  the record it attests anyway). CI never reads the marker and re-executes
  unconditionally.
- **Eval counts are derived, not hand-bumped.** The canonical gate-case total is
  computed at runtime from each suite's `len(CASES)` + the static `cases/*.json`
  count (control add-on the same way), and the doc-count lint checks every
  public doc against the computed value — so a suite can grow without a stale
  literal drifting out from under the badges.

### Learning: feed the outcome back

- **Outcome feedback.** `record outcome <clean|regressed|reverted>` sets an
  optional `outcome` object on the record **and** appends one line to
  `.quality-loop/outcomes.jsonl`; the next session's `brief` tallies it
  (`outcomes (this repo): N recorded — X clean, Y regressed, Z reverted`). The
  `outcome` field is optional in the schema — absence is valid and no gate
  requires it — so post-merge truth can flow back into the loop without becoming
  another thing that blocks.

**Not done here (operator action).** This release makes the six planned §6.2
measurement runs *possible* with one command each; it does **not** run them. The
numbers a real pilot would produce — review yield, escalation rate, cost per
shipped change, regression rate — remain unmeasured until an operator executes
those runs against their own repo. CQL still ships zero field data by doctrine.

## 6.1.0

The field-truth release. A same-day second review round (50 fresh-context
agents: 6 subsystem maps, 5 research sweeps over 2025–26 primary sources, 6
adversarial critics, and two independent verification lenses per finding — 13
of 16 majors dual-confirmed; plan:
`docs/improvement-plan-v6.0.1-2026-07-20.md`) found that v6.0 made the trust
chain honest in design but not yet true in the field: the gates failed exactly
where a real repo differs from this one — record path, default branch, OS,
language, team size, day one. v6.1.0 fixes those boundaries and unblocks the
first real measurement. Suites: 20 static + 55 behavioral + 32 memory + 48
reality + 30 routing + 49 hook = **234 core gate cases** (+35 control add-on).

### One truth per thing

- **One canonical record path.** `init-record` now defaults to
  `.quality-loop/agent-record.json`. The documented root-path default
  structurally failed review freshness: the attestation hash excludes only
  `.quality-loop/`, so on the root path, writing the attested review into the
  record changed the hashed diff and the freshness gate fired from that moment
  on. Docs, action.yml, and templates all teach the one true path; the root
  fallback remains readable for one deprecation release.
- **The config version pin tells the truth.** `EXPECTED_CONFIG_VERSION` had
  silently drifted (5.1.0 vs a 6.0.1 release) while its error message claimed
  drift was impossible. Renamed to `CONFIG_SCHEMA_VERSION` (schema lineage,
  which last changed in 5.1.0 — existing configs stay valid), the false
  "share one version" parenthetical deleted, and an eval now pins constant ==
  schema `const` == example config so a silent three-way drift cannot recur.
- **One heterogeneity resolver.** The load-bearing cross-family check existed
  three times (~278 lines) and the display path had already diverged from the
  enforcing path (`brief` applied default-class fallbacks enforcement bails
  on, so it could report "verified" for configs the gate never evaluated).
  One resolver now feeds both; display shows SKIPPED where enforcement skips.
- **Canonical lists de-drifted by deletion.** The shipped reviewer checklist
  instructed a stale three-value spaced verdict list the schema rejects — now
  the exact 4-value enum. Subagent files point at SKILL.md instead of carrying
  mutated copies; philosophy's artifact list matches the four that ship; the
  unchecked duplicate `validation_contract.acceptance_criteria` is gone (gates
  read the top-level list only).

### First contact

- **A green hello-world.** Onboarding leads with the ~10-second green
  walkthrough (`verify-gates examples/walkthrough/agent-record.json`, exit 0).
  Both canonical demos used the goal "Fix checkout retry bug" — and "checkout"
  is a payments boundary keyword, so the documented first touch of `verify`
  was an 11-finding FAIL wall with no explanation. Demo goals are now
  boundary-free and show expected output.
- **Day-one base sanity.** In a repo with no `origin/*` (fresh `git init`,
  develop/trunk defaults), the base ladder fell through to the empty tree:
  the entire repository in every diff, scope-integrity walls, risk floors
  firing on pre-existing files, and a ~110k-token reviewer prompt for a
  one-line change. Now: a no-origin repo diffs against the best *local*
  baseline — the merge-base with a local `main`/`master` when the branch has
  diverged from it (so a feature branch's committed work stays visible), else
  HEAD when nothing distinct resolves — with an advisory note, never the whole
  repository. Commit-first evasion stays gated in CI, where `--require-terminal`
  keeps the empty-tree anchor. Base precedence: `--base` > `QUALITY_LOOP_BASE`
  > config `base` > auto ladder. Install-manifest paths count as scaffolding
  (filtered to CQL's own shipped path shapes, so a doctored manifest cannot
  exempt a consumer's source files), and every printed next-steps block starts
  with the missing `git add -A && git commit` step.
- **A teardown and a team story.** A committed terminal record used to block
  every hook-installed clone at every Stop — after re-executing all committed
  `commands_run` strings on the teammate's machine. A record byte-identical
  to its content at the resolved base ref is now CLOSED: the Stop is allowed,
  nothing re-executes. Closure requires an explicit base (`QUALITY_LOOP_BASE`
  or the config `base` key) or an `origin/*` ref — never a local branch, so a
  solo no-origin repo still runs the full gate (found by this release's own
  fresh-context review).
  PACKAGE's documented teardown: archive the record to
  `docs/records/vX.Y.Z-agent-record.json` and remove the live file.
  `action.yml` searches the canonical record path first and record-less PRs
  get diff-audit + a loud warning instead of a hard fail (docs/dependabot PRs
  have a green path); the action is now dogfooded in this repo's CI.
- **The deterministic layer is finally dogfooded in-tree.** The repo had
  `.claude/agents/` but no `.claude/settings.json` — the Stop gate and guard,
  the product's centerpiece, had never once fired during CQL's own
  development (every prior dogfood record was cleared without them). The
  hooks are now committed and live in this repo. One honest carve-out:
  `protect_harness` is `false` here only, because this repo's gate scripts
  are the workpiece under edit; the always-on destructive-command layer
  still applies and consumer installs keep the default.
- **Windows actually gets gates.** The hook JSON shipped literal `python3` at
  the launcher layer — the exact defect the v6.0.0 notes claimed fixed (the
  fix had landed only inside the shims). `install.py` now writes the resolved
  absolute interpreter at install time **only where `python3` is absent from
  PATH** (the Windows/minimal-image case); where `python3` exists the portable
  literal is kept, because hook settings are often committed and shared and a
  machine-specific path would silently disable the gates on every other clone
  (re-run install per machine if interpreters differ). npm-smoke executes the
  wired Stop-hook command on all three OSes, so this class can never ship
  silently again. Codex installs into non-git targets warn at install time.

### Adaptability, honestly scoped

- **The test lexicons cover more than this repo's languages.** Hard Rule 6's
  weakening/shrinkage gates were silently inert in Go, Rust, Java, Ruby, and
  C# (the Rust `assert_eq!` macro's `!` defeated the old regex; deleted Go
  test funcs counted zero). One line per family fixed it; the
  enforcement-matrix states exactly which languages are deterministic.
- **Exactly three gate-config keys.** `base`, `tests.path_markers`,
  `high_risk_paths` — additive extensions of the built-in constants, schema
  documented as the complete deliberate gate-config surface. CQL's own
  `evals/cases/` now counts as test paths, so case-pinned releases stop
  shipping on a `bugfix_test_waiver` (deliberately not `evals/` wholesale —
  the runners embed weakening-marker fixture strings to test the detector,
  and marking them as tests made the gate flag its own fixtures; found by
  dogfooding this release).
- **Waivers cite evidence.** `bugfix_test_waiver` accepted any truthy value;
  a waiver now disarms its gate only when it names a pass-labeled recorded
  command (blocking at medium+).
- **Allowlist hygiene.** A line in `.quality-loop/allowed-commands` consisting
  only of `*`/`?` wildcards authorizes nothing and is warned about by line.
- **The guard and the lifecycle stopped contradicting each other.** The
  PreToolUse guard denied Write/Edit on the very record the lifecycle
  requires mutating continuously (honest agents were funneled into Bash
  heredocs — the documented tamper channel), and the Stop gate's printed
  recovery command was itself matched by the guard's destructive-command
  regex. The record is now deliberately unprotected (its integrity comes from
  the freshness hash, verify recomputation, and CI — the deny message says
  exactly this), and the remedy is `git restore --source=HEAD`.
- **Claims sharpened to what is enforced.** README/SECURITY now state plainly:
  the merge-base anti-evasion guarantee is CI-anchored (a local agent that
  rewrites refs can move the base; no gate reads the reflog); truthful-but-
  vacuous evidence rows still clear the local gate (≥3 ACs sharing one
  proving command is warn-only); a terminal Stop auto-executes allowlisted
  recorded commands via a shell. Two previously unowned SKILL.md imperatives
  (pre-attestation right-size re-run, product floor) now have advisory rows
  in the enforcement matrix. Reviewer-checklist rules from a single 2026-07-07
  eval were removed; a lesson is promoted into a shipped checklist only after
  recurring across ≥2 distinct tasks.

### Measurement, unblocked

- **The protocol was amended before any run could game it.** New
  discriminating-power precondition (in the one live run, all four arms
  passed the anchor task's entire objective battery — every reported lift was
  judge noise); judges must be cross-family from the arm's own model; a
  minimum-detectable-effect note (same-packet judge spread 0.25–3.75 is the
  noise floor); §6.3 deletion requires an objective-metric null — judge-only
  nulls downgrade to "unproven", never auto-delete.
- **The §6.2 micro-task spec is committed** at
  `bench/tasks/14-micro-bugfix.json` (verified: committed test red on the
  buggy module, hidden cases wrong, reference fix turns all green). The
  deliberate-omission design ("spec written by whoever executes the cell")
  failed its purpose — §6.2 sat unrun for three releases. Six judge-free
  token-only runs now stand between the project and its first measured
  overhead figure.
- **Theater deleted.** The 10-case trigger smoke fixture — whose own docstring
  admitted its default grader "structurally cannot fail" — is gone. ~1.6 MB of
  dated eval-run archives moved from `examples/` (which is host recipes again)
  to `archive/eval-runs/`. The expired duplicate `_main` entry point noted for
  deletion inside the control-plane module was folded; its docs no longer
  claim the gate CLI lacks flags it registers.
- **First outcome data aggregated from the repo's own history:**
  `docs/review-yield-2026-07-20.md` computes per-release review yield and
  post-ship escapes from `docs/records/*.json` + this changelog — including
  the two strongest data points the repo owns (review rounds 1–4 missed two
  majors a fifth xhigh pass caught; v6.0.0 was tagged failing its own
  verify).

### Residual limits (documented, unchanged)

Tamper-evidence is still not immutability (Bash writes bypass the Edit-tool
guard); `ran_checks` still warns rather than fails; reviewer identity is still
a string comparison, not provenance; `run-evidence` is still not a sandbox
(SECURITY.md's trust model stands). The §6.2 six-run cell and the Wave 4.3
ablation remain the next milestones — the spec is now committed, so the only
remaining input is an afternoon.

## 6.0.1

Patch release closing two trust-chain holes a fifth review pass (Fable 5, xhigh)
found in the shipped v6.0.0 — the higher-effort pass caught what four earlier
rounds did not.

- **Review freshness now treats an empty current diff as N/A, not stale.** On
  the v6.0.0 merge commit `origin/main == HEAD`, so the diff was empty and the
  freshness gate misread the honestly-attested review as stale — the shipped tag
  failed its own `verify` on a fresh clone. An empty diff means there is nothing
  under review against the current base (the reviewed work is now the base);
  the terminal-status phantom gate still covers "done with nothing shipped".
- **`security_review` freshness is now validated too.** The freshness gate only
  recomputed `independent_review.diff_sha256`, so a security approval survived
  arbitrary later code changes at the highest-risk tier — the exact hole the
  gate exists to close. Both reviews are now bound to the diff.
- **Codex Stop hook timeout raised 30s → 600s** to match Claude Code — the v6
  terminal Stop runs the `verify` umbrella (up to 120s per evidence command),
  which the 30s budget could not complete.
- **A configured repo with no task no longer blocks every Stop.** The installer
  steers users into creating `quality-loop.config.json`; the stop gate treated
  its mere presence as "a task is in flight". It now requires real task state
  (run/progress/memory artifacts or a git tombstone of a deleted record), fixing
  the first-contact trap while still catching a record deleted mid-loop.
- Malformed-input hardening: `check-config` on a non-dict `steps` entry and
  `detect_risk_floor` on a scalar `plan` now degrade to a clear finding instead
  of a traceback (both already failed closed).
- `render-prompt` pipes the true diff (including untracked file contents,
  unredacted) to the reviewer CLI — a reviewer must see what shipped; documented
  here as a deliberate exception to the redact-everywhere rule.

Eval floor: **219 core gate cases** (+2 reality: empty-diff freshness N/A,
security-review freshness; +1 hook: config-without-task allows). The doc-count
lint gained badge (`%20`) and total-row table-cell coverage.

## 6.0.0

The trust-chain release. Executed against the 2026-07-20 deep review
(`docs/improvement-plan-2026-07-20.md`, waves 1–3 plus 4.1/4.2): make the
existing promises mechanically true, fix first contact, shrink to what gates
actually read, and pre-register the measurement that decides the rest. Net
effect: the enforced local path re-executes evidence, the installer can
uninstall itself, the medium paper trail halved, the control plane became an
opt-in add-on, and the eval floor grew to **216 gate cases** across the six
core suites plus **35 add-on cases** for the control plane.

**Breaking changes:**

- At medium+ risk (task_class medium/mission, risk_tier medium/high, or
  security_sensitive), every `acceptance_criteria` entry must be an object
  `{"criterion", "proving_command"}` whose proving command matches a
  pass-labeled `commands_run` entry. Bare string ACs now block (they stay valid
  at low risk).
- The reviewer verdict enum is pinned to
  `approve | request_changes | needs_discussion | reject` in the schema and all
  reviewer surfaces (was 9 tolerated variants); reviews also carry
  `ran_checks: true|false`.
- `verify` / `verify-gates` `--base` now defaults to the **merge-base with
  origin/main** (ladder: origin/main → origin/master → main → master; empty
  tree as last resort) instead of `HEAD` — committed-but-unpushed work stays in
  the diff. Explicit `--base` always wins; `diff-audit` and `run-evidence` keep
  their `HEAD` default, and `attest-review` now auto-resolves the same base as
  `verify` (so a committed-branch attestation is not permanently stale).
- The control plane is **no longer installed by default** and is excluded from
  the npm tarball. Opt in from a repo checkout with
  `python3 scripts/install.py --with-control-plane`. `control-*` subcommands are
  registered only when the add-on module is present.
- `memory-recall` no longer bumps hit counters (read-only by default; the
  working tree stays byte-identical). Hit-bumping is opt-in via `--bump` at
  RETROSPECT; `--no-bump` still parses but is a deprecated no-op.
- Deleted templates: `task-contract-template.md` + `validation-contract.md`
  (merged into `assets/contract.md`), `pr-summary-template.md`,
  `decision-log.md`, `execution-log.md`. The medium paper trail is four
  artifacts: `contract.md`, `plan.md`, `completion-record.md`, `progress.md`.
- Bench: tasks 01–12 (unexecutable stubs) deleted; arm names are now
  version-neutral `{baseline, full, no-review, light}`; the `--ablation` flag is
  gone; `--validate` requires `tokens_in`/`tokens_out`/`duration_sec` on live
  runs (`cost_usd` is now optional).

**Trust chain (wave 1):**

- The Claude Code **Stop gate runs the `verify` umbrella** — evidence
  re-execution and AC coverage included — at terminal statuses
  (`package`/`done`); fabricated `{result: "pass"}` rows no longer clear the
  local gate. Non-terminal dirty-tree stops still run
  `verify-gates --against-diff`. A missing record no longer auto-allows a stop
  when CQL config exists in the repo (restore/recreate guidance instead).
- AC coverage runs inside `verify-gates` itself (so at the Stop gate and in
  CI), not only in the umbrella; `detect_risk_floor` reads only the `criterion`
  text of object ACs, so proving-command paths cannot inflate the floor.
- `blocked` command rows are **satisfiable**: a non-empty `reason`/`rationale`
  passes; a bare `blocked` row fails. Honesty is no longer punished.
- **Net test-shrinkage gate**: deleted or gutted test declarations/assertions
  (netted at diff level, so moves stay green) are advisory in `diff-audit` and
  blocking via `verify-gates --against-diff` at medium+. New advisory:
  "possible under-fanning" (medium+, >300 added LOC, ≥90% in one new file) —
  the historical ts-search monolith diff fires it; a modular baseline does not.
- **`protect_harness`** (config, default on): PreToolUse denies Write/Edit to
  `quality_loop*.py`, the hook shims, the active record, and the config, plus
  Bash `rm` of the record/config — tamper-evidence, not immutability.
- **Truthful hook failures**: a missing/broken gate runtime is reported as
  exactly that (allow + warning + fix), never as a fabricated "secret-like text
  blocked"; `sys.executable` replaces hardcoded `python3`.
- Destructive-command coverage: anchored patterns (quoted mentions no longer
  match), plus sudo-wrapped commands, `git checkout -- <path>`, and force
  pushes.
- Gate-bug pass: scope-integrity case/glob fixes, "fix" joins the bugfix
  keywords, `e2e`/`security`/`format`/`migration_dry_run` count as executable
  evidence, blocking findings print `error:` (advisories `note:`; the
  load-bearing `warning:` string parse is gone — consumers read structured
  findings).
- `verify --timeout <s>` / `QUALITY_LOOP_TIMEOUT` (default 120, was a
  hardcoded 30) so honest slow suites stop reading as fabricated.

**Funnel (wave 2):**

- Every install writes `.quality-loop/install-manifest.json`; `cql check`
  verifies against it and **uninstall is real**: `cql remove` /
  `install.py --uninstall` removes manifest files, reverses merged hook groups,
  restores `.bak` backups, strips the AGENTS.md managed section, and leaves
  `git status --porcelain` empty after init → remove (verified for claude-code,
  codex, droid, git, and `--host all`).
- **Codex installs ship `AGENTS.md`** (template copy, or a clearly-delimited
  managed section appended to an existing file).
- **One config file**: root `quality-loop.config.json` is canonical;
  `.quality-loop/config.json` still reads for one release with a deprecation
  warning; the installer never writes the legacy path.
- **`render-prompt --role reviewer|security-reviewer --record …`** substitutes
  `{contract}/{diff}/{evidence}` into the prompt cards — the cross-CLI reviewer
  no longer receives the literal string `{diff}`. Security review requires a
  taint path or reproduction for blocking findings; evidence-free findings are
  advisory.
- Cursor and Pi demoted to **advisory rules only, no runtime** — removed from
  the npm picker and the documented host set (the example recipes remain,
  labeled). The npm tarball no longer ships `evals/` or the control module;
  post-install next steps all exit 0.
- `docs/quickstart.md` is the single onboarding doc (drop-in prompt → npx →
  manual copy, ordered by commitment); the README links instead of duplicating.
- The doc-count lint now covers CONTRIBUTING.md, tracks the control add-on
  separately, and exempts lines annotated "as of vX.Y" — it can no longer
  rewrite history (ROADMAP's v3.0-era count is restored to 121 as of v3.1).

**Shrink (wave 3):**

- Medium paper trail **8–9 artifacts → 4** (eval-pinned): one `contract.md`
  (goal, AC table with per-criterion proving commands, risk boundaries,
  verification plan, rollback) replaces task-contract + validation-contract;
  decisions live inline in `progress.md`; commands live in the record.
- **SKILL.md 6.0.0 at 89 lines**: agent-os paragraph removed (now a labeled
  personal-setup note in `docs/cross-cli-recipe.md`), control-plane section
  collapsed to a pointer, vendor model names replaced by capability classes
  (dated menus live only in `assets/routing/`), "risk trumps size" made
  explicit.
- Dead surface deleted: the 7 unconsumed tool shapes, the advisor-history
  section, duplicate citations; `memory.recall_budget_chars` is now actually
  wired as the recall budget default.
- **Control plane opt-in + diet**: delegation rows may carry `session_id` for a
  direct join (the fuzzy time-window join is one-to-one and unparseable
  timestamps count as `unjoinable` — double-counting is structurally
  impossible); droid wrapper runs are `droid_run` events, not 0-token pseudo
  model-calls (schema v8; hook events are backed up to
  `events-backup-schema<N>.jsonl` before a version-mismatch rebuild);
  `zero_usage_lines` drift canaries turn the dashboard yellow on vendor format
  renames; `retention_days` prunes **all** tables (previously events only);
  one shared incremental reader. `control-report` is named the sanctioned
  local audit surface (ROADMAP's "no cost report subcommand" non-goal rewritten
  to match) — "dashboards visualize, gates decide" stands.

**Memory (wave 3.6):**

- Recall is **read-only** (no hit bumps, no file rewrites; eval-pinned
  byte-identical tree); `--bump` is the explicit RETROSPECT-time credit path.
- The 60/40 global/project split is gone: **one ranked pool** under one budget;
  global lessons compete with a small constant prior and keep the `[global]`
  prefix; a non-matching global store no longer taxes project recall.
- **Outcome feedback**: `memory-commit --outcome clean|regressed|reverted
  [--note …]` appends a `kind=outcome` row — the loop's first signal from
  consequences; the brief renders `last shipped: …`.
- **Provenance** (`source: {task_id, git_author}`) on new rows;
  `[unattributed]` markers on recall; `memory-prune` flags stale-scope lessons
  (zero matching files) without deleting them; a stricter relevance floor (≥2
  shared meaningful tokens or a scope-glob match) with an extended stoplist.
- `model_routing.families` maps model ids/prefixes to families so the
  heterogeneity gate survives model renames **loudly**: brief/check-config
  print verified/SKIPPED/FAILED status lines instead of dying quietly;
  `model_routing.as_of` (validated YYYY-MM-DD) warns once when the menu is >90
  days old; `docs/memory.md` rewritten against the real `lessons.jsonl` schema
  with the Claude Code auto-memory coexistence contract.

**Bench (waves 4.1/4.2):**

- **`bench/PROTOCOL.md`**: one pre-registered protocol (merging
  judge-protocol/ablation-protocol/live-run-recipe) with committed decision
  rules — including the R5 branch and the small-task-tax rule — so a completed
  run forces the stated outcome.
- Fixture regenerated (`fixture-smoke-2026-07-20.json`, 12 runs, clearly
  labeled synthetic) and **CI-validated**: `evals.yml` runs
  `runner.py --validate` on every committed results file.
- `control-report --arm-costs [--since]` emits per-session
  `tokens_in`/`tokens_out`/`duration_sec` matching the bench cost schema — the
  instrument for closing the cost loop is shipped; the live run itself is the
  next milestone (Wave 4.3).

**Reviewed:** two independent fresh-context reviews (a cross-family GPT/Codex
reviewer and a security reviewer) ran on the diff and returned request_changes;
26 findings were fixed with eval coverage, 2 rejected with evidence, then a
third fresh-context re-review of the fix delta drove a second fix round
(local-only-main auto-base, option-bearing destructive wrappers, untracked
symlink disclosure + byte-faithful hashing, uninstall pre-existing-file
protection, control-plane range validation, bench mode allow-list).

**Known residual limits (documented, not defects):**

- The Stop hook runs the `verify` umbrella under a 600s host timeout; a suite
  whose evidence re-execution exceeds that budget should run in CI, not the Stop
  hook. Local Stop is shape + fast checks; CI (`evals.yml` + the `verify`
  umbrella) is ground truth.
- `protect_harness` denies Write/Edit and record-deletion Bash patterns for the
  gate scripts, hooks, record, and config; `apply_patch` targets are matched
  best-effort by path reference. Bash-mediated `sed`/heredoc edits remain a
  documented bypass — this is tamper-evidence, not immutability.
- `ran_checks` is a warn-not-fail signal at medium+ by design (the plan's
  make-ran-checks-real decision): an honest `false` must not block, so an
  approving review without `ran_checks: true` is surfaced as a note.
- `memory-recall`'s text digest and `brief` cap output to the recall budget;
  `memory-recall --json` returns whole lesson objects (a char budget cannot
  truncate structured JSON), so a single over-budget lesson can exceed the
  budget in the `--json` path. The agent-facing surfaces (text digest, brief)
  stay capped.

**Evals:** static 11→20, behavioral 44→54, reality 23→40, hook 16→41, memory
26→32, routing 24→29 core suites; control 27→35 add-on suite. Canonical counts
live in `evals/run_evals.py` (`CANONICAL_GATE_CASES`, `CONTROL_ADDON_CASES`).

Credit: per `docs/improvement-plan-2026-07-20.md`.

## 5.1.0

The audit-trail release for the local control plane: the observability index
now carries the loop's *evidence*, not just its token accounting, and a new
per-task report ties findings, delegations, verdicts, and spend to the sessions
that produced them — all still local, read-only, and additive.

**Audit trail (new, additive API):**
- Review findings are first-class `finding` artifacts (severity + text +
  reviewer), not just a count on the review row.
- The orchestrator's `.quality-loop/delegations.jsonl` ledger ingests to
  `delegation` artifacts; malformed lines are counted and skipped, never fatal.
- Query-time join links each delegation to the session it ran in (agent-name
  match within a time window) with exact token sums — no join is ever stored.
- `GET /api/task?task_id=…` returns a full per-task timeline (record, plan,
  minimality decision, delegations, escalations, reviews, findings) plus linked
  sessions and spend; unknown ids return 404.
- `GET /api/metrics` reports loop KPIs (verdict distribution, findings by
  severity, escalations, repair attempts, minimality rungs, evidence rate,
  spend by role, session durations); empty DB returns a zeroed 200.
- New `control-report --task-id` CLI prints the same bundle as markdown or
  `--json`; unknown task exits 2.
- Tool-call targets are secret-redacted (reusing the memory redactor) before
  they are stored, so a key typed at a prompt never lands in the index.

**Dashboard revamp:**
- New Delegations, Tasks, and Metrics views; task drill-down with the full
  audit timeline. Sessions table no longer overflows (fixed layout + ellipsis
  with full-text titles); labeled stacked in/out chart with hover; relative
  timestamps (absolute on hover); duration column; empty states everywhere.
  Still a single self-contained file with zero external requests.

**Schema:**
- `SCHEMA_VERSION` bumped to 7. As always, a schema bump means the SQLite index
  is rebuilt from source on next index — the index is a disposable cache. The
  one exception is hook-reported events (SessionStart/SessionEnd), which have no
  source file to replay; on a schema bump those historical events are not
  rebuildable and are lost with the old DB.

## 5.0.0

The token-diet release: the always-loaded agent surface is cut roughly in
half, decision-making is centralized in an explicit orchestrator layer, and
delegation is pinned to frontier Anthropic + OpenAI models on two hosts
(Claude Code + Codex).

**Orchestrator layer (new contract):**
- The main session owns every decision: task class, context map, contract,
  right-size rung, plan, routing, verdicts, stop-if-unsafe. Workers
  (implementer, reviewer) receive a one-screen brief — goal, contract slice,
  files, commands, done-check — never the skill text, references, or a
  repository tour.

**Token diet (caveman-terse, ladder-first):**
- `SKILL.md` rewritten ~56% smaller; calibration narrative folded into the
  right-size gate and REVIEW sections; roles/advisor detail moved to
  `references/agentic-orchestration.md` (on-demand only).
- `.claude/agents/*` subagents, `examples/claude-code/CLAUDE.md`,
  `examples/codex/AGENTS.md`, `assets/AGENTS.template.md`,
  `assets/prompts/reviewer.md`, and `assets/prompts/drop-in-prompt.md`
  compressed 40-65% with identical JSON output contracts and machine names.

**Routing simplified to two hosts, two vendors:**
- All three shipped routing variants now route exclusively to the latest
  Anthropic (Fable 5, Opus 4.8, Sonnet 5, Haiku 4.5) and OpenAI (GPT-5.6
  Sol/Terra) models. The droid/GLM executor leg is removed from the shipped
  variants; Claude Code implements, Codex reviews cross-family. All floors
  unchanged: reviewer family heterogeneity, strong_reasoning on
  plan/orchestrate, effort ceiling at high. The example config keeps its
  placeholder shape (eval fixture).

No changes to scripts, hooks, gates, schemas, or eval logic; all record
shapes and machine names are unchanged.

**Release completion (2026-07-13):** synced the shared-version invariant to
`5.0.0` at every site the earlier 5.0.0 commit missed — `packages/npm/package.json`,
`EXPECTED_CONFIG_VERSION` in `scripts/quality_loop.py`, the example config
version, and the GitHub Action pin in `hosts/github/quality-loop-example.yml` —
and completed the v5 documentation overhaul (README landing page, new visual
identity in `docs/images/art/`, orchestrator/worker rewrite of
`references/agentic-orchestration.md`, philosophy consolidation). No gate,
schema, or runtime behavior changed.

## 4.3.0

The control-plane release: one local dashboard to monitor, observe, and learn
what the agents are doing — sessions, model calls with exact token usage, tool
calls, token spend, routing, hook events, and every loop artifact (records,
reviews, minimality decisions, plans, escalations, memory lessons, progress).

**Control plane (new):**
- `scripts/quality_loop_control.py` + five subcommands: `control-index`
  (incremental SQLite index at `.quality-loop/control/control.db`, built from
  Claude Code transcripts and CQL artifacts; per-file byte offsets, uuid
  dedupe — a full rescan never double counts; unparsable lines are counted and
  skipped, never fatal), `control-serve` (GET-only JSON API + self-contained
  HTML dashboard on a hard-coded `127.0.0.1` bind; non-GET → 405), `control-status`,
  `control-stop`, and `control-ingest` (hook entry point; **always exits 0** —
  a broken observability plane must never break a session; errors go to
  `.quality-loop/control/ingest-errors.log`).
- Multi-host coverage: alongside claude-code transcripts, the index reads
  **Codex** rollouts (`~/.codex/sessions`, `host='codex'` — gpt models with
  exact per-call token deltas, cwd-scoped) and **Droid/GLM** runs (the
  `droid-glm-exec` wrapper log, `host='droid'` — model + run counts; Droid does
  not expose token usage, so those calls carry none). Each adapter mirrors the
  transcript adapter's offset/rewrite/dedupe safety.
- Sub-agent tree: a session's detail lists the sub-agents it spawned (agent
  name, model, calls) and links back to the parent — resolved from claude's
  `teamName` and codex's `parent_thread_id` (matched by full id, since codex's
  time-ordered ids share prefixes).
- Dashboard (`assets/control-plane/dashboard.html`): overview with exact token
  tiles and a by-day chart, sessions with per-agent attribution and drill-down
  timelines, spend by model/day/session/agent, records & reviews (verdict,
  attestation, escalations, `models_used`), routing snapshot (reuses
  `brief_routing_info`), memory, live hook events. Single file, zero external
  requests (eval-pinned), light/dark, keyboard navigable.
- Hooks: new `hosts/claude-code/control_plane.py` shim wired for
  `SessionStart`/`SessionEnd` in both claude-code `settings.json` and codex
  `hooks.json` (the ≥2-hosts rule). **Opt-in**: with no `control_plane.enabled:
  true` in the repo config the hooks write nothing and start nothing; with it,
  events are recorded and `autostart` launches the server behind a pidfile
  guard (never double-starts).
- Config: optional `control_plane` block (`enabled`, `autostart`, `port`,
  `retention_days`, `prices`) validated by `check-config` (typo-proof: unknown
  keys error). `prices` is YOUR price table (USD per million tokens, substring
  match) — the repo ships no vendor price data; without it the dashboard
  reports tokens only.
- Doctrine line drawn in ROADMAP: dashboards may visualize, only records and
  gates decide. The DB is a disposable cache over sources of truth; deleting
  `.quality-loop/control/` (self-gitignored, outside the attestation hash)
  loses nothing rebuildable (only recorded hook events live solely in the
  cache), and a schema bump rebuilds it automatically.

**Privacy posture:** metadata only — model ids, token counts, tool names,
truncated tool targets (≤200 chars), timestamps, and a short session title
(≤160 chars of the first prompt or the host's summary); beyond those two
deliberate excerpts, conversation content is never copied into the index.

**Evals:** new 20-case `evals/run_control_evals.py` suite (token math,
incremental/rescan dedupe, malformed-line resilience, subagent attribution,
artifact ingestion, price arithmetic, API endpoint contract, localhost-only
bind, GET-only enforcement, dashboard self-containment, disabled no-op,
garbage-stdin exit 0, pidfile guard, real autostart round-trip, config
validation, installer wiring), wired into CI. Gate-case count is now **164
across 7 suites** (11 static + 44 behavioral + 26 memory + 23 reality + 24
routing + 16 hook + 20 control).

**Migration from 4.2.0:** bump the `version` string in your
`quality-loop.config.json` to `4.3.0` — the `control_plane` block is optional
and everything is off without it. Re-run `scripts/install.py` (or copy
`scripts/`, `hosts/claude-code/`, and `assets/control-plane/`) to get the new
module, shim, and dashboard; the settings merge adds the new hook entries
idempotently.

## 4.2.0

The model-routing release: express a multi-harness topology in config, enforce
reviewer independence on the model *family* across hosts, and make escalation
an evidence trail instead of a claim. Ships the roadmap's R7 cross-CLI recipe
and the evidence base that R5 (per-model process depth) was deferred for.

**Multi-host per-role routing:**
- A `model_routing.agents` entry may now be an object `{host, class}` to pin
  that role to another harness (plain strings keep the v4.1 meaning: the
  default host). New optional `main_session {host, class, model}` declares
  where the implementer runs — nothing is rewritten for it; it feeds the
  heterogeneity check, `brief`, and print-host output.
- `setup-models` with no `--host` applies every host in the topology: file
  hosts (claude-code, droid) get frontmatter rewrites, print hosts (codex, pi)
  print behind an explicit banner — `PRINT-ONLY — settings not applied or
  verified by CQL`. There is deliberately no "applied ✓" for print hosts, and
  no print-host drift detection: their config lives outside the repo, so CQL
  says "declared, not verified" instead of pretending. `--host` keeps its
  historical retarget meaning on v4.1 single-host configs and becomes a pure
  filter on multi-host topologies (it never drags default-host roles onto the
  selected host); a `main_session` must resolve to a host or check-config
  errors (a hostless one would silently skip the heterogeneity check).
- `brief` renders routing per host and keeps drift detection for file hosts.

**Reviewer heterogeneity on model family (fixes a live hole):**
- `check-config` now compares the implementer and fresh_reviewer by resolved
  model **family** (new optional `family` field on host_models blocks, else a
  well-known-prefix match), across hosts. Implementer `sonnet` vs reviewer
  `claude-sonnet-4-5` — different strings, same model family — previously
  passed; it now fails. Unknown/BYOK/placeholder ids skip, never false-positive.
  `allow_same_family: true` is the explicit, greppable escape hatch (same
  *model* is never allowed). Harness diversity is not model heterogeneity.

**The knob — routing variants (`assets/routing/`):**
- Three pre-validated `model_routing` variants along the intelligence↔cost
  dial: `max-intelligence`, `balanced`, `max-throughput`, each pinned by an
  eval case that splices it into the example config and requires `check-config`
  to pass with floors held (strong_reasoning tier, different-family review,
  effort ≤ high). A dated model-menu README documents prices and supply-risk
  notes with **no machine consumers** — stale data can never fail a build.
  Deliberately NOT built: a machine-read model catalog, a dial/pack resolution
  engine, escalation-chain config, a cost-report subcommand (see ROADMAP).

**Escalation as evidence (R5 evidence base):**
- New optional record fields: `models_used` (per-role host/model/attempts/cost
  attribution) and `escalations` (model-tier escalation events). `trigger` is
  an enum of exactly one value — `verified_failure` — and `verify-gates`
  requires every `failing_commands` entry to match a recorded `commands_run`
  failure carrying an evidence handle: self-report escalation is not evidence,
  and a bare fail row is free to fabricate. The `escalated` status stays
  the human-input valve; this gate binds only model-tier escalation.
- A `fail` entry superseded by a later `pass` of the same command (the honest
  RED→GREEN shape an escalation leaves behind) no longer blocks verify-gates;
  outstanding failures still do.
- Cost per accepted record is a documented `jq` recipe, not a subcommand — the
  v3.0 surface reduction stays reduced.

**R7 — cross-CLI orchestrator recipe:**
- `docs/cross-cli-recipe.md`: live-verified headless commands for running the
  loop's roles across `claude -p`, `codex exec`, and `droid exec`, with the
  caveat that harness diversity does not guarantee model heterogeneity —
  `check-config` stays the arbiter.

**Counts and migration:**
- Gate-case count is now **144 across 6 suites** (11 static + 44 behavioral +
  26 memory + 23 reality + 24 routing + 16 hook); the trigger smoke fixture
  stays a separate 10-case fixture.
- Migration: bump the `version` string in your `quality-loop.config.json` to
  `4.2.0` — every new config and record field is optional and additive
  (`run_metrics` untouched; the archived v4.1.0 record passes unchanged, pinned
  by eval). **One behavior change is deliberate:** a v4.1 config whose
  implementer and reviewer are different models in the *same family* (e.g. an
  all-Claude sonnet-implements/opus-reviews tiering) now fails check-config —
  that was always the documented intent ("different model family", SKILL.md
  §Calibration) and the code finally enforces it. The error names the fix:
  route review to another family, or set `"allow_same_family": true` to accept
  the risk explicitly.

## 4.1.0

The trust-chain release, reconciled onto the independently shipped 4.0.0
(both streams ran the same day; 4.0.0 was released while this stream was in
review, so its changes land here as 4.1.0). Implements the 2026-07-09 critical review
(`docs/critical-review-2026-07-09.md`): R1–R4 and R6–R8. R5 (per-model process
depth) is deliberately deferred to the roadmap pending n≥3 live replication.

**Enforcement (R1) — close the inversion:**
- `action.yml` executes the action's **own pinned copy** of the gate scripts via
  `GITHUB_ACTION_PATH`, never the user checkout. The documented soften-and-commit
  attack now fails end-to-end; a red-team reality case replays the attack and a
  lint case pins every python invocation to the pinned path.
- Inputs are passed to the action step via `env` (no `${{ }}` interpolation into
  bash — script-injection sink closed), the action fails when a repo carries
  quality-loop config but no record (record-deletion bypass closed), and a
  `base: HEAD` no-op configuration emits a CI warning.
- Stop gate decision table: gates also fire at `verify`/`review` with a dirty
  tree; `escalated` pauses require a non-empty `escalation_reason` (reasonless
  escalation is gated like any non-terminal status); a present-but-unreadable
  record **blocks instead of crashing** (fail closed); git-absent environments
  fail open by design, documented. Earlier statuses still stop freely — the
  merge boundary is anchored by CI.
- New `verify --require-terminal`: fails when the diff vs base is non-empty but
  the record status never reached `package`/`done`.

**Evidence base (R2/R4):**
- README publishes **all five** eval runs with methodology labels derived from
  each run's own documentation — including the model-proxy relabel of Sudoku
  07-01 and the negative results (ts-search Codex **−9.0**, webapp Codex −1.11).
- Trigger suite reclassified as a **smoke fixture** and excluded from the gate
  count: its default keyword grader is reverse-engineered from its own prompts
  and structurally cannot fail. A real activation check needs `--judge-command`.
- Gate-case count is now **130 across 6 suites** (11 static + 39 behavioral +
  26 memory + 23 reality + 15 routing + 16 hook — grown by the union of both
  streams' suites plus the merge-seam case), synced across every public doc
  and enforced by a count-consistency lint case. Evidence dashboard regenerated.
- Test-weakening detection is scoped to added lines in test files
  (`quality_loop_core.test_weakening_hits`), removing a false-positive class.

**Process cost (R3):**
- Live bench results must record per-arm `cost_usd`, `tokens_in`, `tokens_out`,
  `duration_sec`; `bench/runner.py --validate` hard-fails on missing, zero,
  negative, or non-numeric values and on empty/missing `runs`. Fixture runs are
  exempt and labeled.
- Optional `run_metrics` block in the record schema, type-checked when present.
- README states the measured process tax (~15–22k tokens scaffolding per medium
  loop, 3–6× wall time) next to the lift numbers, with the new policy: **every
  gate must earn its tokens** (`references/philosophy.md`).

**Docs (R6/R7):**
- References deduped to canonical locations (task-class table, right-size
  ladder, phase prose); the three divergent definitions of "medium" unified;
  `references/` shrank 65,869 → 62,982 bytes vs the shipped 4.0.0 baseline
  (−4.4%; both streams had already deduped independently — the trust-chain
  branch's own measurement was −12.6% against its pre-dedup base. The −40%
  aspiration was not reached without cutting load-bearing content — recorded
  as an accepted deviation).
- `agentic-orchestration.md` rewritten so page-weight matches what ships, with a
  2026 topology decision note: orchestrator-delegates (host-native) vs
  executor-consults-advisor (Anthropic advisor tool, an API-level primitive) —
  including the strong-executor caveat and why harness diversity does not
  guarantee model heterogeneity.
- Philosophy #8 corrected: the scaffold-model interaction is **model-specific,
  not a strength gradient** (Claude took the largest lifts; Codex was
  flat-to-negative; strength did not predict the sign).
- Cursor rule no longer `alwaysApply: true` (both the local copy and the tracked
  `examples/cursor/` source users actually install); `v240-validation-contract.md`
  moved to `archive/` with pointers updated; version markers unified on 4.1.0.

**Code health (R8):**
- New `scripts/quality_loop_core.py` (319 lines): shared status-set constants,
  atomic write, git wrapper, secret patterns/redaction, evidence predicates.
  Module sizes vs the shipped 4.0.0 baseline: quality_loop.py 1,833 → 1,693;
  memory 481 → 464; reality 574 → 561; routing 577 → 567. Reviewer-heterogeneity checks single-sourced;
  dead phase machinery (`resolve_phase`, `--phase`, schema field) removed with
  legacy-field tolerance; `init-record` no longer nests `.quality-loop/` when
  the record lives inside it.

Reviewed before merge by a fresh-context quality reviewer, a fresh-context
security reviewer, and an independent Codex/GPT-5.5 pass; all verified findings
fixed or explicitly accepted (accepted: references-dedup shortfall; stop gate
allowing implement-status stops with the CI backstop; git-absent fail-open).

## 4.0.0

Trust-the-gates hardening from a two-reviewer audit: the deterministic gates now
run one code path, advisory findings stop forcing false failures, and the
lifecycle models the retrospective step it always described. Version is now a
single source of truth (skill, config, CHANGELOG, npm all read 4.0.0; `check-config`
rejects a config that disagrees).

### Removed

- **Runtime-dead classifier path** in `scripts/quality_loop.py` (`evaluate_input`,
  `derive_risk_tier`, `derive_task_class`, `required_gates_for_tier`,
  `minimality_flags`, `requires_security_reviewer`, and the `*_SIGNALS` / `GATES_*`
  tables). Nothing in the shipped commands called it; the real gates derive risk
  from the record and the diff. Eval cases now feed a raw goal + record through the
  same production path, so a second implementation can no longer drift from it.
- **`archive/`** (Honcho adapter, driven-mode orchestrator, v2.4 ceremony
  subcommands and their evals) deleted outright — it was frozen dead code kept only
  as history, which `git log` already provides.
- **Vendored skill copies** under `examples/*/variants/*` replaced with a one-line
  README pointer to the repo-root source of truth, so the skill is defined once.
- **`v240-validation-contract.md`** removed from the repo root.
- **Checked-in dogfood run artifacts** (`.quality-loop/readme-rebuild-*`) removed and
  `.gitignore`d.

### Fixed

- **Advisory findings no longer force `Overall: FAIL`.** `diff-audit` now separates
  **blocking** findings (secrets, test-weakening) from **advisory** ones (dependency
  bump, migration touch, large diff, untracked notes, unreadable file, shortcut
  markers) and exits 0 when only advisories are present. `verify` aggregates the two
  streams, so a benign lockfile bump or a scaffolding sweep is surfaced without
  failing the gate or blocking the pre-commit hook.
- **`diff-audit` untracked sweep** excludes `.quality-loop/`, agent record JSON, and
  `__pycache__`, and now emits an advisory (instead of silently continuing) when an
  untracked file cannot be read.
- **`verify --base`** detects a missing/unresolvable base, prints an actionable hint,
  and falls back through `origin/main`, `main`, `HEAD`, and finally the empty-tree
  object so a fresh detached checkout still audits cleanly.

### Added

- **`RETROSPECT` lifecycle step** modeled end to end: added to `STATUSES`,
  `REQUIRED_STEPS`, the record-schema step enum, and the example config (with a
  `retrospector` profile) behind a `harness_update` gate.
- **Advisor role** (Anthropic advisor-tool pattern): a cheap executor drives the loop
  and consults a strong reasoning model at reasoning walls; the advisor never calls
  tools and is capped at `max_uses ≈ 3`. Documented as the default for small/medium
  tasks in SKILL.md and `references/agentic-orchestration.md`; optional `advisor`
  block added to the config example and schema.
- **Shortcut-marker convention.** An inline `cql:` comment names the complexity
  ceiling and its upgrade path; `diff-audit` reports the count as an advisory only.
- **Stricter `check-config`.** Validates the config version, asserts reasoning-heavy
  steps (PLAN/MINIMALITY_GATE/REVIEW) route to `strong_reasoning`, and the schema now
  sets `additionalProperties: false` at the root and requires `policy_guard` and
  `routing_defaults.{low,medium,high}`.

### Changed

- **Review-waiver scope** clarified in SKILL.md: waivable only on small/low work;
  medium+ always requires an independent review.
- **SKILL.md slimmed** — the drop-in prompt moved to `assets/prompts/drop-in-prompt.md`
  and the per-command CLI catalog to `references/tool-contracts.md`; duplicated
  Tool-Surface and trends/inspirations prose de-duplicated across references.
- **`verify_gates` risk-tier logic** refactored to a table-driven structure and the
  `check-config` reviewer-heterogeneity checks extracted into one
  `_reviewer_heterogeneity()` helper.

## 3.1.0

Capability-aware, cost-disciplined routing, plus reality-layer hardening from
the first live 2x2 webapp eval (`examples/webapp-agent-eval-2026-07-07/`).

### Added

- **Allowlist scaffolding.** `init-record` now creates
  `.quality-loop/allowed-commands` with usage guidance; both live CQL arms
  failed `run-evidence` solely because the file never existed. The
  `not_allowed` finding now says how to fix it.
- **Helper-integrity reporting.** `verify` prints the sha256 of each helper
  module so a hook or CI can catch a locally modified gate script. Motivated by
  a live run where the agent silently softened `diff-audit` in its workspace
  copy and reported PASS against it. SKILL.md adds the rule: never repair or
  stub the helper; report breakage and stop.
- **Actionable partial-install failure.** A `scripts/` copy missing a sibling
  module exits 2 with a clear "incomplete install" message instead of an
  ImportError traceback.
- **Product floor in Calibration.** For user-facing tasks the validation
  contract must include keyboard/labeled/a11y basics, no `prompt()`/`confirm()`
  primary flows, and a class-appropriate test floor; the reviewer checklist
  scores product fitness (live data: Codex +7.5 total but −1.1 code-quality).
- **`hosts/codex/README.md`** documenting `workspace-write` sandbox limits
  (`.git` writes and port binding blocked) and the candor rule for blocked steps.
- **`bench/live-run-recipe.md`** capturing the proven live-eval mechanics:
  clean-home isolation, drop-in delivery, browser-verified hidden behaviors,
  scrubbed two-judge blind protocol, pristine-gate re-runs.
- **4 new reality eval cases** (20 total): record-only trailing change stays
  fresh, allowlist scaffolding, partial-install error, helper-integrity output.

### Fixed

- **Attestation staleness chicken-and-egg.** `attest-review` hashes the diff
  excluding `.quality-loop/`, so recording final verify evidence after
  attestation no longer stales the review. Freshness checks accept legacy
  full-diff hashes. Any code edit after attestation still requires re-attesting.
- **Scope integrity vs record artifacts.** Changed files under `.quality-loop/`
  no longer count as unmapped code changes (and no longer mask phantom
  completion as real work).

### Added (routing)

- **Reasoning-effort ceiling.** `check-config` now rejects `xhigh`/`max` in
  `model_routing.host_models` unless the specific model-class block sets
  `"allow_overthink": true`. Effort is per-step, not per-task endurance —
  `xhigh`/`max` overthink and overspend each step and make reviews noisier. `high`
  is the routine ceiling; `allow_overthink` is an explicit, greppable escape hatch
  for a genuinely ambiguous, architecture-sensitive one-off. `setup-models` also
  surfaces an advisory warning when a block exceeds the ceiling. Schema gains an
  `allow_overthink` boolean on each model-class block.
- **Model capability glossary** in `references/agentic-orchestration.md`: defines
  *intelligence*, *taste*, and *cost*, plus a reasoning-effort-ceiling section and an
  escalation policy (explore cheap, escalate without asking when output misses the
  bar, judge output not price). Turns step-shape routing into capability-aware
  routing.

### Changed

- **Example config `codex` routing** bumped `strong_reasoning` and
  `code_specialized` from `medium` → `high` (plan/minimality/implement reward
  reasoning; `high` is the sweet spot, not `medium`). `cheap_fast` stays `low`.
  Config version 2.2.0 → 2.3.0.

## 3.0.0

Outcome-grounded, model-adaptive, 40% smaller. The biggest refactor since v1.0:
the harness now optimizes for code quality (not artifact production), adapts
ceremony to model strength, and uses a single `verify` command as the primary
gate. Built on evidence from three live cross-agent evals and external research
(Anthropic Mar 2026, Cognition Apr 2026).

### Cut and archived (surface −40%)

- **Archived** to `archive/`: Honcho memory adapter (`quality_loop_honcho.py`),
  driven-mode orchestrator (`quality_loop_run.py`, `quality_loop_hosts.py`),
  v2.4 ceremony subcommands (`context-check`, `verify-phases`, `trace-audit`),
  telemetry/stats, Honcho and Graphify eval suites, memory reference docs for
  those backends, and v2.4 eval cases (12-14).
- **Scripts**: 4,600 → 3,300 lines. **Eval suites**: 9 → 7 (in CI). **Eval
  cases**: 129 → 116. **CLI subcommands**: 20 → 16. **SKILL.md**: 477 → 172 lines.
- **Config/schema**: removed `memory.honcho`, `memory.graphify`, `hosts`,
  `execution` blocks; removed `context_budget` and `phase_verifications` from
  the record schema (kept `phase` for backward compat).
- **Memory**: files backend is the only backend. `memory-recall` and
  `memory-commit` no longer accept `--config` (Honcho selection).

### Rewritten SKILL.md (model-adaptive calibration)

- **New Calibration section**: strong models skip ceremony on tiny/small; weaker
  models get full scaffolding; review is paid only when the task exceeds what the
  model does reliably solo. Cites own eval data (GLM +8.0, Claude +4.5, Codex +1.0
  on Sudoku; Codex −9.0 on ts-search).
- **Complexity Brake → Right-Size Gate**: "minimal diff is not minimal
  architecture" promoted to the rule itself. Fixes the Codex −9.0 failure class
  where the gate pushed GPT-5 into a 60x-slower monolith.
- **Enforcement matrix** moved to `references/enforcement-matrix.md`; 5-line
  summary in SKILL.md.

### Outcome-grounded gate path

- **New `verify` umbrella command**: runs record-shape gates, diff-grounded
  reality checks, evidence re-execution, and AC-to-command coverage in one pass.
  One command to remember instead of four.
- **AC-to-command coverage check**: each acceptance criterion with a
  `proving_command` must have that command in `commands_run` with `result=pass`.
- **Reviewer card v2**: reviewer must **execute** tests/benchmarks when
  available (tool-using evaluator), not just read the diff. Verdict records
  `ran_checks: true|false`. Skeptical-evaluator guidance: penalize stubs,
  verify end-to-end.
- **Communication-bridge rule**: implementer filters reviewer findings against
  the contract; in-scope findings become fix tasks, out-of-scope findings become
  follow-ups. Prevents review loops.

### Capability routing

- **Reviewer heterogeneity**: `check-config` now hard-fails when implementer and
  fresh_reviewer resolve to the same model on medium+ tasks. Checks both profile
  models and model-class resolution via `model_routing.host_models`.
- **Capability annotations**: model classes annotated (cheap_fast = map/package/
  summarize; strong_reasoning = plan/review/debug; code_specialized = implement/
  test) in the config description.
- **Smart Friend pattern**: optional role where the implementer consults a
  stronger model on defined triggers (2 failed repairs, merge conflicts,
  architecture uncertainty). Documented in `references/agentic-orchestration.md`
  with per-host wiring.

### Ablation eval program

- **`bench/ablation-protocol.md`**: 3 tasks × 2-3 model families × 3 seeds × 4
  arms (baseline, v3-full, v3-no-review, v3-no-contract). Headline metric
  excludes D7 (artifact production) — code-quality lift only.
- **New web-app task** (`bench/tasks/13-webapp-task-manager.json`): browser-based
  task manager with localStorage persistence and browser-automation verification.
- **Pruning rule**: a component whose ablation shows no code-quality lift across
  ≥2 families is a v3.1 cut candidate.
- **Bench runner** updated with `--ablation` flag and ablation arms.

### Docs and packaging

- **ROADMAP.md** updated for v3.0.
- **npm package** bumped to 3.0.0.
- **CI workflow** updated to remove archived eval suites and keep the v3 routing,
  trigger, hook, and ablation smoke checks.
- All 116 eval cases pass (11 static + 32 behavioral + 26 memory + 16 reality +
  12 routing + 10 trigger + 9 hook).

## 2.4.0

Three-phase lifecycle: PLAN → EXECUTE → REVIEW.

- **Canonical model recast as three phases** (`SKILL.md`) — the operating model is now **PLAN → EXECUTE → REVIEW**, each phase closed by its own verification gate before the next may start. Guiding principle: *"An LM runs a plan-execute-review loop. Context is a budget. Verification terminates each phase."* The previous nine-step lifecycle (`INTAKE -> CONTEXT MAP -> SPEC/VALIDATION CONTRACT -> COMPLEXITY BRAKE -> PLAN -> IMPLEMENT IN SMALL SLICES -> VERIFY -> INDEPENDENT REVIEW -> SHIP/HANDOFF -> RETROSPECTIVE`) is preserved in full as sub-steps, mapped onto the three phases in a table so every older machine name (`INTAKE`, `EXPLORE`, `MINIMALITY_GATE`, `PLAN`, `IMPLEMENT_SLICE`, `VERIFY`, `REVIEW`, `PACKAGE`, `RETROSPECT`) stays valid and unlabeled steps do not exist. Existing records, configs, and automation keep working unchanged.
- **New `context-check` subcommand** (`scripts/quality_loop.py`) — enforces that medium/mission tasks declare a per-phase `context_budget` (`inputs`, `excluded`, `output_summary`) in the state record; flags missing budgets, missing `output_summary`, and overlapping `inputs`/`excluded`.
- **New `verify-phases` subcommand** (`scripts/quality_loop.py`) — checks the state record's `phase_verifications` array so a medium/mission task cannot advance phases without a `verified` block, and fails when the `review` phase is verified by the same agent that ran `plan` or `execute` (`verifier: same_agent` is a hard fail for review on medium/mission).
- **New `trace-audit` subcommand** (`scripts/quality_loop.py`) — reads an `execution-log.jsonl` trace, flags pathological loops (same `tool` + `args_hash` three or more times consecutively), and aggregates per-phase step count, duration, and cost.
- **New assets**: `assets/context-budget.md` (context-budget template), `assets/phase-verification.md` (per-phase verification block template), `assets/execution-log.jsonl.md` (execution-trace format doc).
- **Schema additions** (`assets/agent-record.schema.json`) — `phase` (enum `plan|execute|review|done|escalated`), `context_budget`, and `phase_verifications` are all new, optional fields. The existing `status` field is kept for backward compatibility and silently mapped to `phase`; v2.3.x records with no `phase` field continue to validate unchanged.
- **3 new eval cases** (`evals/cases/12-*.json`, `13-*.json`, `14-*.json`) pin the new gates: a medium task missing `context_budget` (fails `context-check`), a medium task missing `phase_verifications` (fails `verify-phases`), and a medium task where the `review` phase is verified by `same_agent` (fails `verify-phases`). Full suite: 14/14 eval-case runs green.
- **Docs sweep** — `README.md`, `references/lifecycle.md`, `references/agentic-orchestration.md`, and the packaged host quickstarts (`examples/claude-code/CLAUDE.md`, `examples/codex/AGENTS.md`, `examples/cursor/.cursor/rules/coding-quality-loop.mdc`) now lead with the three-phase model; the nine machine-name sub-steps remain documented as the mapping table, not removed.
- **Non-goals, explicitly deferred to v2.5.0+**: mutation testing, environment manifest, phantom-symbol resolution, and a metrics aggregator. None of these are in scope for this release.
- **Packaging** — `packages/npm/package.json` bumped to `2.4.0`; `packages/npm/scripts/prepack.mjs` continues to bundle the new asset files (it globs `assets/` recursively, so no prepack changes were required).

## 2.3.2

Findings from the `ts-search-eval-2026-07-03` eval baked into the harness.

- **New `performance_sensitive` medium signal** (`scripts/quality_loop.py`) — tasks whose brief includes a benchmark harness, or that touch a hot request path, indexing/ranking, rendering, or data-pipeline surface, now classify as **medium** even without other multi-file signals. This triggers the validation contract + independent-review gates that the ts-search Codex+CQL run should have run but did not.
- **New `under-fanned` minimality flag** (`scripts/quality_loop.py`) — the simplicity reviewer now flags multi-feature medium/mission tasks that collapse into a single source file or a single test file. Signaled by `single_source_file` / `single_test_file` + `feature_count >= 3` in the proposed solution. Modularity is a maintainability property; a 700-LOC monolith with one 13-test file for a seven-feature brief is not "minimal."
- **`assets/validation-contract.md`: new Performance / Complexity Targets section** — required for performance-sensitive tasks. Forces the implementer to commit to a worst-case complexity for the hot path, a p50/p95 latency budget, a memory budget, and the exact benchmark command *before* implementing. If the chosen approach cannot hit the target, escalate at PLAN — do not implement and discover the miss at VERIFY.
- **`SKILL.md` COMPLEXITY BRAKE: algorithmic-complexity clause** — explicit rule that "simple linear scan" is not simpler than the required data structure when the brief includes a benchmark. Rewrites the perf blind spot from advisory ambient text into a named brake step. Adds an anti-pattern that separates *minimal code* from *minimal performance* and *minimal modularity*.
- **`references/reviewer-checklists.md`: perf-regression and under-fanned checks** — the fresh-context reviewer now must confirm that the diff’s chosen algorithm honors the contract’s worst-case complexity commitment; a diff that meets correctness but misses the perf target is `blocking`, not `minor`. The simplicity reviewer explicitly flags monolithic multi-feature diffs.
- **New eval cases** (`evals/cases/10-*.json`, `11-*.json`) — pin (a) `performance_sensitive` alone lifting a task to medium with the full medium gate set, and (b) `single_source_file` + `single_test_file` + `feature_count >= 3` producing the `under-fanned` minimality flag. Full suite: 11/11 case runs + 31 + 9 + 5 + 15 + 11 + 10 + 27 + 7 = 115 runner checks green.
- **Reference eval published**: `examples/ts-search-eval-2026-07-03/` contains the full 2×2 blind eval, both judge score files, aggregate JSON, and a report that motivates every change above. Directional finding: CQL lifted Claude Code (Sonnet 5) by **+15.0** blind mean but hurt Codex (GPT-5) by **−9.0** on this task — the harness now closes the specific gap that caused the Codex regression.

## 2.3.1

One-command `npx` installer (first npm-installable release).

- **`npx coding-quality-loop init`** — new zero-prerequisite installer under `packages/npm/`. Auto-detects host (Claude Code, Codex, Cursor, Droid, Pi) by scanning the target directory, invokes bundled `scripts/install.py` under the hood, and prints tailored next-steps. Interactive by default; `--yes` for CI, `--dry-run` for preview, `--host` to skip detection. Also ships `npx cql init` alias, `add <host>` for incremental wiring, and `check` for post-install verification.
- **Real skill install for Claude Code + Pi** — `install.py --host claude-code` copies `SKILL.md`, `references/`, `assets/`, and `scripts/` into `.claude/skills/coding-quality-loop/`. `install.py --host pi` does the equivalent under `.pi/skills/coding-quality-loop/`. Previously only settings/hooks landed and the skill was not discoverable by the host.
- **Zero-dependency Node package** — `node:*` built-ins only, ~1 s cold start, ~114 kB tarball. Node 18+.
- **`scripts/install.py` extensions** — new `--host cursor` and `--host pi` (previously required manual `cp -r`), new `--json` flag for machine-parseable output that the Node CLI consumes, `install_runtime()` now also copies `assets/quality-loop.config.example.json` so `setup-models` works immediately after install, and `install_git()` now resolves Python via `sys.executable` → `python3` → `python` (fixes Windows hosts that only ship `python.exe`).
- **CI** — `.github/workflows/npm-smoke.yml` runs `cql init --dry-run --yes` on Ubuntu + macOS + Windows across Node 18/20/22 for every host; `.github/workflows/publish-npm.yml` publishes to npm on release tag with tag/version check (also enforced for manual dispatch non-dry-runs), `NPM_TOKEN` preflight, and a real `npm pack` + tarball-install smoke step. `packages/npm/test/` has `node --test` coverage for the argv parser, host detection, and CLI end-to-end (22 tests).

## 2.3.0

Config-based model routing (`setup-models`).

- **`model_routing` config section**: `assets/quality-loop.config.example.json` ships a
  pre-filled `model_routing` block with per-host mappings (Claude Code, Droid, Codex, Pi).
  Each model class (`cheap_fast`, `strong_reasoning`, `code_specialized`) maps to a real
  model id and optional thinking level. Copy the example to `quality-loop.config.json` at
  your repo root, set `host`, adjust your block, and run `setup-models`. Schema updated in
  `assets/quality-loop.config.schema.json`; `check-config` validates the section when present
  (backward compatible — configs without it still pass).
- **`setup-models` CLI command**: `python3 scripts/quality_loop.py setup-models --host <host>`
  applies the routing through each host's native mechanism. Claude Code and Droid get their
  agent/droid `.md` frontmatter rewritten (`model:` + `effort:`/`reasoningEffort:`); Codex
  prints the `config.toml` additions (`model`, `model_reasoning_effort`, per-role
  `config_file` layers); Pi prints `/model` commands and thinking levels per role. Supports
  `--dry-run`, `--json`, `--target`, and `--config`. Unsupported thinking levels for a host
  are warned and omitted; the command exits non-zero so CI catches divergence.
- **`brief` shows routing**: the session-start briefing now includes a `## Model routing`
  section (host, per-class models/thinking, drift detection for file-based hosts). New
  `--config` arg; auto-detects `quality-loop.config.json` in the working directory. The
  `model_routing` key is added to `--json` output.
- **Droid installer**: `install.py --host droid` copies the example role droids into
  `.factory/droids/` (consistent with the existing Claude/Codex/git/github installers).
  The wiring report now points to `setup-models` as the next step.
- **Agent files switched to `model: inherit`**: the committed `.claude/agents/*.md` and
  `examples/droid/.factory/droids/*.md` files now ship with `model: inherit` (host-neutral
  at rest) instead of Claude-specific aliases. `setup-models` writes the configured
  identifiers. This also fixes the Droid examples, which used `haiku`/`sonnet` aliases that
  Droid's validator rejects as unknown model ids.
- **New module `scripts/quality_loop_routing.py`**: stdlib-only routing resolver, frontmatter
  rewriter (line-based, no YAML dependency), Codex/Pi renderers, validation, and the
  `setup-models` command. Follows the `quality_loop_memory.py` separate-module pattern.
- **Evals**: new `evals/run_routing_evals.py` — 11 offline cases pinning claude-code/droid
  rewrites, idempotency, thinking write/remove, codex/pi print output, unsupported-thinking
  exit code, check-config validation, brief routing+drift, and dry-run. Full suite:
  9+31+27+15+9+5+10+7+11 = 124 cases.
- **Docs**: `references/agentic-orchestration.md` gains a "Config-Driven Model Setup"
  subsection with the per-host mechanism table and workflow. `examples/droid/README.md`,
  `examples/pi/README.md`, `examples/codex/AGENTS.md`, `SKILL.md`, and `README.md` updated.

## 2.2.0

Harness-agnostic multi-agent routing + longitudinal coding partner + memory hardening.

- **Per-role prompt cards**: add `intake.md`, `context-map.md`, `minimality.md`,
  `implementer.md` to `assets/prompts/` (joining planner/reviewer/security-reviewer/
  package). Any harness or human can now run any role by pasting one card.
- **Claude Code subagent set**: add read-only `quality-loop-context-mapper.md` (model:
  haiku) and `quality-loop-planner.md` (model: sonnet) to `.claude/agents/`, alongside
  the 2 existing reviewers (now model: sonnet).
- **Droid host example**: `examples/droid/` with `.factory/droids/` role droids
  (mapper, planner, reviewer, security-reviewer) and a README explaining the
  single-threaded-writes + clean-context-intelligence pattern.
- **Pi role wiring**: extended `examples/pi/README.md` with provider/model-per-role
  notes and Pi as the documented escalation harness for mission-class work.
- **Harness-agnostic wiring section** in `references/agentic-orchestration.md`: a
  role -> native mechanism table (Claude subagents, Droid droids, Codex, Cursor, Pi),
  with Cognition 2026 and Anthropic 2025 citations confirming the core bet.
- **`brief` command**: `python3 scripts/quality_loop.py brief` prints a session-start
  project briefing — last run summary, open risks, top recalled lessons (project +
  global, split-capped), progress-file tail, and a suggested next step. Wired into
  the Claude Code `SessionStart` hook; one-line "run brief at session start" added
  to `assets/AGENTS.template.md`.
- **Global cross-project memory**: `~/.quality-loop/global/` store for user-level
  conventions/preferences. `memory-commit --global`; recall merges project + global
  under a split-capped budget. `memory-status` reports both stores. `memory-commit`
  now accepts `--lesson` without a record path (for manual global lessons).
- **Session continuity**: `assets/progress.md` template; SKILL.md gains a "Session
  continuity" rule (read brief+progress at session start, update at PACKAGE/RETROSPECT,
  resume from the surfaced next step). Follows Anthropic's long-running-agent harness
  pattern (progress file + incremental sessions + git as memory).
- **Driven mode reframed**: README/SKILL.md now state that `quality_loop_run.py` is an
  optional *reference* orchestrator using a single host for all steps — per-role model
  routing is the host's job via the config profiles and the harness-agnostic role pack.
  The config description clarifies it is routing *data*, not a runtime.
- **Skills Hub publish checklist** added to the Release & pinning section.
- **References updated** with Cognition (Apr 2026, multi-agents-working) and Anthropic
  (Nov 2025, effective-harnesses-for-long-running-agents) citations in philosophy and
  orchestration trend sections.
- **Fix (security):** `redact()` missed OpenAI hyphenated key families
  (`sk-live-*`, `sk-proj-*`, `sk-test-*`, `sk-svcacct-*`) because the fallback
  `sk-[A-Za-z0-9]{20,}` pattern excludes hyphens. Independent review proved a
  raw `sk-live-<hex>` could be persisted verbatim into `.quality-loop/memory/lessons.jsonl`
  and its hex payload leaked into the searchable `keywords` array. New regex
  covers all four variants; keyword tokens are re-scrubbed at Honcho egress.
- **Add (defense in depth):** entropy-based secondary redactor catches
  obfuscated / novel-shape secrets that no regex covers. Uses Shannon entropy
  >= 3.5 bits on tokens >= 28 chars; skips hex-only git SHAs, UUIDs, dotted
  paths, and file paths so prose and identifiers stay intact.
- **Add:** `scripts/quality_loop_honcho.py` — runnable [Honcho](https://honcho.dev)
  memory adapter. Same recall/commit contract as the files backend; dual-writes
  to files then mirrors to Honcho; transparent fallback to files when the SDK
  is missing, the API key is unset, or the network call fails. Config lives
  under `memory.honcho` with `HONCHO_API_KEY` from env. Runtime dep
  `honcho-ai` is imported lazily so files-backend users never install it.
- **Add (zero-config local):** the Honcho adapter now defaults `base_url` to
  `http://localhost:8000` and connects **without an API key** to any local
  endpoint (`localhost`, `127.0.0.1`, `0.0.0.0`, `host.docker.internal`,
  `.local`, `::1`). Run upstream Honcho with `AUTH_USE_AUTH=false docker
  compose up` and you get reasoning-based memory with zero secrets on disk.
  Cloud URLs (`https://api.honcho.dev`, any non-local host) still require
  `HONCHO_API_KEY` — the adapter refuses to connect keyless as a safety rail.
- **Docs:** `references/memory-honcho.md` rewritten to describe the runnable
  adapter and document the zero-config local mode.
- **Evals**: behavioral 27 -> **31** (4 brief cases: empty repo, record+progress,
  JSON output, run journal); memory 20 -> **27** (global commit+recall, global
  status, budget split, global redaction, OpenAI hyphenated key redaction,
  sk-proj/sk-test variants, entropy redaction); hook 8 -> **9** (SessionStart
  brief); honcho 0 -> **7** (fallback, dual-write, boundary redaction,
  files-only defaults, zero-config local, cloud keyless-refusal). Full suite:
  9+31+27+15+9+5+10+7 = 113 cases.

## 2.1.0

Proof layer.

- Add a tracked live Sudoku eval summary for the 2026-07-01 Codex / Claude Code /
  Droid run, where CQL averaged 89.5 vs 85.0 for baselines under two blind LLM
  judges. The docs state the one-seed and no-browser-automation caveats.
- Add `bench/` with 12 vendored benchmark tasks, objective metrics, a blind
  judge protocol, and a deterministic fixture-mode runner.
- Commit `bench/results/fixture-smoke-2026-07-01.json` as a harness smoke result.
  It validates plumbing only and is explicitly not a live agent benchmark.
- Add `evals/run_trigger_evals.py` for activation/description checks with either
  a heuristic offline judge or a caller-supplied `--judge-command`.
- Wire a benchmark fixture smoke into CI without committing generated CI output.

## 2.0.0

Driven mode core.

- Add `scripts/quality_loop_run.py`: a risk-scaled state machine with pure step
  ordering gates, orchestrator-native VERIFY, fresh-by-construction REVIEW, and
  PACKAGE reasserting the v1 `verify-gates` suite.
- Add `scripts/quality_loop_hosts.py`: `HostAdapter` protocol plus `fake`,
  `manual`, `claude`, and `codex` adapters. Fake host makes the orchestrator eval
  suite fully offline.
- Add prompt templates in `assets/prompts/`.
- Add `.quality-loop/runs/<id>/journal.jsonl` redacted local journals (gitignored).
- Add memory dogfooding: `memory-recall --no-bump` is injected into planner
  prompts; successful PACKAGE attempts a local `memory-commit`.
- Add `evals/run_orchestrator_evals.py` covering step order, transcript isolation,
  VERIFY blocking REVIEW, tiny topology, and v1 gate compatibility.
- Extend config schema/example with optional backward-compatible `hosts` and
  `execution` blocks.

## 1.6.0

Session ring + backstop + install DX.

- Add Claude Code project hook wiring in `hosts/claude-code/settings.json` plus
  stdlib shims for `PreToolUse`, `Stop`, and `SessionStart`.
- Add read-only Claude reviewer subagents:
  `.claude/agents/quality-loop-reviewer.md` and
  `.claude/agents/quality-loop-security-reviewer.md`.
- Add Codex project hook wiring in `hosts/codex/hooks.json` using the current
  Codex hook schema (`hooks.json`, command handlers, trust review via `/hooks`).
- Add git backstop: `hosts/git/install-git-hooks.py` and
  `hosts/git/.pre-commit-config.yaml` run staged `diff-audit`.
- Add `action.yml` composite action and `hosts/github/quality-loop-example.yml`.
- Add `scripts/install.py` idempotent host installer with JSON hook merging,
  backups, and an advisory/enforced wiring report.
- Add `evals/run_hook_evals.py` fixture tests for every host shim and installer
  idempotence; wire it into CI.

## 1.5.0

The "reality layer" — closes the three free lies in v1.4.0 by grounding the record in git.
A new sibling module `scripts/quality_loop_reality.py` (mirroring `quality_loop_memory.py`,
reusing `run_git`/`redact`/`SECRET_PATTERNS`/`has_evidence`/`load_json` from `quality_loop`)
adds record↔reality verification. Stdlib-only, portable, no network, no new dependencies.

- **`verify-gates --against-diff [--base REF]`** reads the real git diff and catches:
  phantom completion (package/done with an empty diff), scope integrity (changed files not
  mapped in repo_map/plan/completion_record, glob-tolerant), a **diff-derived risk floor**
  (changed paths matching auth/, payments/, migrations/, .env, terraform/, lockfiles force
  high-tier gates — grounding `detect_risk_floor` in git, not prose), bugfix-test co-presence
  (a bug/fix goal with no test in the diff and no waiver), review freshness
  (`independent_review.diff_sha256` recomputed; mismatch/missing at medium+ fails), and
  promotes diff-audit secret/test-weakening warnings to blocking at medium+.
- **`attest-review`** embeds a recomputed `git diff | sha256` into the review object — the
  reviewer's last act — so review freshness is checkable, not self-attested.
- **`run-evidence`** re-executes each recorded `commands_run[result=pass]` (allowlist
  `.quality-loop/allowed-commands`, per-command timeout, sidecar `.quality-loop/rerun-<task>.json`,
  never mutates the record). **`--red-green`** replays a `red_green: true` command in a
  `git worktree` at base (expect fail) and HEAD (expect pass) — catches a faked RED→GREEN;
  worktree unavailable → explicit "not proven", never a silent pass.
- **`diff-audit --staged`** + **`scan-text --stdin`**: pre-commit (cached) diff mode +
  secret-scan-as-a-service for host hook shims.
- **Telemetry + `stats`**: verify-gates/diff-audit/run-evidence append
  `{ts, cmd, task_id, risk, findings, pass, overrides}` to `.quality-loop/telemetry.jsonl`
  (local-only, no network; opt out with `QUALITY_LOOP_NO_TELEMETRY=1`). `stats` renders
  SKILL.md's metrics table, printing "not instrumented" for rows it can't compute.
- **Contradiction fixes:** canonicalized complexity-brake-before-PLAN across
  SKILL.md/`references/lifecycle.md`/config step order (MINIMALITY_GATE now precedes PLAN);
  fixed `assets/completion-record.md` trigger (small low-risk ships without it); bumped config
  `version` to 1.5.0; added concurrency/race/data-loss/PII to runtime `BOUNDARY_KEYWORDS`.
- **Enforcement Matrix** section in SKILL.md: every Hard Rule × its deterministic owner or an
  explicit "advisory" label — candor becomes an auditable trust artifact.
- **README claims reframe:** Sudoku presented as an honest pilot (n=1, rubric caveats, headline
  numbers removed until bench v1); Honcho/Graphify downgraded to "documented integration pattern".
- **Schema:** record gains **optional** fields only (`diff_sha256`, `files_changed`, `red_green`)
  — no adopter break; migration is additive.
- **Evals:** new `evals/run_reality_evals.py` (15 temp-git-repo fixtures where record and diff
  disagree); wired into CI. Existing 9/26/20 suites stay green.

## 1.4.0

- Add an optional, advisory **persistent per-project memory** layer: a stdlib-only files
  lessons-store (default, checked-in to `.quality-loop/memory/`) behind a backend-agnostic
  `memory-recall` / `memory-commit` / `memory-prune` / `memory-status` CLI.
- Document two optional loop-integrated backends: `honcho` (reasoning-based lessons recall)
  and `graphify` (code-graph relevance), selectable via the config `memory` block, degrading
  gracefully to the files backend.
- Memory is retrieval-not-stuffing: only a <=40-line `MEMORY.md` index auto-loads; recall is
  budget-capped and relevance-scoped. Writes are advisory (no new hard gate).
- New offline eval harness `evals/run_memory_evals.py` pins recall determinism/budget, commit
  distillation, prune, config validation, and docs presence; wired into CI.

## 1.3.2

Follow-ups from an independent max-effort review — small, in-philosophy fixes (no new subsystems).

- **Resolved a self-contradiction in the shipping gate.** `evaluate_input` (static evals) required
  a completion record for the `small` class while the runtime `verify_gates` did not — two
  definitions of "non-trivial" in one file. Aligned both: the completion-record gate fires for
  medium/mission, medium/high risk, or security-sensitive work; a small low-risk task ships with
  handoff evidence (matching its task-class description). Updated `SKILL.md`/`README.md` to match.
- **Fixed a secret-scan false negative.** The unquoted-assignment placeholder guard treated any
  value starting with `your_` as a stub, so `api_key = your_realProductionKey` was suppressed. The
  guard now anchors on exact stub words only. Added `passwd`/`pwd`/`credential`/`private_key`
  keywords to both the quoted and unquoted patterns (quoted secrets with these keywords were also
  missed).
- **De-noised the detected-risk floor.** Dropped the false-positive-prone bare words
  (`admin`, `grant`, `session`, `token`) that forced full high-risk ceremony onto benign copy/docs
  ("improve the admin dashboard copy") — the exact process theater the skill disclaims. Precise
  multi-word/domain terms are kept (`admin endpoint`, `oauth`, `rbac`, `payout`, …).
- **Right-sized the wording.** "deep validation / never a placeholder" and "shape-only placeholders
  are rejected" now accurately say required fields must be present and non-empty (shape, not
  substance); the README states plainly that `verify-gates` lints the record and `diff-audit` + CI
  are the actual block.
- **Evals:** behavioral suite 23 → **26** (small+low ships without a completion record and the two
  halves agree; secret guard flags real keys and skips only stubs; floor ignores benign common
  words). Static unchanged at 9/9.

## 1.3.0

Enforcement hardening — closes reproduced gate bypasses so "deterministic gates beat advisory
text" is actually true. All changes stay stdlib-only with offline, model-free CI.

- **Closed the self-downgrade hole (P0).** `verify-gates` derived every decision from
  agent-declared `risk_tier`/`task_class`/`security_sensitive`, so a record with goal "Disable
  auth check on admin endpoint" declared `low`/`tiny` with no evidence passed clean. New
  `detect_risk_floor` word-boundary-scans the record's own goal/criteria/plan for risk
  boundaries (auth/authz, secrets, crypto, payments, migrations, destructive, infra) and forces
  high-risk + security-review gates regardless of the declared tier. It is a curated text-scan
  heuristic — it catches honest mis-tiering, not an agent that deliberately phrases around it.
- **Fixed the flagship walkthrough (P0).** `examples/walkthrough/agent-record.json` failed the
  `verify-gates` command its own README tells you to run (missing `implementer`,
  `validation_contract`, structured `independent_review`, `completion_record`). It now passes
  both `check-record` and `verify-gates`, and CI runs both on **every** `examples/*` record so
  the showcase can never silently regress.
- **`diff-audit` sees ground truth (P0).** Untracked files (the common new-module case) were
  invisible to `git diff`, so a brand-new file with a secret returned a clean pass. They are now
  enumerated and scanned. Secret patterns broadened to the unquoted `KEY=value` shape
  (placeholder-guarded) and mainstream prefixes (`sk_live_`, `gh*_`, `github_pat_`, `ASIA`,
  `xoxb-`, `AIza`). Added a test-weakening warning (added `skip`/`xfail`/`.only` in test files).
- **Gated the UNDERSTAND verb.** Non-trivial work now requires a substantive `repo_map`
  (entry points/likely files plus callers or tests) by implementation — previously the only
  Hard Rule with no record-level enforcement.
- **Hardened artifact and command evidence.** A string artifact path must now satisfy the same
  content contract as an inline object (any existing file such as `LICENSE` no longer passes);
  command `class` is constrained to a known set; every `pass`-labeled command needs a verifiable
  evidence handle.
- **Test integrity** named as a first-class concept: a new Hard Rule and Anti-Pattern for
  RED→GREEN reproduction and not weakening/deleting tests to reach green.
- **Docs/adoption:** added a native Claude Code `.claude/skills/` install row (instruction-only
  path relabeled); normalized all documented invocations to `python3`; documented the
  `gh skill publish/install --pin` provenance path (publishing remains a maintainer step,
  provenance is not hand-faked); inlined the role→config-profile mapping in `SKILL.md`; added a
  worktree-isolation principle to mission topology; relabeled the eval suites honestly (static =
  intake-classification regression, behavioral = the gates; evidence is attested, not
  re-executed).
- **Evals:** behavioral harness grew from 15 to **23** cases (self-downgrade block + boundary-
  phrasing coverage + compliant-high pass, untracked secret, empty context map, wrong-content
  artifact, unknown command class, missing command evidence). Static suite unchanged at 9/9.
  Added opt-in trigger-eval data
  (`evals/triggers/cases.json`, should/should-NOT-trigger) kept out of offline CI by design.

## 1.2.3

- Added `references/philosophy.md` — a manifesto covering the mantra (bounded autonomy, smallest
  correct change, evidence over confidence, deterministic gates over vibes, repo maps over context
  stuffing, durable harness changes over repeated chat corrections), the problem framing (agents
  overbuild, self-attest, lose context, skip evidence, repeat mistakes), trends observed,
  inspirations (cited as influences, not endorsements or adoption claims), how the loop packages
  those ideas, and explicit non-goals.
- Rewrote the README `Philosophy` section as the seven-line mantra with a link to the full
  manifesto and the existing engineering-OS rationale.
- Docs-only change: no behavior change to `scripts/quality_loop.py`, the gates, or any asset; all
  prior validation fixes intact (9/9 static eval cases and 15/15 behavioral gate cases still pass).

## 1.2.2

- Added a root `LICENSE` file (MIT) to match the `license: MIT` declared in `SKILL.md`
  frontmatter, closing a credibility gap (claim without file).
- Rewrote `README.md` for adoption: bounded-autonomy hero/positioning, a 30-second start
  (no-install / install / orchestrated), an install-&-use matrix for Claude Code, Codex,
  Cursor, Pi, `gh skill`/generic `.agents/skills`, and standalone agents, a before/after
  example, a packaging/structure map with progressive disclosure, a runnable proof/evidence
  section, and release/pinning + trust guidance. Marketplace/`gh skill install` framed as
  conditional on a published release (no overclaiming).
- Added a lightweight, dependency-free CI workflow (`.github/workflows/evals.yml`) running
  `py_compile`, `check-config`, `eval-cases`, and `run_evals.py` on push and PR, so the
  "evals pass" claim is continuously verifiable.
- No behavior change to `scripts/quality_loop.py` or the gates; all prior validation fixes
  intact (9/9 static eval cases and 15/15 behavioral gate cases still pass).

## 1.2.1

- **Deep artifact validation** in `verify-gates`: the validation contract and completion record
  are now accepted only as a string path to a file that exists, or a complete inline object
  (goal + acceptance criteria + evidence). Shape-only placeholders (e.g. `{"placeholder":"yes"}`),
  empty strings, bare booleans/numbers, and nonexistent paths are rejected.
- **Repeated-failure → durable harness change** is now machine-checkable: new record fields
  `repeated_failure`, `repair_attempts`, and `harness_update`. When a failure recurs
  (`repeated_failure: true` or `repair_attempts >= 2`), `verify-gates` requires `harness_update`
  evidence so a clean final record cannot hide a repeated mistake corrected only in chat.
- Added the three new fields to `agent-record.schema.json` and `init-record` defaults;
  `check-record` validates their types and rejects boolean/number placeholders consistently.
- Added 4 record-gate eval cases (shallow/nonexistent artifacts fail, complete inline artifacts
  pass, existing-file path passes, repeated-failure requires harness update); 15/15 pass.
- README: corrected the lifecycle claim (8 routed machine steps vs. 2 artifact/rule-gate
  phases), added a "What the helper enforces (and does not)" section, and dropped
  `--ask-for-approval never` from the Codex one-liner.

## 1.2.0

- Reframed the skill as an **engineering operating system** (five parts: durable repo
  instructions, reusable skills, mission artifacts, independent verification, complexity
  discipline) rather than just better prompting.
- Exposed a canonical 10-step lifecycle (INTAKE -> CONTEXT MAP -> SPEC/VALIDATION CONTRACT ->
  COMPLEXITY BRAKE -> PLAN -> IMPLEMENT IN SMALL SLICES -> VERIFY -> INDEPENDENT REVIEW ->
  SHIP/HANDOFF -> RETROSPECTIVE) with stable machine-name aliases for backward compatibility.
- Added **task classes** (tiny / small / medium / mission) and scaling rules; default to the
  smallest class that is safe.
- Added a mental-model graph for mapping a change before editing.
- Expanded role architecture: `orchestrator`, `context_mapper`, `implementer`, `validator`,
  `simplicity_reviewer`, `security_reviewer`, `policy_guard`; added mission topology.
- Promoted the **complexity brake** (run before plan and before review) with explicit
  non-negotiables, and added **hard rules** and a **shipping gate** (completion record required
  for non-trivial tasks).
- Added quality gates by task type, harness implementation modes, and tool-surface guidance.
- New mission-artifact templates: `validation-contract.md`, `plan.md`, `completion-record.md`,
  `execution-log.md`, `decision-log.md`, `context-map.md`, plus a baseline `AGENTS.template.md`.
- New reference `engineering-operating-system.md` (trend synthesis, task classes, harness
  modes, tool surface, improvement loop); updated lifecycle, orchestration, reviewer, and
  tool-contract references (simplicity + security reviewer passes, security review and
  completion-record tool contracts).
- Extended the eval engine and added 5 cases: tiny-no-mission-artifacts, medium-requires-
  contract+review, security-hard-gate, complexity-brake-dependency, retrospective-harness-update
  (task_class, validation-contract/independent-review/completion-record, security reviewer,
  hard gate, and harness-update logic).
- Added a **Pi** example (`.pi/settings.json` + skill pointer) and one-line usage; README now
  covers Claude Code, Codex, Cursor, Pi, and standalone, with citations to Anthropic Agent
  Skills, Factory Missions, Aider repo map, OpenAI Agent Improvement Loop, Pi, and Codex docs.
- Bumped routing config to 1.2.0 (added orchestrator + security_reviewer profiles).

Safety hardening (runtime record gates):

- `verify-gates` now enforces the operating-system concepts against an actual agent
  record, not just the static intake derivation: non-trivial work requires a named
  `implementer`, a `validation_contract` with evidence, and an approving
  `independent_review` whose reviewer differs from the implementer; `package`/`done`
  require a `completion_record` with evidence; high-risk / `security_sensitive` work
  requires a distinct approving `security_review` artifact (a self-run `class=security`
  command no longer satisfies the gate).
- `validation_contract` / `completion_record` must be objects or non-empty
  paths/strings with evidence, never bare booleans/numbers (schema + `check-record`).
- `check-record` validates `commands_run` entry shapes and review verdicts;
  `verify-gates` handles malformed `commands_run` defensively (fails cleanly, no crash).
- Added `evals/run_evals.py`: 11 record-gate cases covering the behaviors above,
  complementing the static `eval-cases` intake-derivation suite in `evals/cases/`.

## 1.1.0

- Made the skill agentic-first: each lifecycle step can be routed to a role-based agent
  profile (`contract_agent`, `repo_mapper`, `planner`, `minimality_reviewer`, `implementer`,
  `verification_runner`, `fresh_reviewer`, `packager`, `policy_guard`).
- Added `references/agentic-orchestration.md` with the step-to-agent matrix, model-selection
  heuristics, and per-platform mapping.
- Added `assets/quality-loop.config.example.json` (+ schema) as machine-readable routing
  config, and a `check-config` helper command.
- Added an offline eval harness: `evals/` with 4 cases (low docs, medium multi-file,
  high-risk migration/security, overengineering trap) and a `eval-cases` helper command.
- Added portable examples with one-line usage for Claude Code, Codex, Cursor, and standalone
  agents, plus a real end-to-end walkthrough with a state record.
- Reworked README into adoption paths (instruction-only, skill package, orchestrated
  multi-agent, enforced production) and linked official Claude Code, Codex, and Cursor docs.
- Made agentic orchestration first-class in SKILL.md (kept under 500 lines).

## 1.0.0

- Initial release of the Coding Quality Loop skill.
- Added lifecycle instructions, review checklists, tool contracts, templates, and helper script.
