# Security policy

## Reporting a vulnerability

If you find a security issue in the Coding Quality Loop, please report it privately.
Do not open a public issue for anything that would give an attacker a working exploit.

**Preferred**: open a [GitHub security advisory](https://github.com/zaingz/coding-quality-loop/security/advisories/new)
against this repository. GitHub will notify the maintainer and coordinate a fix.

**Fallback**: email `zaingz [at] icloud [dot] com` with `[cql-security]` in the subject
line. Include:

- What the issue is, in one sentence.
- The smallest reproduction you can share.
- Whether you have already disclosed the issue to anyone else.
- Whether you would like public credit for the report.

We aim to acknowledge reports within **72 hours** and to ship or triage a fix within
**14 days** for high-severity issues.

## What is in scope

This project's security surface is small on purpose, but it is not zero:

| Surface | In scope | Notes |
|---|---|---|
| `scripts/quality_loop*.py` | ✅ | Runtime CLI. Stdlib-only. Any injection, path traversal, or unsafe eval is in scope. |
| `run-evidence` command execution | ✅ | Re-executes commands from the record's allowlist. Escaping the allowlist is a security bug. |
| `scan-text --stdin` and `diff-audit` | ✅ | Secret-scan heuristics. False negatives on well-known secret formats are in scope. |
| Redaction in `memory-commit` | ✅ | Secrets leaking into `.quality-loop/memory/` is a security bug. |
| Host hook shims under `hosts/` | ✅ | Injection or privilege escalation through hook input. |
| Templates and examples under `assets/`, `examples/`, `docs/` | ⚠️ Advisory | Wording issues that mislead an agent are welcome as bugs, but not treated as vulns. |

## What is out of scope

- **Sandbox escape from `run-evidence`.** By design, `run-evidence` is not a sandbox. It
  is a repo-authored allowlist runner with the same trust model as CI. If your repo's
  allowlist runs untrusted code, that is a repo configuration bug, not a CQL bug. State it
  plainly: at a terminal Stop the Claude Code hook runs the full `verify` umbrella, which
  **auto-executes** the record's allowlisted `commands_run` strings through a shell — no
  prompt, no confirmation. Anything you put on `.quality-loop/allowed-commands` will run at
  Stop, so treat that allowlist with the same care as a CI step.
- **Merge-base evasion.** The base that every diff-derived gate (risk floor, secrets, scope,
  shrinkage) compares against is a **CI-anchored** guarantee, not a local one. Locally, an
  agent that rewrites refs (e.g. `git update-ref`) can move the resolved base and blind those
  gates, and no gate reads the reflog to catch it — a moved base can also satisfy the Stop
  gate's closed-record predicate. Commit-first evasion is caught in CI, where the base is
  fixed; the local run is a convenience, not the anti-evasion boundary.
- **Install-manifest trust.** Paths listed in `.quality-loop/install-manifest.json` are
  exempt from scope-integrity as scaffolding, by membership only (no hashes). The manifest
  is checkout data — including in CI, where the action runs pinned scripts over the
  checkout's manifest. Membership exempts **only paths matching CQL's own shipped shapes**
  (`quality_loop_core._is_cql_shipped_shape`: the skill/host/prompt/routing prefixes, the
  known scaffolding filenames, or any path containing `quality-loop`/`quality_loop`), so a
  doctored manifest cannot exempt an arbitrary consumer source file (`src/…` stays flagged).
  The residual: an attacker can still exempt a backdoor by *naming* it into a CQL shape
  (e.g. `src/quality_loop_evil.py`) and listing it. Same trust model as the allowlist:
  review what lands in `.quality-loop/`.
- **Missing-record CI bypass.** The GitHub Action defaults `allow-missing-record: true`: a
  loop-configured checkout (has `.quality-loop/` or `quality-loop.config.json`) that ships
  **no record** for a PR runs `diff-audit` only and passes with a loud warning — a
  deliberate green path for docs/dependabot lanes. This is a real bypass of the record
  gates (terminal status, AC coverage, evidence replay, review freshness): deleting the
  record makes a PR take the soft path. Close it for feature work by setting
  `allow-missing-record: false` (hard-fails a record-less loop-configured PR) or a
  required-record branch-protection check.
- **Reviewer identity forgery.** Identity is string-compared and freshness is
  self-attested. `attest-review --against-diff` makes review freshness checkable, but
  cannot prove the reviewer *read* the diff. Treat this as a design boundary.
- **Model or host vulnerabilities.** Report those to the model or host vendor.

## What we will do

For any confirmed vulnerability:

1. Acknowledge the report within 72 hours.
2. Assign a severity (low/medium/high/critical) using the description in
   [CVSS-style terms](https://www.first.org/cvss/) — informally, high or critical is
   "an attacker can act on your repo, secrets, or CI".
3. Fix the issue on `main` and, if the impact is high or critical, tag a patch release.
4. Credit the reporter in the [CHANGELOG](CHANGELOG.md) unless they ask us not to.

## What you should do

Treat this skill like any other dependency:

- **Inspect before you install.** Read `SKILL.md` and `scripts/quality_loop.py`. There is
  no hidden network access; the helper is stdlib-only.
- **Pin for team use.** Install from a tagged release or a pinned tree SHA, not a moving
  branch. The version lives in `SKILL.md` frontmatter and [`CHANGELOG.md`](CHANGELOG.md).
- **Enforce non-negotiables with hooks, not text.** For anything you cannot afford an
  agent to get wrong (secrets, migrations, auth, billing, protected paths), wire
  deterministic host or git hooks.

Thanks for helping keep users safe.
