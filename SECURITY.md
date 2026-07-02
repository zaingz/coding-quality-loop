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
| Honcho boundary redaction | ✅ | Anything reaching `api.honcho.dev` or a self-hosted Honcho that should have been redacted. |
| Host hook shims under `hosts/` | ✅ | Injection or privilege escalation through hook input. |
| Templates and examples under `assets/`, `examples/`, `docs/` | ⚠️ Advisory | Wording issues that mislead an agent are welcome as bugs, but not treated as vulns. |

## What is out of scope

- **Sandbox escape from `run-evidence`.** By design, `run-evidence` is not a sandbox. It
  is a repo-authored allowlist runner with the same trust model as CI. If your repo's
  allowlist runs untrusted code, that is a repo configuration bug, not a CQL bug.
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
