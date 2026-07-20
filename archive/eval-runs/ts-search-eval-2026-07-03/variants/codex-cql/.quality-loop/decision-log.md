# Decision Log

- Use one public `src/index.ts` module to keep the package small and easy to review.
- Use standard library data structures (`Map`, `Set`, arrays) and no runtime dependencies.
- Rebuild internal postings from serialized docs in `fromJSON` instead of serializing implementation internals; this keeps snapshots plain JSON and resilient.
- Use a compact English stopword list that excludes one-letter query-test tokens while still handling all-stopword queries safely.
- Complexity brake before review: retained minimal new code and no runtime dependencies; generated `dist/` and `node_modules/` exist only as local verification outputs and are not source deliverables.
- Kept query parsing in the library rather than adding parser tooling because the required grammar is small and dependencies are prohibited.
- Used exhaustive re-evaluation for phrase/fuzzy candidates where simpler inverted approaches would complicate correctness; benchmark still completes with the required workload.
