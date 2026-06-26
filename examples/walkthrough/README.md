# Walkthrough: a bug fix through the full loop

A real, end-to-end example of a **medium-risk bug fix** moving through the Coding Quality
Loop. The matching state record is `agent-record.json` in this folder; validate it with:

```bash
python ../../scripts/quality_loop.py check-record agent-record.json
python ../../scripts/quality_loop.py verify-gates agent-record.json
```

## The bug

Invoice totals are off by a cent on multi-line invoices because each line item is rounded
before summation instead of rounding once at the total.

## Step by step

**INTAKE — `contract_agent`.** Goal, acceptance criteria (round once; single-line invoices
unchanged; regression test), constraints (no API change, no new deps), risk tier `medium`.

**EXPLORE — `repo_mapper`.** Found the bug at `billing/invoice.py:Invoice.total`, the existing
`ROUND_HALF_UP` quantize helper in `billing/money.py`, and the caller
`api/routes/invoices.py:get_invoice`. No schema or config involved.

**PLAN — `planner`.** Sum at full precision, quantize the total once, add a 3-line regression
test. Verification: failing test first, then the billing suite, then typecheck.

**MINIMALITY_GATE — `minimality_reviewer`.** Chosen rung: `one_liner` — move the existing
quantize call from per-item to the total. Lower rungs rejected (the total is genuinely wrong,
no dead code, reuse already applies). Safety checked: validation and data-loss — neither
weakened.

**IMPLEMENT_SLICE — `implementer`.** One small diff in `billing/invoice.py` plus a regression
test. No API change, no new dependency, existing conventions followed.

**VERIFY — `verification_runner`.** The new test failed before the fix (`expected 10.00, got
10.01`), passed after (`14 passed`), and `mypy billing` is clean. Commands and results are
recorded in the state record.

**REVIEW — `fresh_reviewer` (separate session).** Checked the diff against the contract, not
the implementer's confidence: rounding moved to the total, regression test covers the reported
case, no public API change. Verdict: **approve**.

**PACKAGE — `packager`.** Handoff assembled with `assets/pr-summary-template.md`: goal, files
changed, minimality decision (`one_liner`), verification evidence table, the rounding-policy
risk note, and rollback (revert the single diff).

## Why this is the model behavior

- The fix is the smallest correct change (one moved call), not a rounding-utility rewrite.
- Evidence precedes the success claim: a failing-then-passing regression test, not "looks
  right."
- Review was independent, so approval reflects the contract rather than self-confidence.
- The one residual risk (rounding mode) is documented instead of hidden.
