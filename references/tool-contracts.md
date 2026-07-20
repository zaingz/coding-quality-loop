# Tool Contracts for Coding Quality Loop

This file is the helper command catalog plus the record shapes the shipped subcommands
actually consume. Policy hooks are the enforcement mechanism for non-negotiable safety
blocks; everything else here is evidence tooling.

## Helper Command Catalog (`scripts/quality_loop.py`)

**Primary verification (one command):**

```bash
python3 scripts/quality_loop.py verify .quality-loop/agent-record.json --red-green
```

`verify` runs record-shape gates, diff-grounded reality checks, evidence re-execution, and
AC-to-command coverage in one pass.

- `--base` defaults to **auto**: the merge-base of the first resolvable ref in the
  `origin/main` → `origin/master` → `main` → `master` → `HEAD` ladder and `HEAD` (empty tree
  as last resort), so committed-but-unpushed work stays in the diff. Precedence: an explicit
  `--base` flag wins, then the `QUALITY_LOOP_BASE` env var, then the config `base` key, then the
  auto ladder. `verify-gates` and `render-prompt` share this auto default; `diff-audit`,
  `run-evidence`, and `attest-review` keep a `--base` default of `HEAD`.
- `--timeout <seconds>` bounds each evidence re-execution; precedence is `--timeout` >
  `QUALITY_LOOP_TIMEOUT` env > default 120. (The standalone `run-evidence` subcommand keeps
  its own `--timeout` default of 30 and does not read `QUALITY_LOOP_TIMEOUT`.)
- `--require-terminal` fails when the diff vs base is non-empty while the record status is
  not `package`/`done`.

**Gate configuration (exactly three keys).** The gates read three keys from the canonical root
`quality-loop.config.json`, and these three are the complete, deliberate gate-config surface —
everything else about the gates is intentionally not configurable:

- `base` — seeds the base-resolution ladder above (overridden by `QUALITY_LOOP_BASE`, then by an
  explicit `--base`).
- `tests.path_markers` — the path fragments that mark a file as a test, so a repo whose tests
  live under `evals/` or `spec/` gets the bugfix-test and test-shrinkage gates. Point markers at
  real test/fixture paths only: a marked file that *embeds* weakening-marker strings (say, a
  test harness whose fixtures contain `t.Skip` or `.only`) will trip the weakening gate on its
  own fixtures.
- `high_risk_paths` — extra path prefixes that force the diff-derived risk floor, for a repo
  whose auth/payments code lives outside the built-in defaults.

**Individual commands (for targeted checks):**

```bash
python3 scripts/quality_loop.py init-record --goal "Fix bug" --risk-tier medium --output .quality-loop/agent-record.json
python3 scripts/quality_loop.py check-record .quality-loop/agent-record.json --strict
python3 scripts/quality_loop.py verify-gates .quality-loop/agent-record.json --against-diff
python3 scripts/quality_loop.py diff-audit --base origin/main
python3 scripts/quality_loop.py run-evidence .quality-loop/agent-record.json --red-green --base origin/main
python3 scripts/quality_loop.py attest-review review.json --base origin/main
python3 scripts/quality_loop.py render-prompt --role reviewer --record .quality-loop/agent-record.json
python3 scripts/quality_loop.py scan-text --stdin
python3 scripts/quality_loop.py brief
python3 scripts/quality_loop.py check-config assets/quality-loop.config.example.json
python3 scripts/quality_loop.py setup-models --host claude-code
python3 scripts/quality_loop.py eval-cases evals/cases --config assets/quality-loop.config.example.json
```

- `check-record` validates the record shape: object acceptance criteria, the minimality rung
  enum, statuses, and the optional `reason`/`rationale` fields on blocked `commands_run` rows
  (optional, but must be non-empty strings when present).
- `verify-gates` prints blocking findings with an `error:` prefix and advisories with `note:`
  (`warning:` is no longer emitted). AC-to-command coverage runs inside `verify-gates` itself
  — so it fires at the host Stop gate and in CI loops, not only under the `verify` umbrella.
  At medium+ (risk tier or task class, or `security_sensitive`) every `acceptance_criteria`
  entry must be an object `{"criterion": ..., "proving_command": ...}` whose `proving_command`
  matches a pass-labeled `commands_run` entry; bare strings block. Strings stay valid at low
  risk. Advisory (never blocking): >=3 criteria sharing one identical proving_command.
  `commands_run` rows with `result: "blocked"` pass only when they carry a non-empty `reason`
  (or `rationale`) string; a bare blocked row fails.
