# Contributing to the Coding Quality Loop

Thanks for wanting to help. This project ships a single [Agent Skill](https://agentskills.io/specification)
package plus a stdlib-only Python helper. The bar for contributions is small, but the
process is unusual: **the repo uses its own loop on itself.**

## The one-line summary

1. Open an issue that names the problem.
2. Ship the smallest correct change with proof.
3. Let a reviewer other than yourself approve it.

## Before you open a PR

Every PR must pass the same loop the skill teaches. That is not ceremony — it is how
the repo stays trustable.

- [ ] The change matches an existing issue, or a new one you filed first.
- [ ] Your PR body includes a **task contract** (goal, acceptance criteria, constraints,
      risk tier). The [contract template](assets/contract.md) is a good
      starting point.
- [ ] The diff is the **smallest safe rung**. If you rewrote something, say why in the PR
      body.
- [ ] You added or updated an eval case for anything gate-related. Advisory changes to
      instructions do not need evals, but changes to `scripts/quality_loop*.py` do.
- [ ] The full local verification suite passes:

      ```bash
      python3 -m py_compile scripts/*.py evals/*.py
      python3 scripts/quality_loop.py check-config assets/quality-loop.config.example.json
      python3 scripts/quality_loop.py eval-cases evals/cases --config assets/quality-loop.config.example.json
      python3 evals/run_evals.py            # behavioral gate cases (includes the doc-count lint)
      python3 evals/run_memory_evals.py
      python3 evals/run_reality_evals.py
      python3 evals/run_routing_evals.py
      python3 evals/run_hook_evals.py
      python3 evals/run_control_evals.py    # control-plane add-on suite (in-repo checkout)
      ```

      The six core gate suites total **247 offline gate cases** (20 static + 61 behavioral +
      32 memory + 50 reality + 30 routing + 54 hook). The opt-in control plane adds
      **36 add-on cases** (`run_control_evals.py`), counted separately because the
      add-on is not installed by default. The canonical numbers are DERIVED at
      runtime from the suites (`canonical_gate_cases()` / `control_addon_cases()` in
      `evals/run_evals.py`) — nothing to bump when a count changes; a lint fails if
      any public doc — this one included — states a wrong total, breakdown addend,
      or sum.

- [ ] If your change touches `bench/`, follow the pre-registered protocol in
      [`bench/PROTOCOL.md`](bench/PROTOCOL.md) — decision rules are committed before
      data, and `python3 bench/runner.py --validate` must pass on any results file.

- [ ] The GitHub Actions [`evals.yml`](.github/workflows/evals.yml) run is green.
- [ ] If your change touches docs, you regenerated any affected images or diagrams and
      the alt text is descriptive.

## What we accept eagerly

- **New eval cases** that pin behavior. If you can express a rule as a failing test, we
  probably want it.
- **New host integrations** that follow the existing pattern (files under `examples/<host>/`
  plus a matching `hosts/<host>/`).
- **Portability fixes.** Any regression that makes the loop harder to drop into a new
  host is a bug.
- **Documentation clarity.** If a section confused you, a PR that fixes the wording is
  welcome.
- **Real bugs found in the wild.** Attach a minimal repro record if you can.

## What we push back on

- **New runtime dependencies.** The helper stays stdlib-only. If you need something
  fancy, it belongs in an optional adapter that degrades gracefully when the dep is missing.
- **Advisory rules without an eval.** If it is not checkable, it drifts. Prefer a gate
  and an eval over a paragraph.
- **Feature creep into "we score the model" territory.** The loop checks the *shape* of
  evidence. It is not a benchmark harness (that is what `bench/` is for) and it is not
  a hosted service.
- **Refactors without a task contract.** Not because the rule is silly, but because
  bigger, unmotivated refactors are how portable projects die.

## Local development

The helper is stdlib-only, so setup is:

```bash
git clone https://github.com/zaingz/coding-quality-loop.git
cd coding-quality-loop
python3 --version   # 3.10+ required for the helper
```

That is it. There is no `pip install`, no lockfile, no venv, no build step.

For host-specific work, see `hosts/<host>/README.md` where present, or the example
folder for your host under `examples/`.

Running `python3 scripts/install.py --host all` inside this source repo is useful for
local hook testing, but most generated host copies are intentionally ignored here. Commit
the source templates under `hosts/`, `examples/`, `scripts/`, and `.claude/agents/`
instead.

**The deterministic layer is live in this repo.** Since v6.1.0, `.claude/settings.json`
is committed: the SessionStart brief, PreToolUse guard, and Stop gate fire during CQL's
own development, so a release can no longer ship a broken hook path unfelt. One honest
carve-out: the repo's `quality-loop.config.json` sets `protect_harness: false`, because
here the gate scripts are the workpiece — the guard's harness-file edit denies would
make developing CQL impossible. The always-on destructive-command layer still applies,
and consumer installs keep the default (on). If a hook misfires while you work, fix the
hook — do not delete the settings file to get unstuck.

## Reviewer independence

The repo enforces its own rules. When you open a PR, an independent reviewer — not you —
approves before merge. If you are also the maintainer, ask a second maintainer or a
trusted contributor to review. This is inconvenient sometimes; it is also the point.

## Style

- Prose in Markdown. Sentence case for headings; no ALL CAPS titles unless we already
  have them.
- Code in Python 3.10+, stdlib only, four-space indentation.
- No trailing whitespace; final newline; ASCII quotes.
- Keep filenames lowercase-with-dashes for docs, lowercase-with-underscores for Python.

## Filing issues

Please include:

- What you tried (the exact command or the exact prompt).
- What you expected.
- What happened (paste the output; do not paraphrase).
- Which host and version (the output of `python3 scripts/quality_loop.py brief` helps).

Bugs that fit on one screen get looked at fastest.

## License

By contributing you agree your work is licensed under the MIT license, same as the rest
of the repo.

## Code of conduct

Be kind, be direct, assume good faith. Do not attack contributors. If a discussion is
going sideways, step away and come back.

## Thanks

The best thing you can do for this project, short of shipping a PR, is to use it on a
real task and tell us where the docs lied, the gates missed something, or the ceremony
felt wrong. Open an issue.
