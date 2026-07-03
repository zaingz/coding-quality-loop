# Machine checks (2026-07-03)

## codex-baseline

- Source LOC (src/*.rs): 929
- Test LOC (tests/*.rs): 42
- README lines: 49
- Runtime deps: 5 (regex = "1.10",serde = { version = "1.0", features = ["derive"] },serde_json = "1.0",libc = "0.2",ctrlc = "3.4",)
- Quality-loop artifacts: none

### Build/test/clippy
```
-- cargo build --release --
   Compiling itoa v1.0.18
   Compiling ctrlc v3.5.2
   Compiling regex v1.12.4
   Compiling procmon v0.1.0 (/home/user/workspace/rust-eval-2026-07-03/variants/codex-baseline)
    Finished `release` profile [optimized] target(s) in 18.42s
-- cargo test --
running 3 tests
test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
running 3 tests
test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.01s
-- cargo clippy -- -D warnings --
    Checking serde v1.0.228
    Checking regex v1.12.4
    Checking ctrlc v3.5.2
    Checking procmon v0.1.0 (/home/user/workspace/rust-eval-2026-07-03/variants/codex-baseline)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 3.50s
```

## codex-cql

- Source LOC (src/*.rs): 932
- Test LOC (tests/*.rs): 33
- README lines: 65
- Runtime deps: 2 (libc = "0.2",regex = "1",)
- Quality-loop artifacts: completion-record.md context-map.md decision-log.md execution-log.md plan.md task-contract.md validation-contract.md 

### Build/test/clippy
```
-- cargo build --release --
   Compiling aho-corasick v1.1.4
   Compiling regex-automata v0.4.14
   Compiling regex v1.12.4
   Compiling procmon v0.1.0 (/home/user/workspace/rust-eval-2026-07-03/variants/codex-cql)
    Finished `release` profile [optimized] target(s) in 13.37s
-- cargo test --
running 5 tests
test result: ok. 5 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
running 0 tests
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
running 3 tests
test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.01s
running 0 tests
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
-- cargo clippy -- -D warnings --
    Checking libc v0.2.186
    Checking regex-automata v0.4.14
    Checking regex v1.12.4
    Checking procmon v0.1.0 (/home/user/workspace/rust-eval-2026-07-03/variants/codex-cql)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 2.39s
```

## claude-baseline

- Source LOC (src/*.rs): 744
- Test LOC (tests/*.rs): 187
- README lines: 170
- Runtime deps: 5 (clap = { version = "4", features = ["derive"] },regex = "1",serde = { version = "1", features = ["derive"] },serde_json = "1",libc = "0.2",)
- Quality-loop artifacts: none

### Build/test/clippy
```
-- cargo build --release --
   Compiling itoa v1.0.18
   Compiling clap v4.6.1
   Compiling regex v1.12.4
   Compiling procmon v0.1.0 (/home/user/workspace/rust-eval-2026-07-03/variants/claude-baseline)
    Finished `release` profile [optimized] target(s) in 28.00s
-- cargo test --
running 0 tests
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
running 12 tests
test result: ok. 12 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.11s
-- cargo clippy -- -D warnings --
    Checking regex v1.12.4
    Checking libc v0.2.186
    Checking clap v4.6.1
    Checking procmon v0.1.0 (/home/user/workspace/rust-eval-2026-07-03/variants/claude-baseline)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 4.72s
```

## claude-cql

- Source LOC (src/*.rs): 968
- Test LOC (tests/*.rs): 214
- README lines: 147
- Runtime deps: 5 (clap = { version = "4", features = ["derive"] },regex = "1",serde = { version = "1", features = ["derive"] },serde_json = "1",libc = "0.2",)
- Quality-loop artifacts: completion-record.md context-map.md decision-log.md execution-log.md plan.md task-contract.md validation-contract.md 

### Build/test/clippy
```
-- cargo build --release --
   Compiling itoa v1.0.18
   Compiling clap v4.6.1
   Compiling regex v1.12.4
   Compiling procmon v0.1.0 (/home/user/workspace/rust-eval-2026-07-03/variants/claude-cql)
    Finished `release` profile [optimized] target(s) in 25.98s
-- cargo test --
running 6 tests
test result: ok. 6 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
running 13 tests
test result: ok. 13 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.21s
-- cargo clippy -- -D warnings --
    = note: `-D unused-imports` implied by `-D warnings`
    = help: to override `-D warnings` add `#[allow(unused_imports)]`

error: could not compile `procmon` (test "integration") due to 1 previous error
warning: build failed, waiting for other jobs to finish...
```