- `verify-gates --against-diff` adds the reality layer: phantom completion, scope integrity,
  diff-derived risk floor, review freshness — and **net test-declaration/assertion loss**
  (deleted or gutted tests, netted diff-level so test moves stay green), which blocks at
  medium+. `diff-audit` reports the same test-shrinkage signal as advisory. `verify` also
  emits a "possible under-fanning" advisory when a medium+ task adds >300 LOC with >=90% in
  one new source file.
- `diff-audit` separates **blocking** findings (secrets, test-weakening — exit 1) from
  **advisory** ones (dependency bump, migration touch, large diff, untracked notes, unreadable
  file, `cql:` shortcut markers, test shrinkage — exit 0).
- `run-evidence` re-executes recorded pass commands from the allowlist file
  `.quality-loop/allowed-commands`: **one command per line, matched exactly against the
  recorded `cmd` string; `#` lines are comments; glob (fnmatch) patterns are allowed.** A
  command not on the allowlist is reported, never silently run.
- `render-prompt --role reviewer|security-reviewer --record <record.json> [--base REF]`
  substitutes `{contract}`/`{diff}`/`{evidence}` into `assets/prompts/<role>.md` and prints to
  stdout — pipe it to the reviewing CLI (see `docs/cross-cli-recipe.md`).
- `scan-text --stdin` secret-scans text for host hook shims.

Memory: `memory-recall`, `memory-commit`, `memory-prune`, `memory-status` (see
`references/memory.md`).

**Control plane (opt-in add-on only).** Installed only via
`python3 scripts/install.py --with-control-plane`; on a default install the `control-*`
subcommands are absent from `--help` and rejected by argparse. See `docs/control-plane.md`.

- `control-index` — incremental SQLite index of host transcripts + loop artifacts under
  `.quality-loop/control/`.
- `control-serve` — dashboard + GET-only JSON API on 127.0.0.1.
- `control-status`, `control-stop` — server/DB state and shutdown.
- `control-ingest --event NAME` — hook entry point; no-op unless `control_plane.enabled`,
  always exits 0.
- `control-report --task-id <id>` — per-task audit bundle (goal, rung, plan, delegations,
  verdicts+findings, spend, sessions) as markdown or JSON; `control-report --arm-costs
  [--since ISO-TS]` emits per-session `tokens_in`/`tokens_out`/`duration_sec` JSON.

Contract: the index is a disposable cache over evidence — no gate reads it.

## Tool Surface Guidance

- **Minimum:** read, search, edit, shell, run tests, `git diff` / branch / commit / PR.
- **Useful extensions:** repo-map generator, AST search, browser automation, GitHub CLI, issue
  tracker, CI logs, Sentry/Datadog logs, read-only DB access, design docs, MCP connectors.
- **MCP only when** context lives outside the repo, changes frequently, or should be repeatable
  via a tool. Add a tool only when it removes a real manual loop — not for its own sake
  ([Codex best practices](https://developers.openai.com/codex/learn/best-practices),
  [Codex customization](https://developers.openai.com/codex/concepts/customization)).

## Task Contract Shape

The contract slice of the agent record, as created by `init-record` and validated by
`check-record`/`verify-gates` (full schema: `assets/agent-record.schema.json`):

```json
{
  "goal": "string",
  "acceptance_criteria": [
    {"criterion": "string", "proving_command": "string (required at medium+; bare strings ok at low risk)"}
  ],
  "constraints": ["string"],
  "non_goals": ["string"],
  "assumptions": ["string"],
  "risk_tier": "low|medium|high",
  "task_class": "tiny|small|medium|mission",
  "verification_plan": ["string"]
}
```

## Verification Evidence Shape

The `commands_run` rows `verify-gates` checks and `run-evidence` re-executes:

```json
{
  "commands_run": [
    {
      "cmd": "string",
      "class": "unit|integration|typecheck|build|lint|format|security|e2e|migration_dry_run",
      "result": "pass|fail|blocked",
      "evidence": "short output or artifact reference",
      "reason": "required (or 'rationale') when result is blocked: why the command could not run"
    }
  ]
}
```

`unit`, `integration`, `typecheck`, `build`, `e2e`, `security`, `format`, and
`migration_dry_run` all count as executable evidence for the medium/high "relevant executable
check" rules.

## Policy Hook

Purpose: Block or require approval for commands and diffs that exceed the agent's authority.
Shipped host hooks (see `references/enforcement-matrix.md`) block or escalate:

- Secrets or credentials in diffs.
- Production credentials, deploys, or destructive infrastructure commands (including
  sudo-wrapped forms, `git checkout -- <path>`, and force pushes).
- Data deletion, irreversible migrations, or payment side effects.
- Tampering with the harness itself (`protect_harness`, default on): edits to the helper
  scripts, hook shims, the active record, or the canonical config are denied — tamper
  evidence, not immutability.
- Completion claims for non-trivial tasks with no completion record (the shipping gate).
