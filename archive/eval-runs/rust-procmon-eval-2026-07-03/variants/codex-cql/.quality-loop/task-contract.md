# Task Contract

## Goal
Build a Rust 2021 single-binary Cargo project named `procmon` that implements a Linux `/proc` based process manager CLI.

## Task Class and Risk
- Class: MEDIUM
- Risk tier: medium (process inspection and signal sending can affect local processes)

## Acceptance Criteria
1. `procmon list` prints current-user processes in the required table, supports `--sort <pid|cpu|mem|start>`, `--reverse`, and `--format table|json`.
2. `procmon find <pattern>` matches command lines using regex by default and substring matching with `--exact`, with table/json output.
3. `procmon kill <pid|pattern> [--signal ...] [--force]` sends signals without shelling out, refuses PID 0, PID 1, and the current process unless forced, and exits non-zero on no match.
4. `procmon watch [pattern] [--interval SECS] [--format table|json]` refreshes repeatedly with a default 2-second interval.
5. `procmon tree [--pid <root>] [--format table|json]` prints an ASCII process tree or JSON lines rooted at the requested PID.
6. Project includes README and tests for list/find/current process behavior plus `/proc/[pid]/stat` parser coverage.
7. `cargo build --release`, `cargo test`, and `cargo clippy -- -D warnings` pass with zero warnings.

## Constraints
- Work only under `/home/user/workspace/rust-eval-2026-07-03/variants/codex-cql`.
- Every cargo/rustc command must be prefixed with `. "$HOME/.cargo/env" &&`.
- Linux-only; read `/proc/[pid]/{stat,status,cmdline,comm}` directly.
- Do not shell out to `ps` or `kill`.
- Keep runtime dependencies minimal and justified.
- No system package installation, no git commit/push, do not commit target/.

## Non-goals
- Windows/macOS support, TUI, daemon/config/plugins, elevated auth/capability management, exhaustive htop parity.

## Assumptions
- USER may be rendered from `/etc/passwd` when available, otherwise as numeric UID.
- CPU and start time may be approximate from `/proc/stat`, `/proc/uptime`, and clock ticks.
- Default Ctrl-C handling is acceptable for `watch` because it terminates the loop cleanly without extra state.

## Verification Plan
Run unit/integration tests and final acceptance commands:
- `. "$HOME/.cargo/env" && cargo build --release 2>&1 | tail -20`
- `. "$HOME/.cargo/env" && cargo test 2>&1 | tail -30`
- `. "$HOME/.cargo/env" && cargo clippy -- -D warnings 2>&1 | tail -30`
Also perform smoke checks for JSON find and PID 1 kill rejection.

## Escalation Conditions
Stop if signal behavior requires destructive testing beyond protected rejection checks, if a new dependency beyond regex/libc is needed, or if repeated verification failures occur after focused repairs.
