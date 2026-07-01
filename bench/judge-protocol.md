# Benchmark Judge Protocol

Judging is objective-first.

Primary metrics come from hidden tests, mutation/reverted-patch adequacy, diff
size, new dependency detection, secret/test-weakening flags, and gate compliance.
LLM or human judges may review artifacts for clarity, but they do not override
objective failures.

Blind review rules:

- Strip arm names and builder identity from artifacts.
- Randomize artifact order per task.
- Judge family must differ from builder family when a model judge is used.
- Publish null results and failures.
- Rotate held-out tasks before claiming durable lift.

The committed fixture result is a harness smoke result, not a live agent claim.
Live sweeps must record host, model, seed, cost, and raw artifacts.
