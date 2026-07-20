# procmon

`procmon` is a small Linux-only process manager written in Rust. It reads `/proc/[pid]/{stat,status,cmdline,comm}` directly and never shells out to `ps` or `kill`.

## Build

```sh
. "$HOME/.cargo/env" && cargo build --release
```

## Usage

```text
procmon list [--sort pid|cpu|mem|start] [--reverse] [--format table|json]
procmon find <pattern> [--exact] [--format table|json]
procmon kill <pid|pattern> [--signal SIGTERM|SIGKILL|...] [--force]
procmon watch [pattern] [--interval SECS] [--format table|json]
procmon tree [--pid <root>] [--format table|json]
```

Examples:

```sh
procmon list --sort cpu --reverse
procmon list --format json
procmon find 'ssh|bash'
procmon find bash --exact
procmon kill 12345 --signal SIGTERM
procmon kill 'my-worker' --signal SIGKILL
procmon watch procmon --interval 1
procmon tree --pid 1
```

`list`, `find`, and `tree --format json` print one JSON object per process. `watch --format json` prints one stable frame object per refresh. The `START` column is a Unix timestamp in seconds. `%CPU` is lifetime CPU time divided by elapsed runtime; `%MEM` is RSS divided by `/proc/meminfo` MemTotal.

`kill` refuses PID 0, PID 1, and `procmon`'s own PID unless `--force` is supplied. Supported signal names are `SIGHUP`, `SIGINT`, `SIGQUIT`, `SIGKILL`, `SIGTERM`, `SIGSTOP`, `SIGCONT`, `SIGUSR1`, and `SIGUSR2`; the `SIG` prefix is optional.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Usage error or no match |
| 2 | Permission denied |
| 3 | Internal error |

## Dependencies

Runtime dependencies are intentionally small: `regex` for process matching, `serde`/`serde_json` for JSON output, `ctrlc` for graceful watch shutdown, and `libc` for the Linux `kill(2)` call. The only `unsafe` block wraps `libc::kill`; it passes integer PID/signal values and checks the OS error immediately.
