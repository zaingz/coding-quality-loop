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

Records may carry optional `diff_sha256` (attest-review), `files_changed`
(completion record), and `red_green` (commands_run) fields.
