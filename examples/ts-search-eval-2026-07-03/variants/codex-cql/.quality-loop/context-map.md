# Context Map

## Repository state
- Workdir initially contains Coding Quality Loop support files only (`.codex/`, `assets/`, `hosts/`, `scripts/`).
- No package source, tests, benchmark, or README existed before implementation.

## Entry points to create
- `src/index.ts`: public API exports, tokenizer, query types, index implementation.
- `test/search-index.test.ts`: Node built-in tests compiled by `tsc` and run from `dist/test`.
- `bench/bench.ts`: deterministic corpus/workload benchmark.
- `bench/words.ts`: deterministic fixed vocabulary used by benchmark.
- `package.json`, `tsconfig.json`, `README.md`.

## Contracts touched
- Public TypeScript API: `SearchIndex`, constructor options, query/result/snapshot types.
- Package scripts: `build`, `test`, `bench`.
- Serialization: plain JSON snapshot without functions.

## Existing patterns/utilities
- No application code existed to reuse.
- Node standard library and TypeScript compiler are sufficient.

## Likely risks
- Boolean parser precedence and implicit operators.
- Stopword removal accidentally removing test terms.
- Removing/updating documents leaving orphaned postings.
- Unicode normalization/combining marks.
- Fuzzy query performance; acceptable for in-memory benchmark with bounded vocabulary.
- Snippet matching when requested field does not contain a matched term.

## Verification commands
- `npm install`
- `npm run build`
- `npm test`
- `node -e "console.log(Object.keys(require('./package.json').dependencies || {}).length)"`
- `npm run bench`
