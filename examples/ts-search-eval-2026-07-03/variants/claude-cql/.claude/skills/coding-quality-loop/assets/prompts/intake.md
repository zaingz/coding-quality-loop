# Quality Loop Intake

Goal:
{goal}

Turn this goal into a task contract. Output findings, not a repository tour.

Return JSON for the agent record only:
- goal (one sentence)
- acceptance_criteria (list)
- constraints (list)
- non_goals (list)
- assumptions (list)
- risk_tier (low|medium|high)
- task_class (tiny|small|medium|mission)
- verification_plan (list)

Ask a clarifying question only if a missing answer could change architecture, data safety,
security, cost, external side effects, or user-visible behavior. Otherwise make the smallest
safe assumption and record it.

Do not edit files.
