# procmon — Linux process monitor

A scriptable command-line process manager for Linux. Think a minimal, scriptable subset of `htop` / `pgrep` / `pkill` combined — callable from shell scripts and interactive use.

**Linux-only.** Reads `/proc/[pid]/{stat,status,cmdline,comm}` directly — no calls to `ps`, `kill`, or other utilities.

---

## Build

```bash
cargo build --release
./target/release/procmon --help
```

## Subcommands

### `procmon list`

Print running processes for the current user in a fixed-width table.

```
PID     PPID    USER         %CPU   %MEM    RSS(KB) START     COMMAND
1234    1       user          0.0    0.3      28000 10:42     bash
5678    1234    user          0.0    0.1       4276 10:43     ./procmon list
```

Options:
- `--sort <pid|cpu|mem|start>` — sort column (default: `pid`)
- `--reverse` — reverse sort order
- `--format <table|json>` — output format (default: `table`)

```bash
procmon list
procmon list --sort mem --reverse
procmon list --format json
```

> **Note:** `%CPU` is reported as `0.0` in single-shot commands (`list`, `find`).
> A meaningful CPU percentage requires two snapshots; use `watch` for live CPU%.

### `procmon find <pattern>`

Regex-match processes by command line. Prints the same table as `list`.

Options:
- `--exact` — substring match instead of regex
- `--format <table|json>`

```bash
procmon find bash
procmon find "^/usr/bin"
procmon find nginx --exact
procmon find python --format json
```

Exit codes: `0` = matches found, `1` = no match.

### `procmon kill <pid|pattern> [--signal NAME]`

Send a signal to a single PID or every process matching a regex pattern.

- Default signal: `SIGTERM`
- Refused targets (without `--force`): PID 0, PID 1, the current process
- Exit non-zero if no process matched

Options:
- `--signal <name|number>` — signal to send (e.g. `SIGKILL`, `SIGTERM`, `9`)
- `--force` — override the PID 0/1/self guard

```bash
procmon kill 9999
procmon kill nginx --signal SIGKILL
procmon kill "stale-worker-.*" --signal SIGTERM
procmon kill 1 --force   # dangerous — use with care
```

### `procmon watch [pattern] [--interval SECS]`

Clear-and-reprint the process table on each refresh. Exit cleanly with Ctrl-C.

Options:
- `pattern` — optional regex to filter processes
- `--interval <float>` — refresh interval in seconds (default: `2.0`)
- `--format <table|json>`

```bash
procmon watch
procmon watch nginx --interval 1
procmon watch --format json --interval 0.5
```

### `procmon tree [--pid <root>]`

Print an ASCII process tree rooted at a PID (default: PID 1).

Options:
- `--pid <root>` — root PID (default: `1`)
- `--format <table|json>`

```bash
procmon tree
procmon tree --pid $$
procmon tree --format json | python3 -m json.tool
```

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Usage error or no matching processes |
| `2` | Permission denied |
| `3` | Internal error |

---

## JSON format

With `--format json`, each process is printed as one JSON object per line (NDJSON):

```json
{"pid":1234,"ppid":1,"uid":1000,"user":"alice","state":"S","cpu_ticks":100,"rss_kb":28000,"mem_pct":0.34,"cpu_pct":0.0,"start_time":1690000000,"start_fmt":"10:42","command":"/bin/bash","comm":"bash"}
```

---

## Dependencies

| Crate | Version | Justification |
|-------|---------|---------------|
| `clap` | 4 | Argument parsing. The standard library has no arg parser; hand-rolling is larger and less ergonomic. |
| `regex` | 1 | Pattern matching in `find`/`kill`/`watch`. The standard library has no regex engine. |
| `serde` + `serde_json` | 1 | JSON serialization for `--format json`. No JSON serializer in std. |
| `libc` | 0.2 | Signal constants and `kill(2)` syscall. Avoids raw signal numbers; keeps the single `unsafe` block minimal. |

---

## Assumptions / Limitations

- **Linux only.** Assumes `/proc` is mounted (standard on any Linux).
- **%CPU in `list`/`find`:** always reported as `0.0`. Meaningful CPU% requires two snapshots separated in time; use `watch` for live values.
- **No root-specific features:** operates within normal user permissions. Sending signals to processes owned by other users will fail with a permission error (exit 2).
- **Kernel threads:** appear as `[comm]` in the COMMAND column (empty cmdline).
- **Race safety:** if a process exits between listing `/proc` and reading its files, the entry is silently skipped.
