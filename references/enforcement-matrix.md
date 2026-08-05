# Enforcement Matrix

Every Hard Rule in `SKILL.md` maps to a deterministic owner (a script you can run)
or an explicit **advisory** label. This is the trust artifact that says where the
machine stops and the human/host begins.

`verify-gates` reads the record; `verify-gates --against-diff` and `diff-audit`
read git; `run-evidence` re-executes commands. Blocking findings print with an
`error:` prefix and advisories with `note:` (`warning:` is no longer emitted);
exit codes are the machine contract. Shipped host hooks (PreToolUse / Stop)
enforce the deterministic blocks at tool time.

| Hard Rule | Deterministic owner | Advisory where not deterministic |
|---|---|---|
| Understand before editing | `verify-gates` (repo_map gate) + `--against-diff` (scope integrity) | context-map quality is advisory |
| Write down "done" first | `verify-gates` (validation_contract required for non-trivial; at medium+ each acceptance criterion must be an object with a `proving_command` matching a pass-labeled `commands_run` entry — enforced in `verify-gates` itself, so it fires at the host Stop gate) | contract substance is advisory; >=3 criteria sharing one proving_command is advisory |
| Prefer existing code | `verify-gates` (minimality_decision required) | rung choice is advisory; "possible under-fanning" (medium+ with >300 added LOC, >=90% in one new source file) is advisory in `verify` |
| Implementer cannot be the final validator | `verify-gates` (reviewer != implementer string-compare) + `check-config` (model heterogeneity on medium+) | fresh_context is self-attested |
| No success claim without evidence | `verify-gates` (evidence handle required; blocked `commands_run` rows must carry a non-empty `reason`/`rationale` — a bare blocked row blocks) + `run-evidence` (re-execution) + `--against-diff` (phantom completion) | evidence substance beyond re-execution is advisory |
| Don't game the tests | `--against-diff` (bugfix-test co-presence; net test-declaration/assertion loss — deleted or gutted tests, netted diff-level so moves stay green — blocks at medium+) + `run-evidence --red-green` + `diff-audit` (test-weakening blocking; test shrinkage advisory) | test coverage of the contract is advisory. The test-weakening/shrinkage lexicons are deterministic for Python, JS/TS, Go, Rust, Java, Ruby, and C#, but weakening detection fires only for files a path marker recognizes as tests (`TEST_PATH_MARKERS` = test/spec/__tests__, plus `tests.path_markers`). Go `_test.go` and most `test/`-dir suites match; a language whose unit tests live inside source files — notably Rust `#[test]` in `src/` — is covered only when `src/` is added as a `tests.path_markers` entry. A test outside any recognized test path, or in any other language, is advisory-only. |
| Stop at risk boundaries | `detect_risk_floor` (text scan of goal/criteria/plan; object ACs contribute `criterion` text only) + `--against-diff` (diff-derived path floor) | whether to escalate to a human is advisory |
| Delete when deletion is simplest | `verify-gates` (minimality_decision.rung) | whether deletion was considered is advisory |

Two SKILL.md imperatives have no deterministic owner and are **advisory** by design:

| SKILL.md imperative | Deterministic owner | Advisory where not deterministic |
|---|---|---|
| Re-run the right-size gate on the final diff before attestation | none | advisory — no gate compares the pre- and post-attestation rung; `verify` emits only a "possible under-fanning" advisory |
| Product floor (keyboard operable, labeled inputs, no `prompt()`/`confirm()` primary flows) | none | advisory — the reviewer checklist prompts for it, but no gate measures product fitness |

Records may carry optional `diff_sha256` (attest-review), `files_changed`
(completion record), and `red_green` (commands_run) fields.

## Version trust chain (`check-version`)

A project whose brand is checkable claims must be able to prove its own release
surface. `check-version` asserts that every shipped version surface agrees:
`packages/npm/package.json`, the `SKILL.md` frontmatter, the README version
badge, and the shipped GitHub example's action ref — plus the latest git tag.

- **File-to-file drift is always an error** (exit 1), locally and in CI: those
  four files ship together, and the badge and the example ref have shipped stale
  before (caught in the v6.5.0 review).
