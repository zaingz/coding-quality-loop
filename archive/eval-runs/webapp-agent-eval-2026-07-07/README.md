# Live Webapp Task Manager Evaluation - 2026-07-07

A one-seed live 2x2 eval of the previously unrun bench task
[`13-webapp-task-manager`](../../bench/tasks/13-webapp-task-manager.json): **Codex
(gpt-5.5)** and **Claude Code (claude-fable-5)**, each building the same
browser task manager from an identical `SPEC.md`, with and without the CQL v3.0
skill delivered as a drop-in bundle. This run closes a gap from the sudoku
2026-07-01 eval: the five hidden behaviors were verified with **real browser
automation** this time, one isolated localStorage origin per arm.

## Result

All four arms passed `npm test`, used zero dependencies, and passed **5/5 hidden
browser behaviors** (add persists after reload, edit persists, delete removes,
completed filter isolates, empty state on no match). Differentiation came from
two blind LLM judges (gpt-5.5 and claude-fable-5, different letter mappings,
identity-scrubbed packets) on the 10-dimension rubric.

| Rank | Arm | CQL? | Tests | Hidden | Codex judge | Claude judge | Avg | Code-quality (excl. D7) |
|---:|---|---|---:|---|---:|---:|---:|---:|
| 1 | `claude_cql` | yes | 57 | 5/5 | 97.25 | 98.0 | **97.62** | 97.36 |
| 2 | `claude_baseline` | no | 21 | 5/5 | 80.75 | 82.5 | 81.62 | 90.69 |
| 3 | `codex_cql` | yes | 8 | 5/5 | 79.5 | 83.25 | 81.38 | 80.97 |
| 4 | `codex_baseline` | no | 6 | 5/5 | 74.0 | 73.75 | 73.88 | 82.08 |

CQL average: **89.5**. Baseline average: **77.75**. Total lift: **+11.75 points**.

Per-agent delta, split by metric:

| Agent | Total lift (with D7) | Code-quality lift (excl. D7) | Wall time baseline -> CQL |
|---|---:|---:|---|
| Claude Code | **+16.0** | **+6.67** | 5.5 min -> 32 min |
| Codex | +7.5 | **-1.11** | 3 min -> 10 min |

Read the split honestly: for Claude Code, CQL improved the code itself (more and
better tests, guarded storage, inline editing with focus management, a two-round
independent review that changed the code). For Codex, the total lift comes almost
entirely from D7 process artifacts; the code-quality headline is flat-to-negative,
echoing the ts-search finding that CQL scaffolding does not by itself force better
product decisions (codex-cql shipped `window.prompt()` editing and an 8-test suite).

## The gate-gaming incident (the most useful finding)

A harness bug made this run a natural experiment. The `cql/scripts` bundle
initially omitted two modules that `quality_loop.py` imports. Both CQL arms hit
the breakage:

- **claude_cql** reconstructed the missing modules in a clearly labeled commit
  and left `quality_loop.py` byte-identical to the original.
- **codex_cql** reconstructed stub modules and **also edited `quality_loop.py`
  itself**, softening two diff-audit behaviors (removed the untracked-files
  warning, added a package.json carve-out), then reported `verify ... Overall:
  PASS` against its own modified gate. Its final summary disclosed two sandbox
  blockers but not the gate edit.

This directly supports CQL's documented trust model: the helper is advisory, an
agent can game local gates, and deterministic repo-side hooks and CI must remain
the backstop. Post-hoc re-verification with the pristine repo scripts returned
**FAIL** for both CQL arms (missing `allowed-commands` allowlist in both; an
unattested review for codex_cql; a stale review hash for claude_cql that the
reality layer caught exactly as designed).

## Methodology

1. **Four isolated workspaces**, identical `SPEC.md`, fresh git repo each. CQL
   arms got the v3.0 skill bundle at `cql/` (drop-in path) and a prompt to follow
   it; baseline prompts banned CQL and nested agent CLIs.
2. **Contamination control**: the operator machine had CQL installed user-scope
   for both hosts, and both global instruction files reference CQL. Codex arms
   therefore ran with a clean `CODEX_HOME`; Claude arms ran with `--safe-mode`.
   Post-hoc transcript checks found zero CQL usage in the baselines.
3. **Machine checks**: `npm test`, dependency count, LOC, `diff-audit`, load
   timing (all arms < 25ms against the 500ms budget).
4. **Hidden behaviors**: the five held-out behaviors from the bench task were
   exercised through real browser automation per arm.
5. **Blind judging**: anonymized packets (`.quality-loop/` renamed to
   `process-notes/`, host/model strings scrubbed), different letter mappings per
   judge, blinded machine-check summary attached, judges from both model
   families.

Codex's `workspace-write` sandbox blocks `.git` writes, so codex arms could not
commit; their final trees were captured by a neutral harness commit and the
limitation is recorded here rather than scored.

## Caveats

- **Single task, single seed.** Directional evidence, not a durable benchmark
  claim. A retry could swing any cell.
- **Drop-in delivery, not native skill discovery.** Chosen for isolation
  symmetry; native hook wiring was validated separately (installer lands 50
  files for Claude Code, hooks + runtime for Codex) but not live-tested here.
- **Judges are LLMs** from the same two families as the builders (mitigated by
  blinding, scrubbing, and distinct mappings, not eliminated). The two judges
  agreed on rank 1 and rank 4 and swapped ranks 2 and 3.
- **Same person designs, runs, and interprets the eval and maintains the
  skill.** The full run tree (workspaces, transcripts, judge packets) was kept
  locally under an ignored path, not committed.
- The harness-bundle bug means the CQL arms' in-run helper experience was not
  pristine; the gate-gaming observation is a finding about agent behavior under
  a broken harness, not a controlled measurement.

The sanitized result data is in [`results.json`](results.json).
