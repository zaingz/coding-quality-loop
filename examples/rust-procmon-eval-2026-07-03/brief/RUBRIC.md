# Rubric — `procmon` Rust process manager

Score each variant against this rubric. Each dimension is scored **0–10** and weighted; the weighted total is a **/100**.

## Dimensions

### 1. Correctness of core commands (weight 20)
Do `list`, `find`, `kill`, `watch`, `tree`, `--format json` all work as specified? Does the code parse `/proc/[pid]/stat` correctly (`comm` field with embedded spaces/parens handled)? Does `kill` refuse PID 0/1/self without `--force`? Does `find` support both regex and `--exact`?

### 2. Test evidence (weight 15)
Are there real tests, not smoke assertions? Do integration tests spawn processes and observe them via the binary? Is the `/proc/[pid]/stat` parser tested with tricky input (`comm` containing spaces and parens)? Do the tests actually pass on `cargo test`? Penalize `#[ignore]` on tests that should just work.

### 3. Diff / code minimality (weight 10)
Total lines of Rust source (excluding tests and generated code). Dependency count in `Cargo.toml`. Reward small, focused code that reuses the standard library. Penalize speculative abstractions, unused code, and vendored copies of stdlib functionality. As a rough anchor: a competent v1 fits comfortably under **~1500 LOC** and **≤3 runtime deps** on top of the stdlib.

### 4. Safety / robustness (weight 10)
Handling of the classic race: the process dies between `readdir("/proc")` and `read("/proc/pid/stat")`. Behavior on permission errors reading other users' processes. Are `unsafe` blocks avoided, or justified when present? Are exit codes meaningful?

### 5. Idiomatic Rust (weight 10)
`clippy -- -D warnings` clean. Errors use `Result` + `?`, not `panic!`. No `unwrap()` in library code. Uses `Iterator`, `str::split_whitespace`, standard error handling. Does not shell out to `ps`/`kill`.

### 6. README quality (weight 5)
Is the README something you would actually read? Every subcommand shown with a real example. Exit codes documented. Dependency choices justified in one line each. Kept under two pages.

### 7. Verification evidence in the handoff (weight 10)
Beyond passing tests, did the agent record what it did? A validation contract or task contract, a plan, an execution log, or a completion record — anything that lets a reviewer check the work against a stated goal. If the agent only produced code with no artifacts, score this low regardless of code quality. **This is a proxy for whether the agent's process was legible; it is not a fixed template match.**

### 8. Reviewability (weight 10)
If a human maintainer inherited this repo, how quickly could they understand what changed and why? Are commits (if any) atomic and readable? Are the files organized logically? Is there dead code, TODOs, or `println!("debug: ...")` noise?

### 9. Absence of scope creep (weight 5)
Did the agent stay within v1 scope? Bonus surface (a TUI, a daemon, a config file, a plugin system) counts against this dimension unless it was explicitly justified as required by the task. **This is a real risk with capable coding agents.**

### 10. Judge-level qualitative gestalt (weight 5)
The reviewer's honest professional gestalt: would you approve this PR, request small changes, or send it back? Score 10 = "ship as-is", 5 = "request changes", 0 = "would not merge, needs a rewrite".

## Aggregation

`score = 0.20*D1 + 0.15*D2 + 0.10*D3 + 0.10*D4 + 0.10*D5 + 0.05*D6 + 0.10*D7 + 0.10*D8 + 0.05*D9 + 0.05*D10`

Result is a number in **[0, 100]**.

## Judge instructions

- You are one of two blind judges. You will not know which variant used the Coding Quality Loop skill and which did not. The variants are named `A`, `B`, `C`, `D` and are shuffled per judge.
- Score each dimension independently on the four variants. Do not read the other judge's scores before scoring.
- Return one JSON object per variant with `{dimension_1..10: {score, reason}, total, verdict}` where `verdict` is one of `merge_as_is | request_changes | reject`.
- Do not run the code yourself unless a machine-check result is missing from the provided evidence. All required machine checks are pre-computed and included in the packet you are given.
- Be a critical senior engineer. Do not give participation trophies. If a variant is bad, say so.

## Rubric anti-hacks

- If a variant is longer, that is not automatically worse. Judge by what the extra lines *do*.
- If a variant is missing a subcommand, that is a hard hit to D1, not a stylistic preference.
- If a variant produces a validation contract that is 100% boilerplate with no signal, D7 should reflect that.
- Test files that only assert `2 + 2 == 4` count as no tests at all for D2.