- **A tag that lags the files is a warning**, not an error: between releases main
  legitimately sits ahead of the newest tag. The tag leg is hard-enforced only on
  a release-framed CI event — a push to `main`, a tag push, or a published
  release (`_ci_enforces_tag`) — or when `--enforce-tag` is passed explicitly.
- **No tags at all is always a warning**: a shallow or fresh clone has none, and
  that is a clone artifact, not a release-surface defect.
- **The tag is read from the repo the files are read from.** File surfaces come
  from the CQL repo root, so `git tag` runs with that root as cwd: invoked from
  another directory the check no longer reports the caller's tags (or, outside any
  repo, a spurious "no tags").
- **Only release tags count** (`^v?\d+\.\d+\.\d+$`). `--sort=-v:refname` ranks
  `v6.7.0-rc1` and foreign namespaces like `skill-v9.9.9` above the real latest
  release; comparing shipped files against one of those is a false mismatch.

`.github/workflows/version-trust.yml` runs the check on PRs (advisory tag leg)
and on main/tag/release events (enforced), with `fetch-depth: 0` so tags exist.
Overlap, stated plainly: `evals/run_evals.py::case_release_version_parity`
already pins the same four *file* surfaces in-tree. `check-version` adds the tag
leg, the release-event enforcement, and a portable command a consumer repo can
run; folding the eval onto it is a follow-up, not a claim made here.

## Complexity delta (advisory, `diff-audit`)

`diff-audit` scores each changed `.py` file's functions with stdlib `ast`
(cyclomatic complexity; nested functions and classes are pruned so a closure is
not charged to its parent twice). A function whose score grows by at least
`diff_audit.complexity_delta` (config, default 5) earns an **advisory** line;
new functions are measured against a straight-line baseline of 1.

Which two sides are compared follows the mode, so the audit always describes the
change it claims to:

| mode | pre-change side | post-change side |
| --- | --- | --- |
| `--base REF` | blob at `REF` | working tree file |
| `--staged` | blob at `HEAD` | **index blob** (`git show :path`) |

`--staged` is pre-commit mode, so it reads the staged content; unstaged edits on
top are deliberately invisible to it.

