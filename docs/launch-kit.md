# Launch kit

Short-form assets for sharing the Coding Quality Loop on Hacker News, Reddit, X, and
LinkedIn. Nothing here is exclusive — copy, edit, ship.

Use the [hero art](images/art/hero-art.png), [evidence dashboard](images/evidence-dashboard.png), or
[gate-gaming panel](images/gate-gaming.png) image as the visual.

---

## Hacker News

**Title (≤ 80 chars):**

> Show HN: Coding Quality Loop – executable gates for AI coding agents

**Body:**

> I got tired of AI coding agents shipping "looks right to me" diffs that touched five
> unrelated files, added a dependency I didn't want, and self-attested that the tests
> passed. So I packaged the process I actually want them to follow — smallest correct
> change, evidence over confidence, an independent reviewer that isn't the implementer —
> as a portable Agent Skill with executable gates.
>
> - Drops into Claude Code, Codex, and Droid via copy-to-folder (advisory rules for Cursor and Pi).
> - Zero runtime dependencies; the gate CLI is a handful of stdlib-only Python modules you can read.
> - 251 offline gate cases across 6 core suites pin the gates so they don't drift (plus 37 add-on cases for the opt-in control plane).
> - Reality layer reads the actual `git diff` and catches phantom completions, stale
>   review hashes, missing bugfix tests, and self-downgraded risk tiers.
> - Optional project memory (files backend) so the agent stops relearning the
>   same lesson every session.
>
> The README has a quickstart demo and a comparison to superpowers, addyosmani/agent-skills,
> and ponytail. Feedback and PRs welcome.
>
> https://github.com/zaingz/coding-quality-loop

---

## Reddit — r/LocalLLaMA / r/ChatGPTCoding / r/MachineLearning

**Title:**

> I built an Agent Skill that makes coding agents ship smaller, verified diffs — with executable gates, not just prompts

**Body:**

> Same agent, same model. The difference is the process wrapped around it.
>
> The **Coding Quality Loop** is a portable Agent Skill that turns "fix this bug" into a
> repeatable workflow: task contract → context map → smallest-safe rung → plan →
> implement → verify → *independent* review → ship, with the non-negotiables enforced
> by a stdlib-only Python CLI you can read.
>
> What that gets you in practice:
>
> - **Small diffs.** Complexity brake runs twice: before planning and before review.
> - **Real proof, not "looks right to me".** Every acceptance criterion is paired with a
>   check; the reality layer diff-audits the actual `git diff` against the record.
> - **Reviewer ≠ implementer.** Freshness is checked; the diff hash is embedded.
> - **Portable.** Drops into Claude Code, Codex, and Droid via copy-to-folder; advisory rules for Cursor and Pi.
> - **Optional cross-session memory.** Distilled lessons, budget-capped recall, secret
>   redaction at write.
>
> Repo, README, and eval suite: https://github.com/zaingz/coding-quality-loop
>
> Not a benchmark, not a hosted service — just files, git, and Python. Honest about
> what it doesn't do (see the README's "what it enforces and what it does not" table).

---

## X / Twitter thread (7 tweets)

**1/**
Same agent, same model. The difference is the process wrapped around it.
Coding Quality Loop is a portable Agent Skill that makes your AI agent ship changes you
can trust — not giant diffs you have to babysit.

**2/**
The problem: one model owning intake, code, *and* self-review is the dominant failure mode.
It overbuilds, self-attests, loses context, skips evidence, and repeats mistakes.

**3/**
The fix isn't a smarter model. It's a process artifact:
– task contract before code
– smallest safe rung
– verification evidence, recorded
– independent reviewer, fresh context
– durable lessons across sessions

**4/**
And executable gates, not advisory text. A stdlib-only Python CLI reads the state record,
the `git diff`, and the recorded evidence — and refuses to let a task self-downgrade
around auth, payments, migrations, or PII.

**5/**
Drops into Claude Code, Codex, and Droid via copy-to-folder. Zero runtime
dependencies. 251 offline gate cases across 6 core suites, re-run on every push.

**6/**
Optional project memory: distilled lessons, budget-capped recall, secrets redacted at
write. Files backend, stdlib-only.

**7/**
Repo: https://github.com/zaingz/coding-quality-loop
README has a quickstart demo, a comparison to superpowers / addyosmani/agent-skills /
ponytail, and an honest table of what it enforces and what it doesn't.

---

## LinkedIn

**One-paragraph version:**

> I've been shipping the same lesson to every coding agent I use: fix one thing, prove it,
> let a second agent check the diff. I packaged that as an open-source Agent Skill —
> stdlib-only, portable across Claude Code, Codex, and Droid — with
> executable gates that reject "looks right to me" instead of taking its word. 250
> offline gate cases keep the gates from drifting. The repo has a quickstart demo, an
> honest comparison to the other strong skills in this space, and an "enforced vs not
> enforced" table so you can decide before you install:
> https://github.com/zaingz/coding-quality-loop

---

## Product Hunt

**Tagline (≤ 60 chars):**

> Executable gates for your AI coding agent

**Description (≤ 260 chars):**

> Coding Quality Loop is a portable Agent Skill that makes AI coding agents ship the
> smallest correct change with verifiable evidence and an independent review — instead
> of huge, self-attested diffs. Zero runtime deps. Works in Claude Code, Codex, and Droid.

**First comment (maker note):**

> Hi everyone — I'm the author. I built this because my coding agents kept shipping
> sprawling diffs and grading their own work. The loop is one Markdown skill plus a
> stdlib-only Python gate CLI you can read. It's not a benchmark and
> it's not a hosted service; it's the process I wanted my agent to follow, packaged so
> it works the same in Claude Code, Codex, and Droid. Honest feedback in
> the comments would be more useful than upvotes.

---

## Elevator description (for talks, podcasts, README of another project)

> Coding Quality Loop is a portable Agent Skill that turns "please fix this bug" into a
> repeatable workflow: task contract, smallest-safe rung, evidence, independent review,
> and a durable lesson at the end. The non-negotiables are enforced by a stdlib-only
> Python CLI so they don't drift the way prompts do. Drops into Claude Code, Codex,
> and Droid via copy-to-folder. Zero runtime dependencies.

---

## Things to check before posting

- The eval badge in the README shows the current pass count.
- The star history and version badges are up to date.
- The quickstart demo in the README still runs on a clean checkout.
- The "how it compares" section links to the current release of each alternative.

If you catch drift between the docs and the code, the [`docs/`](.) index tells you what
was changed when.
