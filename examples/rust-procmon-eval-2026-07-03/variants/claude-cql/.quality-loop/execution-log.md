# Execution Log

## Slice 1 — Cargo scaffold + proc.rs + error.rs
- `cargo init --name procmon`
- Wrote `Cargo.toml` with dependencies: clap 4, regex 1, serde/serde_json 1, libc 0.2
- Wrote `src/error.rs`: `AppError` enum with exit codes 0/1/2/3
- Wrote `src/proc.rs`: `ProcInfo`, `StatFields`, `parse_stat`, `read_uid`, `read_cmdline`, `read_uptime`, `read_mem_total_kb`, `uid_to_username`, `read_proc_entry`, `list_all_procs`, `build_children_map`
- Unit tests for `parse_stat` (basic, spaces-in-comm, invalid), `read_uptime`, `read_mem_total_kb`, `list_all_procs` (self-pid inclusion)

## Slice 2 — table.rs + output.rs
- Wrote `src/table.rs`: fixed-width formatter with header and row printing
- Wrote `src/output.rs`: `Format` enum, `print_procs` dispatcher

## Slice 3 — signals.rs + `procmon kill`
- Wrote `src/signals.rs`: signal name/number parser, `send_signal` wrapper around `libc::kill`
- Implemented `cmd_kill`, `check_kill_guards` in main.rs

## Slice 4 — tree.rs + `procmon tree`
- Wrote `src/tree.rs`: recursive DFS printer with ASCII tree connectors

## Slice 5 — watch.rs + `procmon watch`
- Wrote `src/watch.rs`: SIGINT handler using process-global `AtomicBool`, clear-and-reprint loop

## Slice 6 — main.rs + clap CLI
- Wrote `src/main.rs`: clap derive CLI with `list`, `find`, `kill`, `watch`, `tree` subcommands
- Exit-code propagation via `AppError::exit_code()`

## Slice 7 — integration tests + README
- Wrote `tests/integration.rs`: 13 integration tests
- Wrote `README.md`

## Build cycle
1. First build: 4 warnings (dead field, dead fn, dead inner fn, function-cast-as-integer)
2. Fixed all 4 warnings
3. Clippy pass 1: 3 errors (print_literal, redundant_closure, ptr_arg)
4. Fixed all 3 clippy errors
5. Test run 1: `test_find_no_match_exits_1` FAILED — pattern matched procmon's own cmdline
6. Fixed test to use anchored regex `^IMPOSSIBLE_...$`
7. All subsequent runs: 19/19 tests pass, 0 warnings, 0 clippy errors

## Review fix
- Changed `partial_cmp().unwrap()` to `total_cmp()` in float sort to prevent potential NaN panic
