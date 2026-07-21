# Coding Quality Loop Evals

These evals validate that the skill's decision rules are coherent and that the orchestration
config is well-formed. They run fully offline — no models, no network, no external services.

## Gate suites and the canonical count

The offline **gate** suites — the ones that can fail on a real regression — total
**250 gate cases across 6 core suites**, plus **37 add-on cases** for the opt-in
control plane:

| Suite | Cases | Runner |
|---|---:|---|
| Static (intake classifier) | 20 | `quality_loop.py eval-cases evals/cases` |
| Behavioral (record gates) | 63 | `evals/run_evals.py` |
| Memory | 32 | `evals/run_memory_evals.py` |
| Reality (record ↔ diff) | 51 | `evals/run_reality_evals.py` |
| Routing | 30 | `evals/run_routing_evals.py` |
| Hook (host shims) | 54 | `evals/run_hook_evals.py` |
| **Total core gate cases** | **250** | re-run by `.github/workflows/evals.yml` |
| Control plane add-on (index, server, ingest) | 37 | `evals/run_control_evals.py` — counted separately: the add-on is installed only via `install.py --with-control-plane` and is not in the npm tarball |

The canonical numbers are **derived, not hand-set**: `canonical_gate_cases()` and
`control_addon_cases()` in [`run_evals.py`](run_evals.py) compute the totals from the
suites themselves (static `cases/*.json` + each core suite's `len(CASES)`), and a
behavioral case (`case_doc_counts_match_canonical`) fails if any public doc states a
contradicting total, a wrong per-suite breakdown addend, or a breakdown that does not
sum to the total (lines annotated "as of vX.Y" are exempt as declared-historical).
Nothing to bump when a suite's case count changes — the derived total moves with it,
and the lint tells you which docs to update.

## What they check

Each case in `cases/*.json` declares a `record` (a real agent record: goal, risk tier, task
class, plan, evidence, review) and an `expect` block. The harness runs the **production gates**
on that record — `detect_risk_floor` (which scans the goal/criteria/plan prose) and
`verify-gates` — and asserts the outcome. There is no separate static classifier to recompute,
so a case can never pass a rule the shipping gate ignores.

`expect` keys (each case asserts only the keys it declares, so cases stay focused):

- **`risk_floor`** — the floor `detect_risk_floor` derives from the record's prose
  (`low` / `medium` / `high`). A record that declares `low` but touches an auth/migration
  boundary is floored to `high`.
- **`floor_markers`** — boundary markers that must appear in the detected floor's reasoning.
- **`gates_exit`** — the `verify-gates` exit code (`0` pass, `1` fail).
- **`findings_include`** / **`findings_exclude`** — substrings that must / must not appear in
  the gate findings (e.g. a tiny task must exclude `validation_contract`; a self-downgraded
  boundary task must include the risk-floor finding).

## Run

```bash
# Validate config + run all cases
python3 scripts/quality_loop.py eval-cases evals/cases --config assets/quality-loop.config.example.json

# Run a single case
python3 scripts/quality_loop.py eval-cases evals/cases/03-high-migration-security.json
```

Exit code is non-zero if any case fails or the config check fails, so it is CI-friendly.

## Two suites: record cases vs behavioral CLI cases

- **Record cases** (`evals/cases/*.json`, run via `eval-cases`) feed a raw goal + record through
  the same `detect_risk_floor` + `verify-gates` the loop ships with, asserting the risk floor,
  gate exit code, and presence/absence of specific findings.
- **Behavioral cases** (`evals/run_evals.py`) drive the **actual CLI** (`verify-gates`,
  `check-record`, `diff-audit`) against constructed records and assert hard-to-fake behavior:
  the detected-risk floor blocks a self-downgraded boundary task, the artifact gates reject
  placeholders/wrong-content files, a pass command needs evidence, untracked secrets are
  flagged, diff-audit untracked hygiene (scaffolding excluded, unreadable surfaced, `cql:`
  markers counted), the implementer cannot be the reviewer, and `package`/`done` needs a
  completion record. One case (`case_repeated_mistake_retrospective`) is a docs-presence lint,
  not a gate test — it confirms the retrospective guidance is still documented. Two cases hold
  the project to its own candor standard: `case_doc_counts_match_canonical` fails on gate-count
  drift across the public docs, and `case_bench_validate_requires_cost_fields` proves the
  live-sweep cost validator rejects an uninstrumented run.

  Note: recorded evidence is *attested* by `verify-gates`, but `run-evidence` and
  `verify --red-green` re-execute allowlisted commands to catch lying evidence.

```bash
python3 evals/run_evals.py          # record-gate behaviors
python3 evals/run_reality_evals.py  # diff-grounded reality checks (base fallback, red/green, hashes)
python3 evals/run_routing_evals.py  # model-routing + check-config (heterogeneity, planner class)
python3 evals/run_memory_evals.py   # persistent-memory recall/commit/redaction
python3 evals/run_hook_evals.py     # policy-hook enforcement
```

## Activation (SKILL.md `description`)

There is no offline suite for the frontmatter `description` — the sole activation signal, and
the #1 skill failure mode when it is too vague (misses) or too broad (misfires). The former keyword-overlap trigger fixture was **deleted in
v6.1**: its grader's word lists were reverse-engineered from its own 10 prompts, so it
**structurally could not fail** and proved nothing about whether a changed `description` would
activate (its own docstring said so).
A real activation check needs an LLM judge, which depends on the host/model and cannot run
offline; keep that check manual — after changing the `description`, confirm on your host that a
should-trigger prompt still activates and a should-not prompt does not.

## Cases

| Case | Scenario | Floor | Key assertion |
|---|---|---|---|
| `01-simple-docs-low` | Typo / copy fix | low | minimal gates, ships (exit 0) |
| `02-medium-multifile-behavior` | Retry backoff across callers | low | complete record ships |
| `03-high-migration-security` | Declared-low migration + authz change | high | cannot downgrade the boundary; fails |
| `04-overengineering-trap` | Non-trivial work missing a minimality decision | low | fails without a right-size decision |
| `05-tiny-no-mission-artifacts` | Typo + obvious test update | low | `tiny` class needs no contract/review/record |
| `06-medium-validation-contract-review` | Multi-file feature | low | requires validation contract + independent review |
| `07-security-hard-gate` | Authz + secrets on upload path | high | security boundary triggers a distinct security review |
| `08-right-size-gate-dependency` | High-risk record with full evidence | high | complete high-risk record ships |
| `09-retrospective-harness-update` | Repeated forgotten check | low | requires a durable `harness_update` |
| `10-performance-sensitive-medium` | Independent review present | low | reviewer cannot be the implementer |
| `11-under-fanned-monolith` | Pass command without evidence | low | a `pass` command with no evidence fails |
| `12-medium-string-acs-blocked` | Medium task with bare string ACs | low | medium+ ACs need a `proving_command`; fails |
| `13-low-string-acs-pass` | Low-risk task with string ACs | low | string ACs stay valid at low risk |
| `14-blocked-with-reason-passes` | `blocked` command with a recorded reason | low | honest sandbox blocks pass |
| `15-bare-blocked-fails` | `blocked` command without a reason | low | a bare `blocked` row fails |
| `16-e2e-counts-as-executable` | e2e pass as the executable check | low | `e2e` counts as executable evidence |
| `17-proving-path-no-floor` | Boundary-looking path in a `proving_command` | low | command paths do not feed the risk floor |
| `18-tiny-boundary-risk-trumps-size` | Tiny diff touching authn | high | risk trumps size; boundary forces heavy gates |
| `19-escalation-needs-failing-check` | Escalation citing no failing check | low | self-reported escalation is not evidence |

## Add a case

Copy a file in `cases/`, change `record` and `expect`, and rerun. Keep cases small and
high-signal: one scenario, one clear expectation. The record flows through the same production
gates as a real run, so the expectation you assert is exactly what the shipping gate enforces.
