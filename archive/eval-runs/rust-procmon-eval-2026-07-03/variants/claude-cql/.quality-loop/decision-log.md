# Decision Log

## D-01: %CPU single-shot strategy
**Decision:** `cpu_pct` is always `0.0` in `list`/`find`. Only `watch` can compute a delta.
**Rationale:** A single snapshot cannot produce a meaningful CPU percentage. Options were: (a) sleep briefly and take two snapshots in `list` — adds latency; (b) report 0.0 and document — chosen. Documented in README.
**Impact:** Users see 0.0 in `list`/`find`. This is the standard behavior of most tools for single-shot reads.

## D-02: `find` does not filter by UID
**Decision:** `find` matches across all visible processes (not just the current user's).
**Rationale:** `pgrep` semantics: `find` is a search tool, not a "my processes" view. `list` filters by UID, `find` does not. This matches the task spec ("regex-match processes by command line").
**Impact:** Consistent with the task spec; documented implicitly by behavior.

## D-03: Parse `/proc/pid/stat` comm field via last `)`
**Decision:** Use `rfind(')')` to find the end of the `comm` field rather than `find(')')`.
**Rationale:** The `comm` field can contain literal `()` characters (e.g., `my (weird) proc`). Using `rfind` correctly handles all cases. This is the standard approach.

## D-04: `unsafe` blocks — 4 sites, all documented
**Decision:** Accept 4 `unsafe` blocks: `libc::getuid()`, `libc::kill()`, and two `libc::signal()` calls in `watch.rs`.
**Rationale:** All four are direct Linux syscall wrappers with no memory aliasing risk. No `unsafe` is used for pointer arithmetic, raw memory access, or transmutes. Each is annotated with a `// Safety:` comment.

## D-05: `total_cmp` instead of `partial_cmp().unwrap()` for float sort
**Decision:** Use `f64::total_cmp` for sorting by cpu_pct and mem_pct.
**Rationale:** Identified during independent review. `partial_cmp().unwrap()` panics on NaN; `total_cmp` provides a total ordering over all floats including NaN. Defensive choice with zero overhead.

## D-06: Integration test anchored regex for no-match case
**Decision:** Use `^IMPOSSIBLE_DEADBEEF_WONTMATCH_1234567890$` rather than a plain string for the "no match" test.
**Rationale:** `procmon find <pattern>` passes the pattern as argv, so any unanchored string would match procmon's own command line. Anchoring prevents false self-match.

## D-07: `libc` signal handler via `*const () as sighandler_t`
**Decision:** Cast `handle_sigint` as `*const () as libc::sighandler_t` rather than direct cast.
**Rationale:** The direct cast `handle_sigint as libc::sighandler_t` triggers Rust's `function_casts_as_integer` lint (now warning-by-default). The two-step cast through `*const ()` is the recommended workaround and passes clippy cleanly.
