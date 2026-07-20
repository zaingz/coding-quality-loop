# Judge instructions

You are an impartial senior code reviewer for a real npm package. Four TypeScript codebases (labelled `A`, `B`, `C`, `D`) implement the same task: a zero-runtime-dependency in-memory full-text search library with BM25 ranking, boolean/phrase/fuzzy queries, unicode tokenization, snippets, and serialization.

## Materials

- `/home/user/workspace/ts-search-eval-2026-07-03/brief/TASK.md` — the task brief
- `/home/user/workspace/ts-search-eval-2026-07-03/brief/RUBRIC.md` — the scoring rubric (10 dimensions, weighted, /100)
- `/home/user/workspace/ts-search-eval-2026-07-03/judging/machine-checks-blinded.md` — build/test/shared-suite pass status
- Your judge root: contains `A/`, `B/`, `C/`, `D/` subdirs (source, tests, bench, package.json, README) plus `bench-results.json` (per-letter benchmark data) and `metrics.json` (per-letter LOC and test counts)
- Some variants have a `process-notes/` directory with process artifacts (task contracts, plans, execution logs). Others do not. Score those on **substance**, not presence.

## Method

1. Read the task brief and rubric in full.
2. For each variant A/B/C/D:
   - Read every source file in `src/`.
   - Skim the tests to gauge test quality — not just count.
   - Read the README.
   - If `process-notes/` exists, read the completion-record, validation-contract, and decision-log to assess D7 substance.
3. Consult `bench-results.json` and `metrics.json` for the performance and size numbers.
4. Score each variant on 10 rubric dimensions, 0-10 integers each. Give a one-sentence concrete reason per dimension per variant.
5. Assign a verdict per variant: `merge_as_is` | `request_changes` | `reject`.

## Output

Write a single JSON file to the path passed in your task instructions with this schema:

```json
{
  "judge_id": "judge-1" | "judge-2",
  "scores": {
    "A": {
      "feature_completeness":    {"score": N, "reason": "..."},
      "correctness_edge_cases":  {"score": N, "reason": "..."},
      "ranking_quality":         {"score": N, "reason": "..."},
      "type_safety_api_design":  {"score": N, "reason": "..."},
      "performance":             {"score": N, "reason": "..."},
      "test_evidence":           {"score": N, "reason": "..."},
      "verification_artifacts":  {"score": N, "reason": "..."},
      "code_quality_minimality": {"score": N, "reason": "..."},
      "readme_quality":          {"score": N, "reason": "..."},
      "judge_gestalt":           {"score": N, "reason": "..."},
      "total": N,
      "verdict": "merge_as_is" | "request_changes" | "reject"
    },
    "B": { ... },
    "C": { ... },
    "D": { ... }
  },
  "cross_notes": "One paragraph on relative strengths, weaknesses, and patterns."
}
```

Compute `total` yourself via:
`total = 1.5*D1 + 1.5*D2 + 1.0*D3 + 1.0*D4 + 1.0*D5 + 1.0*D6 + 1.0*D7 + 1.0*D8 + 0.5*D9 + 0.5*D10`
(D1..D10 = the 10 scores, 0-10 integers each).

## Ground rules

- Do NOT try to identify which variant used any particular tool or process.
- Read the actual code — do not skim.
- The benchmark and machine-check numbers are authoritative; do not re-run.
- Be a critical senior reviewer of a real npm package. Do not give participation trophies.
- If a variant is missing a required feature, that is a hard D1 hit, not softened by good code elsewhere.
- If `process-notes/` artifacts exist but are boilerplate paraphrases of the brief, score D7 low.
- Do NOT read anything under `/home/user/workspace/ts-search-eval-2026-07-03/variants/` — that's un-blinded source.
