---
name: test-integrity-gate
description: "Use when AI-written code or tests claim green and you need to replay the proposed test against old and current code."
license: MIT
compatibility: "Requires git and Python 3.10+. No Python packages or model-specific runtime."
---

# Test Integrity Gate

Your agent's green tests may be misleading. This gate checks whether the proposed
test command fails against old source and passes against current source. Inspect
the old failure before claiming that the test found the intended bug.

## Run

From the repository root:

```bash
python3 "<skill-root>/scripts/test_integrity.py" --base <base-ref> \
  --command "<focused test command>" --expected-red "<intended assertion failure text>"
```

Replace `<skill-root>` with this skill's installed directory. Use the merge
target or task-start commit as `<base-ref>`, not the current `HEAD`.

## Decision

- **PASS** means the command exits nonzero against base source with proposed
  test files overlaid, its captured output contains the selected literal
  `--expected-red` substring, and it exits zero in the current working tree.
  Choose a specific assertion message before replay. The marker is selected by
  the operator, so inspect the captured old output as well: a weak substring
  can still match an unrelated failure.
- **NOT_PROVEN** when the expected substring is absent or does not match,
  including missing runners, imports, dependencies, and timeouts. The JSON
  report retains the old command's exit code and output tail for diagnosis.
- **FAIL** when it passes against old source, fails now, times out, or the
  worktree cannot be built. "Not proven" never counts as success.
- Separately inspect the diff for edited expected values, weakened matchers,
  removed assertions, skips, or lower coverage thresholds. Those are review
  clues; replay is a blocking evidence check, with human inspection still
  needed to judge whether the base failure is the intended behavior.

For completion contracts, independent review, diff scope, and CI receipts, use
the full [Coding Quality Loop](https://github.com/zaingz/coding-quality-loop).
