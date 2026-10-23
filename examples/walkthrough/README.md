# Walkthrough: a bug fix through the full loop

An illustrative **medium-risk bug-fix record** showing the Coding Quality Loop fields.
This folder contains no invoice implementation, regression test, or captured command logs.
Validate the record shape with:

```bash
python3 ../../scripts/quality_loop.py check-record agent-record.json
python3 ../../scripts/quality_loop.py verify-gates agent-record.json
```

This record passes **both** commands (exit 0). They validate the recorded fields and gate
policy, not the claimed invoice behavior or independent review. CI re-runs these shape
checks so the fixture does not drift out of compliance.

## The bug

Invoice totals are off by a cent on multi-line invoices because each line item is rounded
before summation instead of rounding once at the total.

## Step by step

**INTAKE — `contract_agent`.** Goal, acceptance criteria (round once; single-line invoices
unchanged; regression test), constraints (no API change, no new deps), risk tier `medium`.

**EXPLORE — `repo_mapper`.** The record names `billing/invoice.py:Invoice.total`, the existing
`ROUND_HALF_UP` quantize helper in `billing/money.py`, and the caller
`api/routes/invoices.py:get_invoice`. No schema or config involved.

**PLAN — `planner`.** Sum at full precision, quantize the total once, add a 3-line regression
test. Verification: failing test first, then the billing suite, then typecheck.

**MINIMALITY_GATE — `minimality_reviewer`.** Chosen rung: `one_liner` — move the existing
quantize call from per-item to the total. Lower rungs rejected (the total is genuinely wrong,
no dead code, reuse already applies). Safety checked: validation and data-loss — neither
weakened.

**IMPLEMENT_SLICE — `implementer`.** The example describes one small diff in
`billing/invoice.py` plus a regression test. Neither file is included here.

**VERIFY — `verification_runner`.** The record claims the new test failed before the fix
(`expected 10.00, got 10.01`), passed after (`14 passed`), and `mypy billing` was clean.
These outcomes are sample text, not independently runnable evidence.

**REVIEW — `fresh_reviewer` (separate session).** The record claims a fresh reviewer checked
the diff and ran the billing suite (`ran_checks: true`), then approved. The fixture cannot
establish that a reviewer session or billing suite actually ran.

**PACKAGE — `packager`.** Completion record assembled with `assets/completion-record.md`: goal,
files changed, right-size decision (`one_liner`), verification evidence table, the
rounding-policy risk note, and rollback (revert the single diff).

## Why this is the model behavior

- The fix is the smallest correct change (one moved call), not a rounding-utility rewrite.
- A real run needs inspectable RED and GREEN outputs from executable tests before claiming success.
- A real run needs a separate review whose findings can be checked against the diff.
- The one residual risk (rounding mode) is documented instead of hidden.
