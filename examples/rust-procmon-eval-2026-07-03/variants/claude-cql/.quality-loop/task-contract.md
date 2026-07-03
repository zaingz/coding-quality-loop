# Task Contract

## One-sentence goal
Build `procmon`, a Linux process-monitoring CLI in Rust that lists, finds, kills, watches, and trees processes by reading `/proc` directly.

## Task class
**Medium** — multiple source files, a feature set with six subcommands, integration tests, and full quality-loop ceremony required.

## Risk tier
**Medium** — sends real signals to processes; reads `/proc` with race-condition risk; no external data-loss or auth risk.

## Acceptance criteria
1. `procmon list` prints a fixed-width table (PID, PPID, USER, %CPU, %MEM, RSS(KB), START, COMMAND) for the current user's processes, sortable via `--sort` and reversible via `--reverse`.
2. `procmon find <pattern>` regex-matches processes by command line and prints the same table; `--exact` toggles to substring match.
3. `procmon kill <pid|pattern> [--signal ...]` sends the specified signal (default SIGTERM); refuses PID 0/1/self without `--force`; exits non-zero if no process matched.
4. `procmon watch [pattern] [--interval SECS]` refreshes (default 2 s), clears and reprints the table; exits cleanly on Ctrl-C.
5. `procmon tree [--pid <root>]` prints an ASCII tree rooted at the given PID (default 1), children indented under parents.
6. Every subcommand accepts `--format table|json`; JSON is a single line per process / stable object per watch frame.
7. `cargo build --release` produces zero warnings.
8. `cargo test` passes.
9. `cargo clippy -- -D warnings` produces zero warnings.
10. Killing PID 1 without `--force` is rejected with a clear error message on stderr.

## Constraints
- Rust edition 2021, single binary `procmon`.
- Linux-only: read `/proc/[pid]/{stat,status,cmdline,comm}` directly — no shelling out to `ps`/`kill`.
- No `unsafe` unless strictly required and explained in a comment.
- Minimal runtime dependencies — complexity brake applies.
- Process races (process exits between listing and reading) must be handled gracefully.
- Errors to stderr; meaningful exit codes: 0 ok, 1 usage/no-match, 2 permission, 3 internal.

## Non-goals
- Windows/macOS support.
- TUI (curses/tui-rs) — `watch` clears and reprints.
- Persistent state, config files, plugins, daemon.
- Capabilities beyond what a normal Linux user can exercise.

## Assumptions
- The build machine has Linux with `/proc` mounted (standard).
- Tests run as a non-root user; tests that require killing arbitrary processes are skipped or scoped to child processes we own.
- `regex` crate is acceptable as a justified dependency (regex matching is a core feature; the standard library has no regex support).
- `libc` crate is acceptable for signal constants (avoids `unsafe` numeric magic).
- `serde`/`serde_json` are acceptable for JSON output (justified by the `--format json` requirement).
- `clap` is acceptable for argument parsing (justified below under complexity brake).

## Verification plan
Run `cargo build --release`, `cargo test`, and `cargo clippy -- -D warnings` and capture the last 20–30 lines of output for each. Exercise `procmon list`, `procmon find procmon --format json`, and `procmon kill 1` (expected rejection) in the completion record.

## Escalation conditions
- Any test that requires root privileges.
- Any use of `unsafe` beyond signal syscalls (requires explicit sign-off in decision log).
- Repeated clippy/test failures after two focused repair cycles.
