# Coding Quality Loop (Cursor)

> **Advisory rules only, no runtime.** This example installs the loop's
> *instructions* as a Cursor rule — none of the hook runtime (PreToolUse guard,
> Stop gate, SessionStart brief) runs in Cursor, and the npm installer no longer
> offers Cursor as an install target. Gates fire only if you run
> `python3 scripts/quality_loop.py …` yourself. The routed loop with enforced
> hooks lives on Claude Code + Codex (see the repo README's install matrix).

## Install

```bash
cp -r examples/cursor/.cursor ./.cursor
```

## Use

In chat:

```text
@coding-quality-loop fix the retry bug with verification evidence
```

The rule file is [`.cursor/rules/coding-quality-loop.mdc`](.cursor/rules/coding-quality-loop.mdc).
