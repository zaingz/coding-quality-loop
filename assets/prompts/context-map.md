# Quality Loop Context Mapper

Goal:
{goal}

Map the change before editing. Identify entry points, callers, tests, config, contracts
touched, existing utilities to reuse, likely files to edit, and likely verification commands.
Output findings, not a repository tour.

Relevant memory:
{memory}

Return JSON for the agent record only:
- repo_map:
  - entry_points (list)
  - likely_files (list)
  - callers_checked (list)
  - tests (list)
  - patterns_to_follow (list)

Do not edit files.
