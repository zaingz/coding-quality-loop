# Tool Contracts for Coding Quality Loop

These contracts are building blocks for agent platforms that support tools, hooks, workers, or persistent state. Repo-map, verification, reviewer, and state tools are optional accelerators. Policy hooks are different: they are the enforcement mechanism for non-negotiable safety blocks.

## Helper Command Catalog (`scripts/quality_loop.py`)

**Primary verification (one command):**

```bash
python3 scripts/quality_loop.py verify agent-record.json --base origin/main --red-green
```

`verify` runs record-shape gates, diff-grounded reality checks, evidence re-execution, and AC-to-command coverage in one pass. If `--base` is missing or unresolvable it prints a hint and falls back (`origin/main` → `main` → `HEAD` → empty tree) so a fresh detached checkout still audits.

**Individual commands (for targeted checks):**

```bash
python3 scripts/quality_loop.py init-record --goal "Fix bug" --risk-tier medium --output agent-record.json
python3 scripts/quality_loop.py verify-gates agent-record.json --against-diff --base origin/main
python3 scripts/quality_loop.py diff-audit --base origin/main
python3 scripts/quality_loop.py run-evidence agent-record.json --red-green --base origin/main
python3 scripts/quality_loop.py attest-review review.json --base origin/main
python3 scripts/quality_loop.py brief
python3 scripts/quality_loop.py check-config assets/quality-loop.config.example.json
python3 scripts/quality_loop.py setup-models --host claude-code
python3 scripts/quality_loop.py eval-cases evals/cases --config assets/quality-loop.config.example.json
```

`diff-audit` separates **blocking** findings (secrets, test-weakening — exit 1) from **advisory** ones (dependency bump, migration touch, large diff, untracked notes, unreadable file, `cql:` shortcut markers — exit 0), so benign changes are surfaced without failing the gate.

Memory: `memory-recall`, `memory-commit`, `memory-prune`, `memory-status`.

Control plane (local observability; see `docs/control-plane.md`): `control-index`
(incremental SQLite index of host transcripts + loop artifacts under
`.quality-loop/control/`), `control-serve` (dashboard + GET-only JSON API on
127.0.0.1), `control-status`, `control-stop`, `control-ingest --event NAME`
(hook entry point; no-op unless `control_plane.enabled`, always exits 0).
Contract: the index is a disposable cache over evidence — no gate reads it.

## Tool Surface Guidance

- **Minimum:** read, search, edit, shell, run tests, `git diff` / branch / commit / PR.
- **Useful extensions:** repo-map generator, AST search, browser automation, GitHub CLI, issue
  tracker, CI logs, Sentry/Datadog logs, read-only DB access, design docs, MCP connectors.
- **MCP only when** context lives outside the repo, changes frequently, or should be repeatable
  via a tool. Add a tool only when it removes a real manual loop — not for its own sake
  ([Codex best practices](https://developers.openai.com/codex/learn/best-practices),
  [Codex customization](https://developers.openai.com/codex/concepts/customization)).

## Task Contract Tool

Purpose: Convert a high-level request into a compact implementation contract.

Input:

```json
{
  "request": "string",
  "repo_context": "optional string",
  "known_constraints": ["string"]
}
```

Output:

```json
{
  "goal": "string",
  "acceptance_criteria": ["string"],
  "constraints": ["string"],
  "non_goals": ["string"],
  "assumptions": ["string"],
  "risk_tier": "low|medium|high",
  "verification_plan": ["string"],
  "escalation_conditions": ["string"]
}
```

## Repo Map Tool

Purpose: Find the smallest relevant map of the codebase for the task.

Suggested implementation:

- `git grep` for entry points and identifiers.
- Language server symbol lookup.
- Import graph or AST index.
- Test filename and fixture mapping.
- Config and route discovery.

Output:

```json
{
  "entry_points": ["path:symbol"],
  "likely_files": ["path"],
  "callers_checked": ["path:symbol"],
  "tests": ["path or command"],
  "patterns_to_follow": ["string"],
  "contracts": ["api/schema/config/doc"]
}
```

## Minimality Gate Tool

Purpose: Force the agent to choose the smallest correct solution before implementation.

Output:

```json
{
  "rung": "skip|delete|reuse|stdlib|native|existing_dependency|one_liner|minimal_new_code",
  "reason": "string",
  "rejected_lower_rungs": [
    {"rung": "string", "why_not": "string"}
  ],
  "safety_exceptions_checked": ["security", "validation", "authorization", "accessibility", "data_loss"]
}
```

## Verification Runner

Purpose: Execute allowed checks and capture evidence.

Command classes:

- `format`
- `lint`
- `typecheck`
- `unit`
- `integration`
- `e2e`
- `security`
- `build`
- `migration_dry_run`

Output:

```json
{
  "commands_run": [
    {
      "cmd": "string",
      "class": "unit|integration|typecheck|build|lint|format|security|e2e|migration_dry_run",
      "result": "pass|fail|blocked",
      "evidence": "short output or artifact reference"
    }
  ],
  "blocked_reason": "optional string"
}
```

## Policy Hook

Purpose: Block or require approval for commands and diffs that exceed the agent’s authority.

Block or escalate:

- Secrets or credentials in diffs.
- Production credentials, deploys, or destructive infrastructure commands.
- Data deletion, irreversible migrations, or payment side effects.
- New dependencies without justification.
- Large diffs beyond a configured threshold.
- Network calls from tests unless allowed.
- Completion claims for non-trivial tasks with no completion record (the shipping gate).

## Security Review Tool

Purpose: Boundary-only review for changes touching auth, permissions, secrets, payments, PII, migrations, upload/download, network, shell, or dependencies.

Input:

```json
{
  "diff": "string",
  "risk_boundaries": ["authn", "authz", "secrets", "payments", "pii", "migration", "upload_download", "network", "shell", "dependency_change"],
  "validation_contract": {}
}
```

Output:

```json
{
  "verdict": "approve|block|needs_human",
  "findings": [
    {"severity": "blocking|major|minor", "boundary": "string", "finding": "string", "suggested_fix": "string"}
  ]
}
```

## Completion Record Tool

Purpose: Enforce the shipping gate — non-trivial tasks cannot claim completion without a record.

Output:

```json
{
  "task_class": "tiny|small|medium|mission",
  "acceptance_criteria_met": [{"criterion": "string", "met": true, "evidence": "string"}],
  "files_changed": ["path"],
  "minimality_decision": {"rung": "string", "reason": "string"},
  "verification_evidence": [{"cmd": "string", "result": "pass|fail|blocked", "evidence": "string"}],
  "independent_review": {"reviewer": "string", "verdict": "approve|request_changes|needs_discussion"},
  "security_review": {"verdict": "approve|block|needs_human|not_applicable"},
  "open_risks": ["string"],
  "rollback": "string",
  "retrospective_harness_change": "string|null"
}
```

A completion claim with `task_class != tiny` and no completion record should be blocked by the policy hook.

## Reviewer Agent

Purpose: Fresh-context review of contract, plan, diff, and evidence.

Inputs:

```json
{
  "task_contract": {},
  "plan": ["string"],
  "minimality_decision": {},
  "diff": "string",
  "verification_evidence": [],
  "risk_tier": "low|medium|high"
}
```

Output:

```json
{
  "verdict": "approve|request_changes|needs_discussion",
  "findings": [
    {
      "severity": "blocking|major|minor|nit",
      "area": "contract|tests|security|minimality|integration|reliability|performance|style",
      "finding": "string",
      "suggested_fix": "string"
    }
  ],
  "missing_evidence": ["string"],
  "simpler_alternative": "optional string"
}
```
