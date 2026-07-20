# Context Map

## Repository State
The working directory contains Coding Quality Loop support files but no Cargo project yet. The implementation will create a single Rust binary project rooted here.

## Entry Points
- `src/main.rs`: CLI argument parsing, subcommand dispatch, exit-code mapping.
- `src/lib.rs`: shared modules for `/proc` reading, formatting, matching, signal parsing, and tree construction.

## Data Sources and Contracts
- `/proc`: enumerate numeric directories.
- `/proc/[pid]/stat`: parse PID, command-in-parens, state, PPID, start ticks, and CPU ticks.
- `/proc/[pid]/status`: parse UID and VmRSS.
- `/proc/[pid]/cmdline`: null-separated command line; fallback to `/proc/[pid]/comm`.
- `/proc/uptime`, `/proc/meminfo`: support CPU and memory percentage calculations.
- `/etc/passwd`: optional UID-to-name display lookup.

## Likely Files to Edit/Create
- `Cargo.toml`
- `src/lib.rs`
- `src/main.rs`
- `tests/cli.rs`
- `README.md`
- `.quality-loop/*.md`

## Existing Patterns to Reuse
No application code exists. Use standard-library filesystem parsing, localized modules, and minimal crates for regex matching and POSIX signal delivery.

## Verification Commands
- `. "$HOME/.cargo/env" && cargo fmt --check`
- `. "$HOME/.cargo/env" && cargo test`
- `. "$HOME/.cargo/env" && cargo build --release`
- `. "$HOME/.cargo/env" && cargo clippy -- -D warnings`
- Smoke checks for `list`, `find --format json`, and guarded `kill 1`.

## Risks
- `/proc` races when processes exit mid-read: handle by skipping vanished/unreadable process entries.
- `/proc/[pid]/stat` parsing must handle command names containing spaces or parentheses by splitting at the final `)`.
- Signal sending is a risk boundary; guard PID 0, PID 1, and current PID by default.
