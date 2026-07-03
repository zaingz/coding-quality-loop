# Build task: In-memory TypeScript search library (baseline)

You are a coding agent in a fresh shell. Your working directory is given below. Node 20 and npm are pre-installed. `npm install` works.

## Task

Read `/home/user/workspace/ts-search-eval-2026-07-03/brief/TASK.md` in full. Build the library it describes, in your working directory.

## Working directory

**{{WORKDIR}}**

All source, tests, bench, package.json, README go here. Do not write outside it. Do not `git commit` or `git push`.

## Constraints

- Zero runtime dependencies. Dev deps: typescript, @types/node only.
- Strict TypeScript. No `any`. No `@ts-ignore` without justification.
- Node's built-in test runner (`node --test`) — no jest/vitest/mocha.
- The library must be a real, working search index — not a stub.
- Include the benchmark harness at `bench/bench.ts` as specified.

## Acceptance

At the end, run:
- `npm install`
- `npm run build` (or `npx tsc` if you didn't set up the script)
- `npm test` (or `node --test dist/test/**/*.test.js` after compile)
- Run the benchmark and print its JSON output.

Print a one-paragraph summary and pass/fail status for each acceptance check.

## Do NOT

- Do not preload or use any engineering-process skill.
- Do not install extra dev tooling (no jest, vitest, eslint, prettier, ts-node, tsx, etc.).
- Do not commit `node_modules/` or `dist/`.
- Do not push to any git remote.
