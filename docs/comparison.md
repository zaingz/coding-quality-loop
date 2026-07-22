# How the Coding Quality Loop compares

> Skills in this space make different bets. This page is our honest read of where the
> Coding Quality Loop sits relative to the strongest alternatives, so you can pick the
> right one for your team.

> **Read this before the table:** the summary below is our characterization. We linked
> each project below — read them yourself, run them, and disagree with us in an issue if
> we got it wrong. This is not a benchmark.

## The alternatives worth your time

| Project | Bet | Best when |
|---|---|---|
| [**Coding Quality Loop**](https://github.com/zaingz/coding-quality-loop) | Executable gates + candor. One dependency-free package where the non-negotiables are checked by a script you can read. | You want the same skill to drop into Claude Code, Codex, and Droid (advisory rules for Cursor and Pi), and you care that "tests pass" means someone can prove it. |
| [**superpowers**](https://github.com/obra/superpowers) | Subagent-driven TDD with a two-stage review flow. | You are all-in on Claude Code and want the deepest subagent choreography. |
| [**addyosmani/agent-skills**](https://github.com/addyosmani/agent-skills) | Broad, 24-skill SDLC suite covering the whole software lifecycle. | You want a **library** of skills (planning, testing, release, ops) rather than one focused loop. |
| [**ponytail**](https://github.com/DietrichGebert/ponytail) | A tight minimality ladder — "always take the smaller rung". | You want the simplest possible right-size gate and nothing else. |

**Where the alternatives win.** The feature table below is built around this project's chosen axes, so read it knowing the rubric is ours. On axes we did not pick: superpowers has deeper Claude-native subagent choreography and a far larger install base; addyosmani/agent-skills covers lifecycle breadth (planning, release, ops) this loop deliberately skips; ponytail is smaller and simpler than our right-size gate will ever be. If those axes are your axes, pick them.

## Feature comparison

| Feature | Coding Quality Loop | Superpowers | addyosmani/agent-skills | ponytail |
|---|:-:|:-:|:-:|:-:|
| **Executable gates** (rejects a claim when evidence is missing) | ✅ | ◐ | ◐ | ❌ |
| **Independent review** (implementer ≠ reviewer, checked) | ✅ | ✅ | ❌ | ❌ |
| **Multi-agent role separation** (context-mapper / implementer / validator / security) | ✅ | ✅ | ✅ | ◐ |
| **Right-size gate** (smallest-safe rung, rejected rungs recorded) | ✅ | ◐ | ◐ | ✅ |
| **Project memory** (distilled lessons across sessions) | ✅ | ❌ | ◐ | ❌ |
| **Diff-grounded reality layer** (record vs `git diff`) | ✅ | ❌ | ❌ | ❌ |
| **Zero runtime dependencies** (stdlib-only helper) | ✅ | ❌ | ◐ | ✅ |
| **Portable across hosts** (Claude Code, Codex, Droid, standalone; advisory rules for Cursor/Pi) | ✅ | Claude-first | Claude-first | Claude-first |
| **Offline eval suite** (proves the gates actually fire) | ✅ (251 gate cases across 6 core suites, plus 40 add-on cases for the opt-in control plane) | ◐ | ❌ | ❌ |
| **Public benchmark harness** with trap tasks | ✅ (`bench/`) | ❌ | ❌ | ❌ |

Legend: ✅ first-class · ◐ partial or advisory · ❌ not a goal

## What each project explicitly does not do

Being honest about non-goals matters more than a feature checklist:

**Coding Quality Loop does not**:

- Replace CI, tests, scanners, or human review. The gates check the *shape* of the
  evidence; the tools you already have prove the code works.
- Sandbox command execution. `run-evidence` re-executes commands from a repo-defined
  allowlist — same trust model as CI.
- Ship a hosted service. Everything is local files, git, and stdlib Python.
- Guarantee reviewer independence cryptographically. Identity is string-compared and
  fresh context is self-attested. `attest-review --against-diff` makes it *checkable*,
  not unforgeable.
- Enforce anything that would break the "drop into any host" promise. Host hooks stay
  advisory unless the host or repo opts into trusting them.

**superpowers does not**: chase host portability; its subagent flow is optimized for
Claude Code's native subagent primitives.

**addyosmani/agent-skills does not**: enforce independence between skills. Each skill is
individually excellent; combining them is left to the caller.

**ponytail does not**: try to cover intake, review, packaging, or memory. Minimality is
the whole product.

## Which one should you pick?

- **Want the loop for one task, one team, one host?** Any of these can work.
- **Want a portable skill that runs the same way in Claude Code, Codex, and Droid, and you want the gates to be checkable?** Coding Quality Loop.
- **Deep Claude Code shop that wants richer subagent choreography?** Superpowers.
- **Want a broad SDLC skill library rather than a single focused loop?** addyosmani/agent-skills.
- **Want just the minimality discipline and nothing else?** ponytail.

## Positioned against failure modes, not against skills

The Coding Quality Loop's real opponents are two failure modes, not the projects above:

1. **Instruction-only prompts that drift.** Advisory text degrades every model rev. Gates do not.
2. **Full autonomy that produces unreviewable diffs.** Bounded autonomy is the point: the
   boundary is what makes the output trustable.

If those two failure modes bite your team, the loop is worth trying. If you never see them
because your work is small and low-risk, a simpler tool will serve you better — pick
ponytail, or write a five-line prompt.

## Migrating in

If you already run superpowers, addyosmani/agent-skills, or ponytail, you can adopt this
loop **incrementally**:

1. Copy `SKILL.md` and `references/lifecycle.md` into your existing skill folder as a
   secondary skill.
2. Wire `python3 scripts/quality_loop.py diff-audit --staged` as a pre-commit hook. This
   is the smallest-value delta and requires no other change.
3. On the next medium/high-risk task, run `init-record` and `verify-gates`. Keep the
   other skill for tiny/small work.
4. Add reviewer-role wiring only when you have a specific bug the current review missed.

You do not need to replace anything. This loop composes with skills that focus on other
parts of the SDLC.
