# Plan

## Complexity brake decision

Rung evaluation:
1. No change needed — ✗ (new project)
2. Delete/simplify — ✗ (new project)
3. Reuse existing function — ✗ (new project)
4. Standard library — partially (file I/O, process::id, AtomicBool, HashMap, etc.)
5. Native platform — partially (/proc is native Linux)
6. Already-installed dependency — N/A
7. One-liner patch — ✗ (multi-file feature)
8. **Minimal new code** ← chosen, with justified dependencies only

### Dependency justification

| Crate | Rung bypassed | Justification |
|---|---|---|
| `clap` (derive) | Argument parsing | std has no arg parser; hand-rolling would be larger and error-prone. `clap` is the de-facto Rust standard. |
| `regex` | Pattern matching | std has no regex; the feature requires regex. |
| `serde` + `serde_json` | JSON serialization | std has no JSON serializer; `--format json` is an explicit feature requirement. |
| `libc` | Signal constants | Avoids raw integer signal numbers, making the kill dispatch safe and readable. |

No TUI, no async runtime, no database, no HTTP. The dependency set is the minimum to satisfy the stated requirements.

---

## Files to create

```
/variants/claude-cql/
  Cargo.toml
  README.md
  src/
    main.rs         — CLI (clap), dispatch to subcommand handlers
    proc.rs         — /proc parsing: ProcInfo struct, stat/status/cmdline parsers
    table.rs        — fixed-width table formatter
    output.rs       — format dispatcher (table vs JSON via serde_json)
    signals.rs      — signal name parsing, kill dispatch (libc::kill)
    tree.rs         — process tree builder, ASCII printer
    watch.rs        — watch loop (AtomicBool + Ctrl-C handler)
    error.rs        — AppError enum, exit-code mapping
  tests/
    integration.rs  — integration tests
```

## Implementation slices

### Slice 1: Cargo project scaffold + proc.rs
- `cargo init --name procmon`
- Add dependencies to Cargo.toml
- Implement `ProcInfo` struct, stat parser, status parser, cmdline reader
- Unit test for stat parser

### Slice 2: table.rs + output.rs + `procmon list`
- Fixed-width table formatter
- JSON output via serde_json
- `list` subcommand: read all /proc entries, filter by uid, sort, format

### Slice 3: `procmon find` + error.rs
- Regex and exact matching
- AppError enum with exit codes
- `find` subcommand

### Slice 4: signals.rs + `procmon kill`
- Signal name → libc constant map
- kill dispatch with PID 0/1/self guards
- `kill` subcommand

### Slice 5: tree.rs + `procmon tree`
- Build parent→children map
- ASCII DFS printer
- `tree` subcommand

### Slice 6: watch.rs + `procmon watch`
- AtomicBool Ctrl-C handler
- Clear-and-reprint loop
- Interval from CLI

### Slice 7: integration tests + README
- Spawn child process, verify list/find
- PID 1 kill rejection test
- README with usage examples

## Verification commands
```bash
. "$HOME/.cargo/env" && cargo build --release 2>&1 | tail -20
. "$HOME/.cargo/env" && cargo test 2>&1 | tail -30
. "$HOME/.cargo/env" && cargo clippy -- -D warnings 2>&1 | tail -30
```

## Risks
- Stat parser: `comm` field can contain spaces and `(` `)` — must parse from the last `)`.
- /proc race: processes die between listing and reading — all per-pid reads return `Option`, silently skip on `NotFound`.
- Signal `unsafe`: `libc::kill` requires `unsafe` block — document in decision log.
- %CPU single-shot: unavoidable without two snapshots; report 0.0 in list/find, compute delta in watch.

## Rollback
New project — no existing code is modified. Rollback = delete the directory.

## Non-goals (in plan)
- %CPU in single-shot list/find (0.0, documented)
- Interactive TUI
- Windows/macOS