Advisory only, and deliberately so: a real feature legitimately adds branches,
and `diff-audit` does not know the risk tier. The pre-commit hook keys off the
exit code, so this never blocks a commit. Unparsable or unreadable files are
silent rather than guessed at, and a path that is **absent at the base ref** (any
newly added file) reads as empty **quietly** — git's `fatal: path ... does not
exist` never reaches stderr, so a clean advisory run has clean output.

## Delegation ledger advisories

When `.quality-loop/delegations.jsonl` is present (most repos have none, so this
no-ops), ledger-grounded checks run inside `collect_gate_findings`, the same
structured entry point `verify-gates`, `verify`, and `eval-cases` all consume. A
malformed or half-flushed ledger is skipped, never crashing a gate.

- **Brief size** is **advisory only**. Each ledger entry's brief size
  (`brief_chars` if logged, else `len(brief_summary)`) is compared to
  `delegation.brief_char_limit` (config, default 4000). Over the ceiling emits a
  non-blocking `note:` in `verify-gates` and `control-report`; it never fails a
  gate. An oversized hand-off brief signals context bloat, not a rule violation.
  `brief_chars` has a shipped producer — `log-delegation --brief-file <brief>`
  appends the row and records `len(full_brief)` — so the measurement comes from
  the brief itself rather than from the truncated summary.
- **Review isolation** (`isolation_evidence`, medium+ only) is graded, because
  the record cannot prove its own independence. Resolution is **task-scoped and
  fail-advisory**:
  - the task id is `isolation_evidence.task_id`, or the **record's own
    `task_id`** when the evidence omits it. Reviewer *and* implementer are
    resolved only from ledger rows carrying that id — the ledger is append-only,
    so unrelated historical tasks must never be compared against;
  - `role` must be a **non-empty string** (and `task_id`, when present, likewise).
    Shape is validated **before** any lookup, so malformed evidence can never
    resolve to an arbitrary row;
  - resolves to a same-task row whose **recorded** host or model family differs
    from the implementer's -> **silent** (independence is grounded);
  - resolves to a same-task row where **both hosts are recorded and equal AND
    both model families resolve and are equal** -> the **only blocking
    finding**: the ledger does not ground the review as isolated;
  - everything else -> **advisory**, never blocking: evidence absent, non-object,
    blank/wrong-typed selectors, an unknown task, no matching role row, several
    rows with conflicting host/model for the same role (ambiguity is never
    resolved by picking one), an unrecorded implementer, or a host/family that is
    **unknown on either side** (unknown is not "the same").

  Scope honestly stated: this compares *recorded identities in the ledger*, not
  runtime process isolation. It raises the cost of a false independence claim
  from zero to "forge a matching same-task ledger line"; it is not proof of a
  fresh context.

## Helper integrity

The helper itself is a file in the workspace, and a live eval (webapp,
2026-07-07) showed an agent softening its local copy of `quality_loop.py` and
then reporting a verify PASS against the weakened gate. `verify` therefore
prints a `helper-integrity` section: the sha256 of each helper module as
installed. The helper cannot police itself (a tampered copy could lie), so the
check is **externally owned**: a git hook or CI step compares the printed
hashes (or hashes the files directly) against the pinned release. Attestation
hashes exclude `.quality-loop/` so record-only follow-up commits do not stale
an attested review; any code edit after attestation still requires re-attesting.

The shipped PreToolUse hook adds a runtime layer: with `protect_harness` on
(the consumer default; this repo's own config sets it false because here the
gate scripts are the workpiece under constant edit), edits to the helper
scripts, hook shims, and the canonical config — plus `rm` of the record/config
— are denied at tool time. The active record is deliberately NOT in the
edit-deny set: the lifecycle requires the agent to mutate its record
continuously, and record integrity comes instead from the freshness hash,
`verify` recomputation, and the CI anchor. This is tamper evidence, not
immutability: it raises the cost of the quiet soften-the-gate move; the
externally owned hash comparison remains the backstop.

The **sanctioned mutation path** for the record is the `record` CLI
(`record set-status`, `add-evidence`, `add-ac`, `outcome`): each does an
atomic, schema-validated write that preserves unknown fields, so an agent can
advance status or append evidence without hand-editing JSON and without a Bash
heredoc. It exists precisely because the record stays outside the edit-deny set
— structured writes are safer than free-form edits, but neither is denied at
tool time; the gates reason over the resulting record, not over how it was
written.

## Smart Stop gate (skip re-execution when already verified)

At a terminal status (`package`/`done`) the Stop hook runs the full `verify`
umbrella, which re-executes recorded evidence. Two allow-and-skip shortcuts
keep that from firing needlessly, and **both fail safe toward running the
umbrella**:

- **Closed record.** A committed record byte-identical to its base with a clean
  tree is a merged/cloned artifact — the stop is allowed without re-execution.
- **Fresh `last-verified` marker.** When the `verify` umbrella passes it writes
  `.quality-loop/last-verified.json` (`diff_sha256`, `record_sha256`, `base`,
  `status`, `verified_at`). On the next terminal stop, if the marker's diff hash
  (the same canonical diff attest-review and review-freshness use), the record
  content hash, **and** status all match the current state, the umbrella is
  skipped with a one-line stderr note. Any mismatch, missing/unreadable marker,
  or hashing failure runs the full umbrella exactly as before. The `record_sha256`
  is load-bearing: the umbrella verdict depends on the record (it re-executes
  `commands_run` and checks AC coverage) and the record lives under
  `.quality-loop/`, which the canonical *diff* excludes — so without binding the
  record content a post-verify `record add-evidence` could flip the umbrella to
  FAIL while the diff hash still matched. Scope, honestly: this skips
  re-execution only when nothing changed since a passing verify. Like every
  local gate input, the marker is a plain file an agent can write, so it is not
  a boundary against a *forging* agent (which could equally rewrite the record
  it attests) — it is tamper-evident, not immutable, exactly like the rest of
  the local surface. CI (which never reads the marker) re-executes
  unconditionally and remains the anchor.
