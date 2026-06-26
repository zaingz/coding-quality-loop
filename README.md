# Coding Quality Loop

`coding-quality-loop` is a portable Agent Skill for turning high-level software goals into small, verified code changes.

It packages:

- A lifecycle for intake, exploration, planning, minimality, implementation, verification, review, and handoff.
- Reference checklists for risk tiering and fresh-context review.
- Tool contracts for repo mapping, verification runners, reviewer agents, and policy hooks.
- Templates for task contracts, state records, and PR summaries.
- A lightweight helper script for state-record checks, diff audits, and verification-gate sanity checks.

## Quick Start

1. Load `SKILL.md` into your agent or copy the minimal drop-in prompt.
2. For medium/high-risk work, create a state record:

   ```bash
   python scripts/quality_loop.py init-record --goal "Fix checkout retry bug" --risk-tier medium --output agent-record.json
   ```

3. Follow the lifecycle:

   ```text
   INTAKE -> EXPLORE -> PLAN -> MINIMALITY_GATE -> IMPLEMENT_SLICE -> VERIFY -> REVIEW -> PACKAGE
   ```

4. Audit the diff and verification record before handoff:

   ```bash
   python scripts/quality_loop.py diff-audit --base origin/main
   python scripts/quality_loop.py verify-gates agent-record.json
   ```

## Philosophy

The goal is bounded autonomy: small diffs, explicit contracts, deterministic evidence, and fresh-context review. The agent should not overcomplicate by default, and it should never claim success without verification evidence or a clear explanation of blocked checks.
