# Task: `procmon` — Unix process manager in Rust

Build a small command-line task manager for Unix processes, written in idiomatic Rust. It is a workaday tool: think a scriptable alternative to a subset of `htop` / `pgrep` / `pkill` combined, callable from shell scripts and interactive use.

## Deliverables

A single Cargo project rooted at the repository root of your working directory:

- `Cargo.toml` — package `procmon`, edition 2021, `bin/procmon`
- `src/` — Rust source
- `tests/` — integration tests (any tests appropriate for the design; unit tests inside `src/` are also welcome)
- `README.md` — short usage doc

## Required functionality (v1 scope)

1. **`procmon list`** — print running processes for the current user in a fixed-width table:
   `PID  PPID  USER  %CPU  %MEM  RSS(KB)  START     COMMAND`
   Sortable via `--sort <pid|cpu|mem|start>` and reversible via `--reverse`.

2. **`procmon find <pattern>`** — regex-match processes by command line. Print the same table. `--exact` toggles substring vs. regex.

3. **`procmon kill <pid|pattern> [--signal SIGTERM|SIGKILL|...]`** — send a signal to a single PID or every process matching a regex pattern. Refuse to kill PID 1, PID 0, and the current process unless `--force`. Default signal is `SIGTERM`. Exit non-zero if no process matched.

4. **`procmon watch [pattern] [--interval SECS]`** — refresh every `SECS` (default 2.0) and reprint the table. Clean exit on Ctrl-C.

5. **`procmon tree [--pid <root>]`** — print an ASCII process tree rooted at `<root>` (defaults to PID 1). Indent children under parents.

6. **`--format json`** — every subcommand accepts `--format table|json` (default `table`). JSON must be a single line per process for `list`/`find`/`tree`, or a stable object shape for `watch` frames.

## Non-goals (v1)

- Windows / macOS support (Linux-only is acceptable; document what you assume).
- A TUI (curses/tui-rs). `watch` may just clear-and-reprint.
- Persistent state, config files, plugins, or a daemon.
- Auth, capabilities beyond what a normal user can do.

## Constraints

- **Runtime deps**: keep them minimal. Prefer standard library and `/proc` parsing over big crates. If you use a crate, justify it briefly in the README.
- **Safety**: no `unsafe` blocks unless strictly required and explained. Never shell out to `ps`/`kill` — do the work in Rust.
- **Portability inside Linux**: read `/proc/[pid]/{stat,status,cmdline,comm}` directly. Handle races (process dies between listing and reading) gracefully.
- **Errors**: user-facing errors go to stderr, exit codes are meaningful (0 = ok, 1 = usage/no-match, 2 = permission, 3 = internal).
- **Tests**: at minimum a test that exercises `list` and `find` against the current process, and a unit test for the `/proc/[pid]/stat` parser. Integration tests may `spawn` a short-lived child and verify it appears/disappears.
- **README**: 1-2 pages max. Include usage examples for every subcommand and the exit-code table.

## Acceptance (self-check before "done")

- `cargo build --release` succeeds with no warnings.
- `cargo test` passes.
- `cargo clippy -- -D warnings` produces zero warnings.
- `procmon list | head` prints the current shell and this build in a reasonable table.
- `procmon find procmon --format json` prints valid JSON.
- Killing PID 1 without `--force` is rejected with a clear error.

## How to work

Write the code exactly as you would for a normal team code review. You do not need to explain your reasoning outside of source comments and the README, except where the skill or prompt you were given asks for extra artifacts. When you are done, print a short one-paragraph summary of what you built.

You have full access to the shell in your working directory. Rust is pre-installed. Do not install additional system packages. Do not commit build artifacts. Do not push to any git remote.
