# Validation Contract

| Acceptance criterion | Concrete proof |
| --- | --- |
| Cargo project builds as Rust 2021 package `procmon` | `. "$HOME/.cargo/env" && cargo build --release` succeeds with no warnings |
| Tests cover stat parsing and list/find current process behavior | `. "$HOME/.cargo/env" && cargo test` succeeds |
| Clippy has no warnings | `. "$HOME/.cargo/env" && cargo clippy -- -D warnings` succeeds |
| `list` prints required table and supports sorting/reverse/json | Unit tests for sorting and manual smoke via built binary/table output |
| `find` matches current process and emits valid JSON lines | Integration test and smoke `procmon find procmon --format json` |
| `kill` refuses PID 1/0/current process unless forced | Integration test invokes `procmon kill 1` and expects non-zero clear error |
| `watch` has interval/default behavior and JSON frame shape | Code review plus argument parsing/unit validation; default Ctrl-C termination retained |
| `tree` prints rooted process hierarchy and JSON lines | Unit/code review of tree construction and manual dispatch coverage |
| No shell-out to `ps`/`kill`, no unsafe blocks except signal FFI if required | Diff review confirms use of `/proc` and `libc::kill` only |
| README documents usage, Linux assumptions, dependency justification, exit codes | README review |

## Regression Risks
- Parser regressions for commands containing parentheses.
- Incorrectly broad kill pattern matching.
- Clippy warnings from unused/public APIs.
- Flaky tests from process timing; prefer current-process checks and short-lived child only where stable.

## Required Evidence
Record final command tails and pass/fail status in `execution-log.md` and `completion-record.md`.
