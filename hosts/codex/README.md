# Codex host notes

`hooks.json` provides the advisory project hooks. Codex requires hook trust via
`/hooks` before they run.

## Sandbox limits that affect the loop

Observed live (codex-cli 0.142.x, `--sandbox workspace-write`, webapp eval
2026-07-07):

- **`.git` writes are blocked.** `git commit` fails with `Unable to create
  '.git/index.lock': Operation not permitted`. The agent cannot commit slices,
  so `diff-audit --base` and worktree-based `--red-green` replay are limited.
  Options: run with approvals and a policy that permits git writes, commit from
  outside the session, or record the blocker candidly in the state record
  ("commit blocked by sandbox") and let the caller commit.
- **Binding localhost ports is blocked.** `python3 -m http.server` fails, so
  in-session browser smoke against a local server is not possible; record it as
  not-verified rather than claiming it.
- Network is disabled by default under `workspace-write`; zero-dependency
  verification commands (`node --test`, `pytest` on the stdlib) still work.

## Candor rule

When the sandbox blocks a required step, the record must say so. A verify PASS
that silently skips a blocked check is phantom evidence. And never repair or
stub the helper scripts to route around a blocker; report it instead.
