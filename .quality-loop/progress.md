# Progress

## 2026-07-12 — v4.3.0 control plane (branch v4.3-control-plane) — IN REVIEW
- Shipped: local observability control plane — scripts/quality_loop_control.py
  (incremental SQLite index over Claude Code transcripts + CQL artifacts; GET-only
  127.0.0.1 server), assets/control-plane/dashboard.html (self-contained UI:
  overview/sessions/spend/records/routing/memory/events), control-* subcommands,
  SessionStart/SessionEnd hook shim with opt-in autostart (claude-code + codex
  wiring), control_plane config block + check-config validation, 20-case eval
  suite, gate count 144 -> 164 (7 suites), docs/control-plane.md, version 4.3.0
  at 5 synced sites.
- Hardened pre-review: bind-before-index (double-start race), sqlite busy_timeout,
  Windows-safe _pid_alive (os.kill(pid,0) kills on nt), healthz-verified
  control-stop (pid recycling), per-model cost attribution in mixed groups.
- Verified: all 7 suites green (164/164), live smoke on this repo's real
  transcripts (25+ sessions, 3.7k model calls), dashboard screenshots in both
  themes via Playwright/Chrome.
- In flight: codex-exec review, 8-dimension adversarial swarm, security reviewer.
- NEXT: fix confirmed findings -> re-verify -> attest -> commit -> release train
  (push main + v4.2.0 + v4.3.0 tags -> npm publish workflow) -> archive record.

## 2026-07-12 — v4.2.0 model routing — DONE, merged to main + tagged locally
- Merged as 2a3e499 (Merge v4.2-model-routing), tag v4.2.0 local; push rides the
  v4.3.0 release train. Record archived at docs/records/v4.2.0-agent-record.json.
