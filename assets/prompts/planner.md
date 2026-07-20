# Quality Loop Planner

Goal:
{goal}

Risk:
{risk_tier}

Relevant memory:
{memory}

Plan the smallest correct change as reviewable, testable, revertible slices.

Return JSON updates for the agent record only:
- slices: list of implementation slices, each independently reviewable and revertible
- verification: list of the commands that will prove each slice (feeds verification_plan)
- rollback: how to undo the change if it ships broken
- escalation_conditions: list of findings that would require stopping for human input

Do not edit files.
