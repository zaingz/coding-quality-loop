# procmon

`procmon` is a small Linux-only process manager written in Rust. It reads `/proc/[pid]/{stat,status,cmdline,comm}` directly and provides script-friendly `list`, `find`, `kill`, `watch`, and `tree` commands.

## Build

```sh
. "$HOME/.cargo/env" && cargo build --release
```

## Usage

```sh
procmon list [--sort pid|cpu|mem|start] [--reverse] [--format table|json]
procmon find <pattern> [--exact] [--format table|json]
procmon kill <pid|pattern> [--signal SIGTERM|SIGKILL|SIGINT|SIGHUP|SIGQUIT|SIGUSR1|SIGUSR2] [--force]
procmon watch [pattern] [--interval SECS] [--format table|json]
procmon tree [--pid PID] [--format table|json]
```

Examples:

```sh
procmon list --sort cpu --reverse
procmon list --format json
procmon find 'ssh|cargo'
procmon find '/usr/bin/python' --exact
procmon kill 12345 --signal SIGTERM
procmon kill 'my-worker' --signal SIGKILL --force
procmon watch cargo --interval 1
procmon watch --format json
procmon tree --pid 1
procmon tree --pid $$ --format json
```

`list` shows processes owned by the current user in this fixed-width table:

```text
PID    PPID   USER        %CPU  %MEM  RSS(KB)  START    COMMAND
```

`find` searches the command line. By default the pattern is a regular expression; `--exact` treats the pattern as a literal substring. `kill` accepts either one PID or a regex pattern. It refuses to signal PID 0, PID 1, and the current `procmon` process unless `--force` is supplied. `watch` refreshes repeatedly using a default interval of 2 seconds and exits under normal Ctrl-C signal handling.

## Output formats

`--format table` is the default. `--format json` prints one JSON object per process for `list`, `find`, and `tree`; tree rows include a `depth` field. `watch --format json` prints one stable frame object per interval:

```json
{"frame":0,"timestamp_unix":1234567890,"processes":[...]}
```

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Usage error or no match |
| 2 | Permission denied while signaling |
| 3 | Internal error |

## Assumptions and dependencies

This is Linux-only and assumes a mounted `/proc` filesystem. Process entries can disappear while being read; those races are skipped. CPU percentage is an approximation based on process CPU ticks, system uptime, and clock ticks. User names come from `/etc/passwd` when available and otherwise fall back to numeric UIDs.

Runtime dependencies are intentionally small: `regex` implements the required regular-expression matching and `libc` provides direct POSIX `kill(2)`, `getuid(2)`, and `sysconf(3)` access without shelling out to `ps` or `kill`.
