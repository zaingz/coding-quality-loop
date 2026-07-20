# Quality Loop Packager

Package the verified change without adding new claims.

Record:
{record}

Return JSON completion_record fields only (mirrors assets/completion-record.md):
- goal: one sentence, the contract's goal
- files_changed: list of paths with what/why
- right_size_decision: rung chosen and why lower rungs were insufficient
- evidence: list of command -> result entries drawn from commands_run
- risks: list of open risks
- rollback: how to undo the change if it ships broken
- follow_ups: list (empty if none)
