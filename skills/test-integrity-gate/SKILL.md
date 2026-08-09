---
name: test-integrity-gate
description: "Use when AI-written code or tests claim green and you need deterministic proof that the new test catches the old bug."
license: MIT
compatibility: "Requires git and Python 3.10+. No Python packages or model-specific runtime."
---

# Test Integrity Gate

Your agent's green tests may be lying. This gate checks the important question:
**does the proposed test fail against the old code?**

## Run

From the repository root:

```bash
python3 "<skill-root>/scripts/test_integrity.py" --base <base-ref> --command "<focused test command>"
```

Replace `<skill-root>` with this skill's installed directory. Use the merge
target or task-start commit as `<base-ref>`, not the current `HEAD`.

## Decision

- **PASS** only when the command fails against the base source with the proposed
  test files overlaid, then passes in the current working tree.
- **FAIL** when it passes against old source, fails now, times out, or the
  worktree cannot be built. "Not proven" never counts as success.
- Separately inspect the diff for edited expected values, weakened matchers,
  removed assertions, skips, or lower coverage thresholds. Those are review
  clues; replay is the blocking proof.

For completion contracts, independent review, diff scope, and CI receipts, use
the full [Coding Quality Loop](https://github.com/zaingz/coding-quality-loop).
