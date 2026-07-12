# Minimal Drop-In Prompt

Paste this into any coding agent to run the Coding Quality Loop without the full skill.

```markdown
Run the Coding Quality Loop: PLAN -> EXECUTE -> REVIEW. Verification closes each phase.

PLAN: pick the smallest safe task class. Map the change before editing. Non-trivial work gets a validation contract pairing each acceptance criterion with the check that proves it. Right-size gate — highest valid rung: no change, delete, reuse, stdlib, native, existing dependency, one-liner, minimal new code. Minimal diff is not minimal architecture; benchmarked work commits to worst-case complexity and p50/p95 targets at plan time.

EXECUTE: one slice at a time, existing conventions. Run the smallest sufficient checks; record exact commands and results. Bug fix = RED then GREEN; never weaken tests.

REVIEW: non-trivial diffs get a fresh-context review (different session or model) against the contract, executing tests when possible. No completion claim without a completion record. Stop and escalate on destructive, security-sensitive, or repeatedly failing work. Turn every repeated mistake into a durable rule, not a repeated correction.
```
