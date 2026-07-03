# Execution Log Format

`execution-log.jsonl` is the execution trace substrate for a task run: one
JSON object per line (JSON Lines), appended as the agent works. It is the
input to `python scripts/quality_loop.py trace-audit <log-path>`, which
detects pathological tool loops and aggregates cost/duration per phase.

Write one line per tool invocation (or other discrete, loggable action).
Blank lines are ignored by the reader. Malformed JSON on a non-blank line is
a hard error — trace-audit stops and reports the offending line number.

## Fields

- `ts` — ISO 8601 timestamp (UTC recommended), e.g. `2026-07-03T07:35:00Z`.
- `phase` — one of `plan`, `execute`, `review`. Use the canonical three-phase
  name, not the legacy nine-step machine name.
- `step` — sub-step name within the phase, e.g. `context_map`,
  `minimality_gate`, `slice`, `verify`, `fresh_review`. Sub-steps inherit
  their parent phase; nothing is unlabeled.
- `tool` — name of the tool invoked (`edit`, `bash`, `read`, `grep`, ...).
- `target` — file path or identifier the tool acted on.
- `args_hash` — sha256 hex digest of the sorted tool arguments. Used with
  `tool` to identify repeated identical calls.
- `result_digest` — sha256 hex digest of the tool output, or the literal
  string `"empty"` (no output) or `"error"` (the call errored).
- `duration_ms` — integer wall-clock duration of the call in milliseconds.
- `cost_usd` — float, optional. Omit when the call has no attributable
  model cost (e.g. a local `bash` command).
- `model` — model identifier, optional. Omit for non-model tool calls.
- `notes` — free-form string, optional.

## Example

```jsonl
{"ts": "2026-07-03T07:30:00Z", "phase": "plan", "step": "context_map", "tool": "read", "target": "scripts/quality_loop.py", "args_hash": "9f2c1a...", "result_digest": "3b7e9c...", "duration_ms": 120}
{"ts": "2026-07-03T07:35:00Z", "phase": "execute", "step": "slice", "tool": "edit", "target": "scripts/quality_loop.py", "args_hash": "a11c02...", "result_digest": "d4e5f6...", "duration_ms": 340, "cost_usd": 0.004, "model": "claude-sonnet"}
{"ts": "2026-07-03T07:40:00Z", "phase": "review", "step": "fresh_review", "tool": "bash", "target": "pytest tests/", "args_hash": "77bb21...", "result_digest": "empty", "duration_ms": 2200, "notes": "no output, exit 0"}
```

## What `trace-audit` checks

- **Pathological loop (fails the run):** the same `(tool, args_hash)` pair
  appears 3 or more times **consecutively**. Each occurrence past the
  threshold is reported with its line number.
- **Repeated-call warning (does not fail the run):** the same
  `(tool, args_hash)` pair appears 5 or more times **anywhere** in the log,
  not necessarily consecutively.
- **Per-phase aggregation:** total steps, total `duration_ms`, and total
  `cost_usd` (entries without `cost_usd` are skipped from the cost sum, not
  treated as zero-cost evidence).
