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
python3 scripts/quality_loop.py eval-cases evals/cases --config assets/quality-loop.config.example.json

# Run a single case
python3 scripts/quality_loop.py eval-cases evals/cases/03-high-migration-security.json
```

Exit code is non-zero if any case fails or the config check fails, so it is CI-friendly.

## Two suites: static (classifier) vs behavioral (gates)

- **Static cases** (`evals/cases/*.json`, run via `eval-cases`) pin the **intake
  classification** — they recompute `evaluate_input` from declared signals and assert risk
  tier, task class, required gates, and security boundary. They are regression tests for the
  routing table, not proof that a gate fires on real prose.
- **Behavioral cases** (`evals/run_evals.py`) drive the **actual CLI** (`verify-gates`,
  `check-record`, `diff-audit`) against constructed records and assert hard-to-fake behavior:
  the detected-risk floor blocks a self-downgraded boundary task, the artifact gates reject
  placeholders/wrong-content files, a pass command needs evidence, untracked secrets are
  flagged, the implementer cannot be the reviewer, and `package`/`done` needs a completion
  record. One case (`case_repeated_mistake_retrospective`) is a docs-presence lint, not a gate
  test — it confirms the retrospective guidance is still documented.

  Note: recorded evidence (including RED→GREEN) is *attested*, not re-executed — the checker
  grades that the evidence is present and well-formed, it does not run your test suite.

```bash
python3 evals/run_evals.py
```

## Trigger evals (opt-in, not in CI)

`triggers/cases.json` holds `should_trigger` / `should_not_trigger` prompts for the frontmatter
`description` — the sole activation signal, and the #1 skill failure mode when it is too vague
(misses) or too broad (misfires). Grading these needs a model (LLM-judge), so they are
**deliberately excluded from the offline, model-free CI suite**. To run them, feed your host's
judge only the `description_under_test` plus each prompt and check the label. Validate the JSON:

```bash
python3 -c "import json; json.load(open('evals/triggers/cases.json'))"
```

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
