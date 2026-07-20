# Quality Loop Context Mapper

Goal:
{goal}

Map the change before editing. `assets/context-map.md` is the artifact template —
follow its sections (entry points, affected surfaces, callers/consumers, patterns to
reuse, tests, likely files, verification commands). Output findings, not a repository
tour.

Relevant memory:
{memory}

Return JSON for the agent record only (the record's `repo_map` distills the map):
- repo_map:
  - entry_points (list)
  - likely_files (list)
  - callers_checked (list)
  - tests (list)
  - patterns_to_follow (list)

Do not edit files.
