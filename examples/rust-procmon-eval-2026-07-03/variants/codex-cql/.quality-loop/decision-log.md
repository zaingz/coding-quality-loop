# Decision Log

- Classified task as MEDIUM because it creates a multi-file CLI with process signaling behavior.
- Complexity brake: use standard library wherever possible; add `regex` for required regex semantics and `libc` for POSIX signal/user/system calls without shelling out.
- Kept manual CLI parsing and manual JSON line rendering to avoid larger CLI/serialization runtime dependencies for v1 scope.
- Treated `find --exact` as literal substring matching, with regex as the default mode, and documented that behavior in README.
- Added explicit stdout `BrokenPipe` handling after review found piped tree output could otherwise panic when consumers like `head` closed early.
