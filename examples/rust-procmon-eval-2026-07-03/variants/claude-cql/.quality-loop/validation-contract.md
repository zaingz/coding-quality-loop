# Validation Contract

Each acceptance criterion is paired with the concrete check that proves it.

## AC-1: `procmon list` prints a fixed-width table

**Criterion:** Running `procmon list` outputs a header row (PID, PPID, USER, %CPU, %MEM, RSS(KB), START, COMMAND) followed by at least one process row for the current user. Columns are space-padded to fixed widths.

**Check:**
```bash
./target/release/procmon list | head -5
# Must show header line and at least one data row.
# grep for current user's name or PID.
./target/release/procmon list | grep "$(id -un)"
```
**Sort/reverse:**
```bash
./target/release/procmon list --sort pid | head -3
./target/release/procmon list --sort cpu --reverse | head -3
```

---

## AC-2: `procmon find <pattern>` regex-matches by command line

**Criterion:** `procmon find procmon` finds the running procmon process (or the test invocation). `--exact` switches to substring match.

**Check:**
```bash
./target/release/procmon find sh | grep -i sh
./target/release/procmon find "^/bin" --exact | head -3
```

---

## AC-3: `procmon kill` with safety guards

**Criterion:** Killing PID 1 without `--force` prints an error to stderr and exits with code 1. Killing with a valid PID sends SIGTERM by default.

**Check:**
```bash
./target/release/procmon kill 1; echo "Exit: $?"
# Expected: error message on stderr, exit code 1.
./target/release/procmon kill 0; echo "Exit: $?"
# Expected: error message on stderr, exit code 1.
./target/release/procmon kill 99999999; echo "Exit: $?"
# Expected: no-match error, exit code 1.
```

---

## AC-4: `procmon watch` refreshes and exits on Ctrl-C

**Criterion:** `procmon watch` clears terminal and reprints the table at the configured interval. Ctrl-C produces a clean exit (exit 0).

**Check (manual / CI approximation):**
```bash
timeout 3 ./target/release/procmon watch --interval 1 | head -20
# Should print at least one full table frame before timeout.
```

---

## AC-5: `procmon tree` prints ASCII process tree

**Criterion:** `procmon tree` (rooted at PID 1 by default) prints indented children.

**Check:**
```bash
./target/release/procmon tree | head -20
# Must show PID 1 at root with indented children.
./target/release/procmon tree --pid $$ | head -10
```

---

## AC-6: `--format json` produces valid JSON

**Criterion:** `procmon list --format json` emits one JSON object per line. `procmon find procmon --format json` produces parseable JSON.

**Check:**
```bash
./target/release/procmon list --format json | head -5 | python3 -m json.tool --no-indent
./target/release/procmon find procmon --format json | python3 -c "import sys,json; [json.loads(l) for l in sys.stdin]"; echo "JSON valid: $?"
```

---

## AC-7: `cargo build --release` zero warnings

**Check:**
```bash
. "$HOME/.cargo/env" && cargo build --release 2>&1 | tail -20
# Must end with "Finished release" and no "warning:" lines.
```

---

## AC-8: `cargo test` passes

**Check:**
```bash
. "$HOME/.cargo/env" && cargo test 2>&1 | tail -30
# Must end with "test result: ok" and 0 failures.
```
Required tests:
- Unit test for `/proc/pid/stat` parser.
- Integration test that exercises `list` and `find` against the current process.
- Integration test: spawn child, verify it appears in `list`, verify it disappears after exit.

---

## AC-9: `cargo clippy -- -D warnings` zero warnings

**Check:**
```bash
. "$HOME/.cargo/env" && cargo clippy -- -D warnings 2>&1 | tail -30
# Must not contain any "warning:" or "error:" lines from clippy.
```

---

## AC-10: Killing PID 1 rejected

Already covered in AC-3.

---

## Regression risks
- Parser regression: a change to the stat/status parser could silently produce wrong values. Covered by the unit test.
- Race regression: removing the `NotFound`-ignore logic would panic on short-lived processes. Covered by the child-spawning integration test.
- Signal regression: wrong signal mapping could send the wrong signal. Covered by code review and the kill-PID1 rejection test.

## Evidence required for SHIP
1. Terminal output of all three acceptance commands (build, test, clippy) with pass/fail status.
2. Terminal output of `procmon list`, `procmon find procmon --format json`, and `procmon kill 1`.
3. All saved in completion-record.md.
