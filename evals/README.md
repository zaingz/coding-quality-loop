# Coding Quality Loop Evals

These evals validate that the skill's decision rules are coherent and that the orchestration
config is well-formed. They run fully offline — no models, no network, no external services.

## What they check

Each case in `cases/*.json` declares an `input` (goal, risk signals, proposed solution) and
the `expected` outcome. The harness recomputes the outcome from the input using the same
rules the skill prescribes, then asserts it matches `expected`:

- **Risk tier** derived from signals (`low` / `medium` / `high`).
- **Task class** derived from signals (`tiny` / `small` / `medium` / `mission`) — the
  effort/blast-radius axis, orthogonal to risk tier.
- **Required gates** for that tier (targeted tests, fresh review, security review, rollback,
  human approval, etc.).
- **Minimality flags** — whether a proposed solution that introduces new dependencies or
  abstractions while a lower rung is available is flagged as `overengineering`.
- **Escalation** — whether the task must stop for human approval before irreversible action.
- **Mission-artifact requirements** — `requires_validation_contract`,
  `requires_independent_review`, `requires_completion_record`: tiny tasks require none of them;
  medium/mission tasks require all.
- **Security boundary** — `requires_security_reviewer` and `hard_gate` when the change touches
  auth, secrets, payments, PII, migrations, upload/download, network, shell, or dependencies.
- **Retrospective** — `harness_update` is true when a `repeated_mistake` signal is present, so
  the failure must become a durable harness change.

This is a static eval: it pins the routing/risk/class logic so changes to the rules are caught,
and it confirms the documented gates line up with the helper script. Each case asserts only the
keys present in its `expected` block, so cases stay focused.

## Run

```bash
# Validate config + run all cases
python scripts/quality_loop.py eval-cases evals/cases --config assets/quality-loop.config.example.json

# Run a single case
python scripts/quality_loop.py eval-cases evals/cases/03-high-migration-security.json
```

Exit code is non-zero if any case fails or the config check fails, so it is CI-friendly.

## Cases

| Case | Scenario | Tier | Key assertion |
|---|---|---|---|
| `01-simple-docs-low` | Typo / copy fix | low | minimal gates, no escalation |
| `02-medium-multifile-behavior` | Retry backoff across callers | medium | full medium gates, fresh review |
| `03-high-migration-security` | Migration + authz change | high | security review + rollback + human approval, escalate |
| `04-overengineering-trap` | New dep/abstraction for a one-liner | medium | `overengineering` minimality flag |
| `05-tiny-no-mission-artifacts` | Typo + obvious test update | low | `tiny` class needs no contract/review/record |
| `06-medium-validation-contract-review` | Multi-file feature | medium | requires validation contract + independent review + completion record |
| `07-security-hard-gate` | Authz + secrets on upload path | high | `requires_security_reviewer` + `hard_gate`, escalate |
| `08-complexity-brake-dependency` | New dep/abstraction for a trim | medium | complexity brake flags `overengineering` |
| `09-retrospective-harness-update` | Repeated forgotten check | medium | `harness_update` true (durable change, not a chat fix) |

## Add a case

Copy a file in `cases/`, change `input` and `expected`, and rerun. Keep cases small and
high-signal: one scenario, one clear expectation. Signals are matched against the taxonomies
in `scripts/quality_loop.py` (`LOW_SIGNALS`, `MEDIUM_SIGNALS`, `HIGH_SIGNALS`, `TINY_SIGNALS`,
`MISSION_SIGNALS`, `SECURITY_BOUNDARY_SIGNALS`), plus the `repeated_mistake` signal for the
retrospective check.
