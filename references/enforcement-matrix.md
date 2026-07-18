# Enforcement Matrix

Every Hard Rule in `SKILL.md` maps to a deterministic owner (a script you can run)
or an explicit **advisory** label. This is the trust artifact that says where the
machine stops and the human/host begins.

`verify-gates` reads the record; `verify-gates --against-diff` and `diff-audit`
read git; `run-evidence` re-executes commands. Host hooks remain a documented
integration point, not a shipped dependency.

| Hard Rule | Deterministic owner | Advisory where not deterministic |
|---|---|---|
| Understand before editing | `verify-gates` (repo_map gate) + `--against-diff` (scope integrity) | context-map quality is advisory |
| Write down "done" first | `verify-gates` (validation_contract required for non-trivial) | contract substance is advisory |
| Prefer existing code | `verify-gates` (minimality_decision required) | rung choice is advisory |
| Implementer cannot be the final validator | `verify-gates` (reviewer != implementer string-compare) + `check-config` (model heterogeneity on medium+) | fresh_context is self-attested |
| No success claim without evidence | `verify-gates` (evidence handle required) + `run-evidence` (re-execution) + `--against-diff` (phantom completion) | evidence substance beyond re-execution is advisory |
| Don't game the tests | `--against-diff` (bugfix-test co-presence) + `run-evidence --red-green` + `diff-audit` (test-weakening) | test coverage of the contract is advisory |
| Stop at risk boundaries | `detect_risk_floor` (text scan) + `--against-diff` (diff-derived path floor) | whether to escalate to a human is advisory |
| Delete when deletion is simplest | `verify-gates` (minimality_decision.rung) | whether deletion was considered is advisory |
| Release claims must be checkable | `check-version` (npm package == SKILL.md == latest git tag) | — |

Records may carry optional `diff_sha256` (attest-review), `files_changed`
(completion record), and `red_green` (commands_run) fields.

## Version trust chain (`check-version`)

For a project whose brand is checkable claims, the release surface itself passes
a gate. `check-version` asserts three versions agree: the npm package
(`packages/npm/package.json`), the `SKILL.md` frontmatter, and the latest git
tag.

- **package.json ↔ SKILL.md** mismatch is a **hard failure everywhere** — they
  ship together.
- **git tag** mismatch is a **local warning** but a **hard failure on
  release-framed CI** (a push to `main`, a tag, or a published release, detected
  via `GITHUB_ACTIONS` + `GITHUB_REF`/`GITHUB_EVENT_NAME`). A tag that lags the
  files between releases is expected and must not block a feature PR; the CI
  workflow runs the check on every build but only enforces the tag leg on
  main/release events. A missing tag (fresh/shallow clone) is always a warning.

## Delegation ledger advisories

When `.quality-loop/delegations.jsonl` is present (most repos have none, so these
no-op), two ledger-grounded checks run. Both are read by `verify-gates`; a
malformed or half-flushed ledger is skipped, never crashing a gate.

- **Brief size** is **advisory only**. Each ledger entry's brief size
  (`brief_chars` if logged, else `len(brief_summary)`) is compared to
  `delegation.brief_char_limit` (config, default 4000). Over the ceiling emits a
  non-blocking `note:` in `verify-gates` and `control-report`; it never fails a
  gate. An oversized hand-off brief signals context bloat, not a rule violation.

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
