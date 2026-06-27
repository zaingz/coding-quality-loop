# Optional: auto-load project memory in Claude Code

The memory layer is a CLI over a checked-in directory, so it works on every host without
hooks. On Claude Code you can *optionally* surface the slim memory index at session start
with a `SessionStart` hook — a thin wrapper around the same CLI, never required.

Add to `.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 -c \"import json,pathlib; p=pathlib.Path('.quality-loop/memory/MEMORY.md'); print(json.dumps({'hookSpecificOutput':{'hookEventName':'SessionStart','additionalContext': p.read_text() if p.exists() else ''}}))\""
          }
        ]
      }
    ]
  }
}
```

This injects only the ≤40-line index (not the full ledger), once per session. For
task-scoped recall, call `python3 scripts/quality_loop.py memory-recall --goal "..."
--files a,b --risk medium` at INTAKE (add `--no-bump` for a read-only recall, e.g. in CI).
Hooks are a Claude-Code-only accelerator; other hosts call the same CLI inline.
