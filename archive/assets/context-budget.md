# Context Budget

Task ID: {{task_id}}
Phase: {{plan|execute|review}}

## Inputs (what this phase needs)

- path or artifact — reason it's needed
- e.g. `src/billing/invoice.py` — the function under change, needed to write the fix
- e.g. `validation-contract.md#AC2` — the acceptance criterion this phase must satisfy

## Excluded (what this phase must not carry)

- path or artifact — reason it must not leak in
- e.g. `docs/history/**` — historical rationale is not needed to implement; including it
  invites scope creep and burns tokens the phase doesn't need
- e.g. the full `execute` transcript, when this is the `review` phase — review must judge
  the diff and the contract, not be talked into approval by the implementer's narration

An input and an excluded entry must never name the same path or artifact. If a later
phase needs something this phase excluded, that is a signal the phase boundary is wrong,
not a reason to quietly widen this phase's inputs.

## Output summary (≤N tokens)

The digest this phase passes to the next. Write it here after the phase completes.

- e.g. (plan → execute, ≤200 tokens): "Add `context-check` subcommand to
  `quality_loop.py`; validate `context_budget` dict per phase; error on missing
  `output_summary` or `inputs`/`excluded` overlap; warn above 2000-token soft cap.
  Files: `scripts/quality_loop.py`, `assets/context-budget.md`. No schema edit — patch
  proposed separately."
- e.g. (execute → review, ≤150 tokens): "Added `context-check` subcommand + asset.
  11 existing eval cases pass unchanged. Diff touches only the S2-owned files.
  Positive/negative sample runs attached as evidence."

Keep this to a digest, not a transcript. If it needs more than the stated token budget
to be useful, the phase did too much or the digest is doing the summarizing wrong.

## Rationale

One paragraph on why this budget makes sense for this phase. Context is a scarce,
costly resource, not a convenience: every extra path or artifact a phase reads is
something a later phase (or a fresh reviewer) may accidentally inherit, and every
token in the output summary is a token the next phase's model has to hold instead of
spending on its own reasoning. A tight, explicit budget also makes drift visible —
if a phase's actual reads stop matching its declared `inputs`, that mismatch is a
cheap, mechanical signal (checked by `context-check`) that the phase boundary or the
task scope has quietly grown.
