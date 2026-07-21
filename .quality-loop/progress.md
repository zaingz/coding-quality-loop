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

## 2026-07-21 — v6.3.0 (measured) — IN FLIGHT
- Deep independent review (Fable) verified all 7 suites + first contact + uninstall,
  then ran a live §6.2 pilot: baseline aced the micro-task; full arm 4.2-4.8x cost,
  same-model self-review, risk:low on a billing task, pristine gate FAILs the record.
- Gaps chosen for v6.3.0: live §6.2 numbers committed; review-yield dedupe; repair
  v6.1.0 archived record + archive lint; README void-annotation for webapp judge
  numbers; check-config gate-config shape; heterogeneity surfacing; CI-anchor next
  step; SKILL.md outcome nudge; PROTOCOL recipe rot (--safe-mode gone) + materializer.
- Lanes: A (opus) integrity+defaults, B (opus) bench enablement. 6 live cells
  (3 seeds x {baseline,full}) running from pristine v6.2.0 drop-in workspaces.
- PACKAGE: all 8 codex findings + 1 security finding fixed; claims corrected to
  honor §6.0's letter (outcome NOT claimed, fires:false); confirmation approve
  (functional) + final claims approve. Verify umbrella: Overall PASS at package
  with both reviews attested. 250 core + 37 add-on green; npm tests 33/0.

## 2026-07-21 — subtraction pass (branch cleanup/subtraction-pass, PR #22) — IN REVIEW
- Net −233 lines (+147/−380) + a 47KB binary across 32 files; 7 themed commits.
- Cut: dead run-journal reader (writer archived in v3.0), unreachable ORCHESTRATE
  step entry, bench/metrics dead CLI, npm dead surface (step/smoke/exports),
  redundant static case 01, orphaned memory-hooks example + terminal-demo poster,
  retired advisor block from the example config.
- Dedup: stop_gate + sessionstart adopt hooklib (fixes sessionstart's missing-git
  crash, disclosed); run_evals' 4 verbatim repo-init blocks -> one helper.
- Docs: architecture protect-harness claim + invented record example fixed; schema
  gains protect_harness/enforcement; control-plane 35->37 + joins the count lint
  (harness_update); one canon for phase mapping; CHANGELOG Unreleased entry.
- Addition (1): npm-smoke now runs the 33 never-CI-run npm tests (own commit).
- Loop: record at package, verify umbrella Overall PASS (11 commands re-executed);
  Codex cross-family review round 1 request_changes (2 blocking -> fixed/rebutted
  with recorded resolutions), round 2 approve with ran_checks. Suites 249+37.
- NEXT: maintainer sign-off on PR #22 -> merge -> record outcome + archive record
  at the next release tag.
