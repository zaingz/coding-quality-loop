# coding-quality-loop

[![npm](https://img.shields.io/npm/v/coding-quality-loop?style=flat-square&color=111111&label=npm)](https://www.npmjs.com/package/coding-quality-loop)
[![signed provenance](https://img.shields.io/badge/provenance-signed-111111?style=flat-square&logo=sigstore&logoColor=white)](https://search.sigstore.dev/?logIndex=2050768324)
[![zero deps](https://img.shields.io/badge/runtime%20deps-none-111111?style=flat-square)](package.json)

One-command installer for the [Coding Quality Loop](https://github.com/zaingz/coding-quality-loop) skill — an engineering operating system that makes AI coding agents ship small, verified changes you can trust.

## Install

```bash
npx coding-quality-loop init
```

That's it. The installer auto-detects your host, copies the skill files, wires the hooks, and prints next steps. No prerequisites beyond Node 18+ and Python 3. The routed loop runs **Claude Code (implementer) + Codex (independent reviewer)**; Droid is a supported install target outside that two-vendor kernel.

## Commands

```bash
npx coding-quality-loop init              # interactive install
npx coding-quality-loop init --yes        # accept all defaults
npx coding-quality-loop init --host codex # skip host detection
npx coding-quality-loop init --dry-run    # preview without writing
npx coding-quality-loop add git           # add a single host later
npx coding-quality-loop check             # verify a prior install against its manifest
npx coding-quality-loop remove            # uninstall: remove installed files, reverse hook wiring
npx cql --help                            # short alias also works
```

Every install writes a manifest at `.quality-loop/install-manifest.json` recording each file written and each hook group merged. `cql check` verifies the install against that manifest, and `cql remove` uninstalls from it — restoring any `.bak` backups of your pre-install files and leaving your own files alone.

## What it installs

Depending on the host you pick:

- **Claude Code** — copies the skill (`SKILL.md`, `references/`, `assets/`) to `.claude/skills/coding-quality-loop/`, vendors the runtime scripts once at `scripts/`, wires `.claude/settings.json` hooks (`PreToolUse`, `Stop`, `SessionStart`), and installs review/security-review subagents.
- **Codex** — copies `AGENTS.md` (created from the bundled template; if you already have one, a clearly-marked managed section is appended instead) and wires `.codex/hooks.json`.
- **Droid** — copies role droids into `.factory/droids/`.
- **Git backstop** (recommended) — installs a pre-commit hook that runs `diff-audit --staged` to block secrets, weakened tests, and untracked-file leaks before commit.

Cursor and Pi are not runtime install targets: advisory rules recipes for them live in the repository's [`examples/`](https://github.com/zaingz/coding-quality-loop/tree/main/examples) directory.

All installs are idempotent, non-destructive (your pre-existing files are backed up as `.bak`), and can be previewed with `--dry-run`.

## After install

```bash
# 0. Commit the install so the diff gates start from a clean base
git add -A && git commit -m "chore: install coding-quality-loop"

# 1. Create your config from the installed example
cp assets/quality-loop.config.example.json quality-loop.config.json

# 2. Configure per-role model routing once
python3 scripts/quality_loop.py setup-models --host claude-code

# 3. Try it out
claude "Use coding-quality-loop to fix a small bug"
```

## Docs

Full documentation, philosophy, and eval results are in the [main repository](https://github.com/zaingz/coding-quality-loop).

## License

[MIT](https://github.com/zaingz/coding-quality-loop/blob/main/LICENSE)
