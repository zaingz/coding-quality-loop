# Coding Quality Loop Evals

These evals validate that the skill's decision rules are coherent and that the orchestration
config is well-formed. They run fully offline — no models, no network, no external services.

## What they check

Each case in `cases/*.json` declares an `input` (goal, risk signals, proposed solution) and
the `expected` outcome. The harness recomputes the outcome from the input using the same
rules the skill prescribes, then asserts it matches `expected`:

- **Risk tier** derived from signals (`low` / `medium` / `high`).
- **Required gates** for that tier (targeted tests, fresh review, security review, rollback,
  human approval, etc.).
- **Minimality flags** — whether a proposed solution that introduces new dependencies or
  abstractions while a lower rung is available is flagged as `overengineering`.
- **Escalation** — whether the task must stop for human approval before irreversible action.

This is a static eval: it pins the routing/risk logic so changes to the rules are caught,
and it confirms the documented gates line up with the helper script.

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

## Add a case

Copy a file in `cases/`, change `input` and `expected`, and rerun. Keep cases small and
high-signal: one scenario, one clear expectation. Signals are matched against the taxonomy
in `scripts/quality_loop.py` (`LOW_SIGNALS`, `MEDIUM_SIGNALS`, `HIGH_SIGNALS`).
