# Plan

## Complexity brake before implementation
Chosen rung: minimal new code with standard library only. Lower rungs are insufficient because the workdir has no existing library code and the brief explicitly requires implementing BM25, tokenization, fuzzy matching, boolean parsing, snippets, serialization, and benchmark without runtime dependencies.

## Slices
1. Package scaffolding: `package.json`, `tsconfig.json`, directory structure, README skeleton.
2. Core index: types, Unicode tokenizer, stopwords, field extraction, postings, BM25 scoring, add/remove/update, introspection.
3. Query engine: structured queries, string lexer/parser, boolean set operations, phrase/slop, prefix, fuzzy.
4. Result shaping: deterministic sorting, matched metadata, filters/pagination, snippets.
5. Serialization: snapshot and restore.
6. Tests: required scenarios and edge cases.
7. Benchmark: deterministic corpus, workloads, timing summary JSON.
8. Verification/review: run commands, inspect diff, complete artifacts.

## Rollback path
Because this is a new package in an empty variant directory, rollback is to remove the newly added package/source/test/bench files or revert to the pre-implementation tree; no external state is changed.

## Non-goals
No extra frameworks, no runtime dependencies, no publishing, no commits.
