# Sudoku Agent Experiment Evaluation

## Experiment setup

Four variants built the same local browser Sudoku application from the shared requirements:

- `claude_skill`: Claude-style coding agent using the `coding-quality-loop` skill from start to finish.
- `openai_skill`: OpenAI-style coding agent using the `coding-quality-loop` skill from start to finish.
- `claude_baseline`: Claude-style coding agent without the skill.
- `openai_baseline`: OpenAI-style coding agent without the skill.

All variants were instructed to avoid pushing, publishing, or opening a PR. The skill variants were required to produce lifecycle artifacts including task contract, context map, validation contract, plan, execution log, decision log, independent review notes, and completion record.

## Orchestrator-owned verification

I reran each app's deterministic test suite:

| Variant | Test command | Result |
|---|---|---:|
| `claude_skill` | `npm test --prefix /home/user/workspace/sudoku-experiment/claude_skill/app` | 9/9 passed |
| `openai_skill` | `npm test --prefix /home/user/workspace/sudoku-experiment/openai_skill/app` | 17/17 passed |
| `claude_baseline` | `npm test --prefix /home/user/workspace/sudoku-experiment/claude_baseline/app` | 11/11 passed |
| `openai_baseline` | `npm test --prefix /home/user/workspace/sudoku-experiment/openai_baseline/app` | 12/12 passed |

I also ran a real-browser Playwright smoke test against all four apps. Each app rendered an ARIA Sudoku grid with 81 cells, produced no console or page errors, accepted digit input in an editable cell, cleared that cell, and moved focus with arrow-key navigation.

## Judge rubric

Each judge scored independently using this 100-point rubric:

- Product functionality and requirement coverage: 30
- Sudoku correctness, generator/solver robustness, performance: 20
- UX, responsiveness, keyboard support, accessibility: 15
- Code quality, maintainability, minimality: 15
- Testing and verification evidence: 10
- Process quality and quality-loop compliance/evidence: 10

For baseline variants, judges did not require the custom skill, but scored available process/evidence and how easy the work would be to trust and review.

## Judge totals

| Variant | Judge A | Judge B | Judge C | Average |
|---|---:|---:|---:|---:|
| `openai_skill` | 95 | 94 | 90 | 93.0 |
| `claude_skill` | 90 | 90 | 86 | 88.7 |
| `openai_baseline` | 87 | 87 | 85 | 86.3 |
| `claude_baseline` | 80 | 81 | 80 | 80.3 |

Final ranking by average score:

1. `openai_skill`: 93.0
2. `claude_skill`: 88.7
3. `openai_baseline`: 86.3
4. `claude_baseline`: 80.3

## Main findings

- The skill variants outperformed the baselines overall. The two skill variants averaged 90.8, while the two baselines averaged 83.3, a lift of about 7.5 points.
- The OpenAI-style skill variant was the strongest overall. Judges highlighted its 17-test suite, MRV solver, contradictory-board guard, no-mutation checks, stricter difficulty tests, and genuinely separate independent reviewer that found and fixed a weak test.
- The Claude-style skill variant was also strong, with clean MRV-based Sudoku logic, a fallback puzzle bank, complete artifacts, and honest caveats. Its main penalty was that independent review was performed as a fresh-context self-review rather than by a genuinely separate validator.
- The OpenAI-style baseline was the strongest baseline. Judges liked its richer UI, README, path-traversal guarded static server, and committed DOM smoke test.
- The Claude-style baseline was solid and functional, but judges found it had the least process evidence, no README/artifact set, logic-only tests, and a less robust naive solver/generator approach.

## Skill enforcement assessment

The `coding-quality-loop` skill appears to have improved:

- Pre-implementation clarity: task contract, validation contract, plan, non-goals, and risks were explicit in the skill variants.
- Solver robustness: both skill variants chose stronger MRV-style solving, while both baselines used more naive first-empty backtracking.
- Evidence quality: skill variants provided more structured completion evidence and quality-loop artifacts.
- Reviewability: completion records and validation contracts made the skill variants easier for judges to inspect and compare.

The skill did not automatically guarantee perfect enforcement in every environment:

- One skill variant had only self-review because a separate validator was not available inside that subagent.
- Some evidence claims still needed orchestrator-owned reruns to avoid trusting agent-authored prose.
- UI verification remained the weakest shared area until the orchestrator added a real-browser smoke test.

## Recommended harness improvements

- Add a harness-owned Playwright or jsdom E2E gate that every variant must pass, covering new puzzle, cell input, locked givens, conflict display, check, reset, reveal, keyboard navigation, and accessibility roles.
- Require evidence claims in completion records to map to committed artifacts or orchestrator-rerunnable commands. This would catch unverifiable claims like a described smoke test that is not present in the app tree.
- Add fixed worst-case seed and performance cases for Sudoku generation and solving, so robustness differences are measured rather than inferred.
- Make independent review a top-level orchestration responsibility for skill variants. The subagent should not be allowed to satisfy the final validator gate with self-review when the experiment is explicitly about skill enforcement.
- Give each judge a unique output path. The shared `/tmp/claude_code_output.md` path caused potential clobbering across concurrent judges.

## Bottom line

The experiment supports the hypothesis that the `coding-quality-loop` skill improves software-agent output quality, mostly by increasing planning discipline, verification quality, solver robustness, and reviewability. The best overall result was `openai_skill`, and the best no-skill baseline was `openai_baseline`. The next experiment should make the evaluation harness more deterministic and machine-owned, especially around browser UI behavior and independent validation.
