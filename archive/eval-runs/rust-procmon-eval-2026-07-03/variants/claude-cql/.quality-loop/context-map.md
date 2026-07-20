# Context Map

## Entry points
- New Cargo project — no existing source to map.
- Main entry: `src/main.rs` → clap CLI dispatch → subcommand handlers.

## /proc filesystem layout (relevant fields)

### `/proc/[pid]/stat`
Single space-separated line. Key fields (1-indexed):
- 1: pid
- 2: comm (process name, in parentheses — may contain spaces/parens, must parse carefully)
- 3: state (R/S/D/Z/T)
- 4: ppid
- 14: utime (user-mode CPU ticks)
- 15: stime (kernel-mode CPU ticks)
- 22: starttime (ticks since boot — combine with `/proc/uptime` to get wall-clock start time)
- 24: rss (pages; multiply by page size for bytes)

### `/proc/[pid]/status`
Key/value lines. Used for:
- `Uid:` real UID → lookup username via `/etc/passwd` or `getpwuid`
- `VmRSS:` resident set size in kB (cross-check with stat field 24)

### `/proc/[pid]/cmdline`
NUL-delimited argv; NUL-join and display as command. Falls back to `[comm]` if empty (kernel threads).

### `/proc/[pid]/comm`
Short process name (≤15 chars). Used as fallback.

### `/proc/uptime`
Two floats: uptime_seconds idle_seconds. Used to compute process start wall-clock time.

### `/proc/meminfo`
`MemTotal: <kB>` for computing %MEM.

### `/proc` directory listing
`read_dir("/proc")` — filter entries where name is all digits.

## Race conditions
Process may exit between `read_dir` and reading individual files. All file opens in the per-pid reader should return `Option` / be silently skipped on `NotFound`. Other errors (Permission) should be propagated per the exit-code spec.

## Signal sending
`libc::kill(pid, signal)` — use `libc` crate for signal constants (SIGTERM=15, SIGKILL=9, etc.) to avoid raw numeric magic without `unsafe`. The `kill` syscall itself requires `unsafe`.

## CPU % calculation
Single-snapshot CPU% is not meaningful without two readings. For `list`/`find`, report a two-sample delta approach (snapshot, sleep briefly, snapshot again) — or document that %CPU is 0.0 in single-shot mode and only meaningful in `watch`. Decision: use two samples in `watch` (per-refresh delta) and 0.0 in single-shot for simplicity; document in README.

## Modules planned
```
src/
  main.rs          — CLI entry, subcommand dispatch
  proc.rs          — /proc parsing: ProcEntry, stat parser, status parser, cmdline reader
  table.rs         — fixed-width table formatter
  json.rs          — JSON output (via serde_json)
  signals.rs       — signal name → libc constant mapping, kill logic
  tree.rs          — process tree builder and ASCII printer
  watch.rs         — watch loop with Ctrl-C handling
tests/
  integration.rs   — spawn child, test list/find, test kill-PID1-rejection
```

## Existing utilities to reuse
- `std::fs::read_dir`, `std::fs::read_to_string` — /proc reading
- `std::process::Command` — NOT used (no shelling out), but `std::process::id()` for self-PID guard
- `serde`, `serde_json` — JSON output
- `regex` — pattern matching in `find`/`kill`
- `clap` (derive) — argument parsing
- `libc` — signal constants + `kill` syscall

## Verification commands (planned)
```bash
. "$HOME/.cargo/env" && cargo build --release 2>&1 | tail -20
. "$HOME/.cargo/env" && cargo test 2>&1 | tail -30
. "$HOME/.cargo/env" && cargo clippy -- -D warnings 2>&1 | tail -30
./target/release/procmon list | head -5
./target/release/procmon find procmon --format json
./target/release/procmon kill 1  # expect: error on stderr, exit 1
```

## Risks
- `comm` field in `/proc/pid/stat` may contain spaces and parentheses — parser must find last `)` not first.
- `/proc` listing includes non-process entries (e.g., `net`, `sys`) — filter to digit-only names.
- `getpwuid` returns `None` for UIDs not in `/etc/passwd` — fall back to numeric UID string.
- %CPU calculation: only meaningful across two snapshots; single-shot returns 0.0.
- Watch Ctrl-C: use `std::sync::atomic::AtomicBool` + signal handler or `ctrlc` crate.
