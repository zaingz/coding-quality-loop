# Standalone / Custom Agent Runbook

Use this when you orchestrate the loop yourself (a script, a workflow engine, or a custom
multi-agent runtime) instead of a packaged agent platform.

## One-line usage

```bash
python scripts/quality_loop.py eval-cases evals/cases --config assets/quality-loop.config.example.json
```

That single command validates the routing config and runs the offline evals — a good smoke
test before wiring real models.

## Wire the steps

Model each lifecycle step as a workflow node. Route each node to a profile from
`assets/quality-loop.config.example.json` (replace the `<...>` model placeholders with your
provider's identifiers):

| Step | Profile | Model class | Independent? |
|---|---|---|---|
| INTAKE | `contract_agent` | cheap/fast | no |
| EXPLORE | `repo_mapper` | cheap/fast | no |
| PLAN | `planner` | strong reasoning | no |
| MINIMALITY_GATE | `minimality_reviewer` | strong reasoning | no |
| IMPLEMENT_SLICE | `implementer` | code-specialized | no |
| VERIFY | `verification_runner` | cheap/fast + exec | no |
| REVIEW | `fresh_reviewer` | strong reasoning | **yes** |
| PACKAGE | `packager` | cheap/fast | no |
| (all) | `policy_guard` | deterministic hook | enforced |

Tool contracts for each node (repo-map, verification runner, reviewer, policy hook) are in
`references/tool-contracts.md`.

## Minimal loop in pseudocode

```python
contract   = contract_agent.run(goal)                 # INTAKE
repo_map   = repo_mapper.run(contract)                # EXPLORE
plan       = planner.run(contract, repo_map)          # PLAN
minimality = minimality_reviewer.run(plan)            # MINIMALITY_GATE
diff       = implementer.run(plan, minimality)        # IMPLEMENT_SLICE
evidence   = verification_runner.run(diff, contract)  # VERIFY
review     = fresh_reviewer.run(contract, diff, evidence)  # REVIEW (separate session)
handoff    = packager.run(contract, diff, evidence, review)  # PACKAGE

# policy_guard is a deterministic hook on every exec/edit, not a model.
```

## Evidence gate before handoff

```bash
python scripts/quality_loop.py init-record --goal "<goal>" --risk-tier medium --output agent-record.json
# ... fill the record as the loop runs ...
python scripts/quality_loop.py diff-audit --base origin/main
python scripts/quality_loop.py verify-gates agent-record.json
```

Start with one implementer + one independent reviewer + a policy hook. Add specialized agents
only when risk or complexity justifies the coordination cost.
