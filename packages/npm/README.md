# coding-quality-loop

[![npm](https://img.shields.io/npm/v/coding-quality-loop?style=flat-square&color=111111&label=npm)](https://www.npmjs.com/package/coding-quality-loop)
[![signed provenance](https://img.shields.io/badge/provenance-signed-111111?style=flat-square&logo=sigstore&logoColor=white)](https://search.sigstore.dev/?logIndex=2050768324)
[![zero deps](https://img.shields.io/badge/runtime%20deps-none-111111?style=flat-square)](package.json)

One-command installer for the [Coding Quality Loop](https://github.com/zaingz/coding-quality-loop) skill — an engineering operating system that makes AI coding agents ship small, verified changes you can trust.

## Install

```bash
npx coding-quality-loop init
```

That's it. The installer auto-detects your host, copies the skill files, wires the hooks, and prints next steps. Requires Node 18+ and Python 3.10+. The routed loop runs **Claude Code (implementer) + Codex (independent reviewer)**; Droid is a supported install target outside that two-vendor kernel.

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

Every install writes a manifest at `.quality-loop/install-manifest.json` recording each file written and each hook group merged. `cql check` verifies the install against that manifest, and `cql remove` uses it to restore backups it can identify as belonging to the install. Ambiguous legacy backup state requires manual reconciliation before removal.

If a v1 manifest or older v2 backup causes a refusal, stop and preserve the manifest, managed files, hooks, and all adjacent backups. Work from a separate project copy, compare each manifest-listed path and backup with independent ownership evidence, and reconcile manually only after ownership is clear. A `.bak` name or matching bytes do not prove who owns a file. Do not rename or delete the manifest or backups, overwrite managed files, or rerun `init`/`remove` as a shortcut. If ownership remains uncertain, leave the original project unchanged and seek manual review.

## What it installs

Depending on the host you pick:

- **Claude Code** — copies the skill (`SKILL.md`, `references/`, `assets/`) to `.claude/skills/coding-quality-loop/`, vendors the runtime scripts once at `scripts/`, wires `.claude/settings.json` hooks (`PreToolUse`, `Stop`, `SessionStart`), and installs review/security-review subagents.
- **Codex** — copies `AGENTS.md` (created from the bundled template; if you already have one, a clearly-marked managed section is appended instead) and wires `.codex/hooks.json`.
- **Droid** — copies role droids into `.factory/droids/`.
- **Git backstop** (recommended) — installs a pre-commit hook that runs `diff-audit --staged` to block secrets, weakened tests, and untracked-file leaks before commit.

Cursor and Pi are not runtime install targets: advisory rules recipes for them live in the repository's [`examples/`](https://github.com/zaingz/coding-quality-loop/tree/main/examples) directory.

Supported installs can be previewed with `--dry-run`. The installer checks managed files and backup ownership before changing them; it refuses unsafe or ambiguous paths, including legacy manifests that cannot be upgraded automatically. Preserve your project changes and reconcile any refusal before retrying.

Run init and remove while no other process is changing the target project. On POSIX, managed-file writes use a no-follow path boundary that rejects a directory symlink swap observed during the write. Full install and removal, including hooks and backups, are not transactions against concurrent target mutation. After an interrupted operation, inspect the manifest, files, hooks, and backups before retrying; a failed operation may have changed some of them.

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
