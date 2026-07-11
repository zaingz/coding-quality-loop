# Project Memory (index)

2 lesson(s). Recall detail with: python3 scripts/quality_loop.py memory-recall.

- [gotcha/low] Attest-last only works when the working record lives at .quality-loop/agent-record.json (the attestation hash excludes .quality-loop/ but NOT a root-level record, so post-attest record edits stale the review); both host hooks check the .quality-loop/ path first.
- [failure_mode/low] Multi-host routing review lesson: the reviewer's agents-map entry is what setup-models applies, so any independence gate must resolve THAT (not just the REVIEW step class) or the applier and the gate disagree; caught by fresh-context swarm review, pinned in case_cross_host_family.
