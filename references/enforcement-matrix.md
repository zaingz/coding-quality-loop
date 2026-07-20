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
