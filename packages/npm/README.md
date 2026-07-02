# coding-quality-loop

One-command installer for the [Coding Quality Loop](https://github.com/zaingz/coding-quality-loop) skill — an engineering operating system that makes AI coding agents ship small, verified changes you can trust.

## Install

```bash
npx coding-quality-loop init
```

That's it. The installer auto-detects your host (Claude Code, Codex, Cursor, Droid, Pi), copies the skill files, wires the hooks, and prints next steps. No prerequisites beyond Node 18+ and Python 3.

## Commands

```bash
npx coding-quality-loop init              # interactive install
npx coding-quality-loop init --yes        # accept all defaults
npx coding-quality-loop init --host codex # skip host detection
npx coding-quality-loop init --dry-run    # preview without writing
npx coding-quality-loop add git           # add a single host later
npx coding-quality-loop check             # verify install is intact
npx cql --help                            # short alias also works
```

## What it installs

Depending on the host you pick:

- **Claude Code** — copies the skill to `.claude/skills/coding-quality-loop/`, wires `.claude/settings.json` hooks (`PreToolUse`, `Stop`, `SessionStart`), and installs review/security-review subagents.
- **Codex** — copies `AGENTS.md` and wires `.codex/hooks.json`.
- **Cursor** — copies `.cursor/rules/coding-quality-loop.mdc`.
- **Droid** — copies role droids into `.factory/droids/`.
- **Pi** — copies `.pi/` skill rules.
- **Git backstop** (recommended) — installs a pre-commit hook that runs `diff-audit --staged` to block secrets, weakened tests, and untracked-file leaks before commit.

All installs are idempotent, non-destructive (existing files are backed up as `.bak`), and can be previewed with `--dry-run`.

## After install

```bash
# 1. Configure per-role model routing once
python3 scripts/quality_loop.py setup-models --host claude-code

# 2. Try it out
claude "Use coding-quality-loop to fix a small bug"

# 3. Run the eval suite (~2 seconds, no deps)
python3 evals/run_evals.py
```

## Docs

Full documentation, philosophy, and eval results are in the [main repository](https://github.com/zaingz/coding-quality-loop).

## License

[MIT](https://github.com/zaingz/coding-quality-loop/blob/main/LICENSE)
