# Progress

## 2026-07-12 — v4.2.0 model routing (branch v4.2-model-routing) — DONE, release pending
- Shipped: multi-host per-role routing (agents {host,class} + main_session), family-aware
  cross-host reviewer heterogeneity (fixes the sonnet/claude-sonnet-4-5 alias hole),
  three eval-pinned routing variants + dated menu (assets/routing/), escalation evidence
  fields (models_used/escalations) with the evidenced-failing-command gate, R7 cross-CLI
  recipe (live-verified), version 4.2.0 at 5 synced sites, gate count 130 -> 144.
- Reviewed: codex/gpt-5.6-sol (2 rounds) + 24-agent fresh-context swarm with adversarial
  verification; 17 confirmed findings fixed and eval-pinned; review attested
  (diff sha in record), verify umbrella PASS.
- Record: .quality-loop/agent-record.json (status done). Archive to
  docs/records/v4.2.0-agent-record.json as a follow-up commit after release.
- NEXT (human-gated): merge v4.2-model-routing -> main, git tag v4.2.0, npm publish.
  Follow-ups list lives in the record's completion_record.
