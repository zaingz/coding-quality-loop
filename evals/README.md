# Coding Quality Loop Evals

These evals validate that the skill's decision rules are coherent and that the orchestration
config is well-formed. They run fully offline — no models, no network, no external services.

## Gate suites and the canonical count

The offline **gate** suites — the ones that can fail on a real regression — total
**125 gate cases across 6 suites**:

| Suite | Cases | Runner |
|---|---:|---|
| Static (intake classifier) | 11 | `quality_loop.py eval-cases evals/cases` |
| Behavioral (record gates) | 38 | `evals/run_evals.py` |
| Memory | 26 | `evals/run_memory_evals.py` |
| Reality (record ↔ diff) | 21 | `evals/run_reality_evals.py` |
| Routing | 13 | `evals/run_routing_evals.py` |
| Hook (host shims) | 13 | `evals/run_hook_evals.py` |
| **Total gate cases** | **125** | re-run by `.github/workflows/evals.yml` |

The canonical number lives in exactly one place — `CANONICAL_GATE_CASES` in
[`run_evals.py`](run_evals.py) — and a behavioral case
(`case_doc_counts_match_canonical`) fails if any public doc states a contradicting
count. Bump the constant when a suite's case count changes.

The **10-case trigger smoke fixture** is deliberately **excluded** from this count
(see [below](#trigger-smoke-fixture-opt-in-excluded-from-the-gate-count)).

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
  test — it confirms the retrospective guidance is still documented. Two cases hold the project
  to its own candor standard: `case_doc_counts_match_canonical` fails on gate-count drift across
  the public docs, and `case_bench_validate_requires_cost_fields` proves the live-sweep cost
  validator rejects an uninstrumented run.

  Note: recorded evidence (including RED→GREEN) is *attested*, not re-executed — the checker
  grades that the evidence is present and well-formed, it does not run your test suite.

```bash
python3 evals/run_evals.py
```

## Trigger smoke fixture (opt-in, excluded from the gate count)

`triggers/cases.json` holds `should_trigger` / `should_not_trigger` prompts for the frontmatter
`description` — the sole activation signal, and the #1 skill failure mode when it is too vague
(misses) or too broad (misfires).

**Why it is a smoke fixture, not a gate.** The default grader in `run_trigger_evals.py` is a
keyword-overlap heuristic whose `coding` / `quiet` word lists were reverse-engineered from these
exact 10 prompts. It therefore **structurally cannot fail** — passing it proves nothing about
whether a changed `description` would actually activate. For that reason the fixture is
**excluded from the 125-gate-case count** and the suite is **not wired into CI**.

A **real** activation check requires an LLM judge supplied via `--judge-command` (a command that
reads `{"description", "prompt"}` on stdin and prints `true`/`false`). That is kept opt-in
because live judge grading depends on the host/model. A useful mutation test: change SKILL.md's
`description`, then confirm the `--judge-command` run can turn red — an eval that cannot fail is
not an eval.

```bash
python3 evals/run_trigger_evals.py                                       # keyword-overlap smoke (cannot fail)
python3 evals/run_trigger_evals.py --judge-command './judge-trigger.sh'  # real, LLM-judged activation check
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
| `08-right-size-gate-dependency` | New dep/abstraction for a trim | medium | right-size gate flags `overengineering` |
| `09-retrospective-harness-update` | Repeated forgotten check | medium | `harness_update` true (durable change, not a chat fix) |

## Add a case

Copy a file in `cases/`, change `input` and `expected`, and rerun. Keep cases small and
high-signal: one scenario, one clear expectation. Signals are matched against the taxonomies
in `scripts/quality_loop.py` (`LOW_SIGNALS`, `MEDIUM_SIGNALS`, `HIGH_SIGNALS`, `TINY_SIGNALS`,
`MISSION_SIGNALS`, `SECURITY_BOUNDARY_SIGNALS`), plus the `repeated_mistake` signal for the
retrospective check.
