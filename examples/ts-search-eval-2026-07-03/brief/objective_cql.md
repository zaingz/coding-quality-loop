# Build task: In-memory TypeScript search library (with Coding Quality Loop)

You are a coding agent in a fresh shell. Your working directory is given below. Node 20 and npm are pre-installed. `npm install` works.

## Skill guidance

Your working directory has the **Coding Quality Loop** engineering process pre-installed:
- `.codex/` (host: codex), or
- `.claude/skills/coding-quality-loop/SKILL.md` (host: claude-code)

**Load it and follow it.** This is a MEDIUM-to-mission task (multi-module, non-trivial ranking algorithm, unicode edge cases, benchmark harness). The skill requires:

1. **INTAKE** — task contract.
2. **CONTEXT MAP** — narrow findings.
3. **VALIDATION CONTRACT** — pair each acceptance criterion with the concrete check that proves it.
4. **COMPLEXITY BRAKE** — pick highest valid rung; the brief says zero runtime deps, so you MUST implement BM25, tokenization, fuzzy, and phrase-proximity yourself.
5. **PLAN** — files, slices, verification commands.
6. **IMPLEMENT IN SMALL SLICES** — coherent slices.
7. **VERIFY** — run acceptance checks.
8. **INDEPENDENT REVIEW** — self-review the diff against the validation contract.
9. **COMPLETION RECORD**.

Save the mission artifacts under `{{WORKDIR}}/.quality-loop/`:
- task-contract.md
- context-map.md
- validation-contract.md
- plan.md
- execution-log.md
- decision-log.md
- completion-record.md

## Task

Read `/home/user/workspace/ts-search-eval-2026-07-03/brief/TASK.md` in full. Build the library it describes, in your working directory.

## Working directory

**{{WORKDIR}}**

## Constraints (re-emphasized)

- Zero runtime dependencies.
- Strict TypeScript. No `any`.
- Node's built-in test runner (`node --test`) — no jest/vitest/mocha.
- Benchmark harness at `bench/bench.ts`.

## Acceptance

Run at the end:
- `npm install`
- `npm run build`
- `npm test`
- Run the benchmark and print its JSON output.

## Do NOT

- Do not install extra dev tooling.
- Do not commit `node_modules/` or `dist/`.
- Do not push to any git remote.
- Do not skip the quality-loop artifacts — they are part of the deliverable.
