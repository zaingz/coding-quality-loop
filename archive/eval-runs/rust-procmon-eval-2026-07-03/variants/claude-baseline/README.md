# procmon

A command-line process monitor for Linux. Reads directly from `/proc` — no shelling out to `ps` or `kill`.

**Platform**: Linux only (requires `/proc` filesystem).

---

## Installation

```bash
cargo build --release
# Binary at: target/release/procmon
```

---

## Subcommands

### `procmon list`

Print running processes for the current user in a fixed-width table.

```
PID     PPID    USER        %CPU  %MEM   RSS(KB)    START  COMMAND
--------------------------------------------------------------------------------
1234    1       alice        0.1   0.3     12288    10:42  /usr/bin/bash
5678    1234    alice        1.2   1.0     41720    10:43  cargo build --release
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--sort <pid\|cpu\|mem\|start>` | `pid` | Sort column |
| `--reverse` | false | Reverse sort order |
| `--all` | false | Show all users (default: current user only) |
| `--format <table\|json>` | `table` | Output format |

```bash
procmon list --sort cpu --reverse          # top CPU consumers first
procmon list --all --format json           # all users, JSON output
```

---

### `procmon find <pattern>`

Regex-match processes by command line. Prints the same table as `list`.

```bash
procmon find cargo                         # all processes with "cargo" in cmdline
procmon find "^/usr/bin/python"            # anchored regex
procmon find --exact cargo                 # exact substring, no regex
procmon find cargo --format json           # JSON output
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--exact` | false | Substring match instead of regex |
| `--format <table\|json>` | `table` | Output format |

---

### `procmon kill <pid|pattern>`

Send a signal to a single PID or every process matching a regex pattern.

```bash
procmon kill 5678                          # SIGTERM to PID 5678
procmon kill 5678 --signal SIGKILL         # SIGKILL to PID 5678
procmon kill stale_worker                  # SIGTERM to all matching "stale_worker"
procmon kill 1 --force                     # override protection for PID 1
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--signal <SIG>` | `SIGTERM` | Signal name (SIGTERM, SIGKILL, HUP, …) or number |
| `--force` | false | Allow killing PID 0, PID 1, or the current process |

Supported signal names: `HUP`, `INT`, `QUIT`, `KILL`, `TERM`, `USR1`, `USR2`, `STOP`, `CONT`
(prefix `SIG` is optional: `SIGKILL` and `KILL` both work).

---

### `procmon watch [pattern]`

Refresh the process table every `--interval` seconds. Press Ctrl-C to exit.

```bash
procmon watch                              # all processes, refresh every 2s
procmon watch cargo --interval 1           # filter "cargo", 1s refresh
procmon watch --format json                # JSON frames
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--interval <SECS>` | `2.0` | Refresh interval in seconds |
| `--format <table\|json>` | `table` | Output format |

---

### `procmon tree [--pid <root>]`

Print an ASCII process tree rooted at `<root>`.

```bash
procmon tree                               # tree from PID 1
procmon tree --pid 1234                    # subtree rooted at PID 1234
procmon tree --format json                 # JSON with depth field
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--pid <PID>` | `1` | Root PID |
| `--format <table\|json>` | `table` | Output format |

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Usage error / no process matched |
| `2` | Permission denied (e.g. cannot signal process) |
| `3` | Internal error |

---

## JSON format

Every subcommand accepts `--format json`. Each line is a self-contained JSON object:

```json
{"pid":1234,"ppid":1,"uid":1000,"user":"alice","cpu_pct":0.1,"mem_pct":0.3,"rss_kb":12288,"start_epoch":1751500920,"start_str":"10:42","command":"/usr/bin/bash","comm":"bash","state":"S"}
```

For `tree --format json`, an additional `"depth"` field indicates nesting level.

---

## Dependencies

| Crate | Reason |
|-------|--------|
| `clap` (v4, derive) | Ergonomic CLI argument parsing with auto-generated help |
| `regex` | Required for `find`/`kill` pattern matching |
| `serde` + `serde_json` | JSON serialization for `--format json` |
| `libc` | `kill(2)` syscall and signal constants; `sysconf` for page size and clock ticks |

All process data is read directly from `/proc/[pid]/{stat,status,cmdline,comm}`.
No `ps`, `kill`, or other external commands are invoked.

---

## Design notes

- **TOCTOU**: Processes can disappear between `/proc` enumeration and file reads. All reads are best-effort; missing processes are silently skipped.
- **Signal handling in `watch`**: A `SIGINT` handler sets an atomic flag so the refresh loop exits cleanly on Ctrl-C.
- **CPU %**: Computed as `(utime + stime) / ticks_per_sec / process_elapsed_seconds * 100`. This is a lifetime average, not an instantaneous measurement (which would require two samples).
- **RSS**: Read from `/proc/[pid]/stat` field 24 (pages × page size). Falls back to `VmRSS` in `/proc/[pid]/status` if the stat field is zero or negative.
