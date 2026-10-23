# Coding Quality Loop (Pi)

This recipe is source-checked against [Pi 1.4.0 at `ede2c9b`](https://github.com/earendil-works/pi/tree/ede2c9b468d8e061c557d16957513715e6d49cd6). The project [moved from `badlogic/pi-mono` to `earendil-works/pi`](https://pi.dev/changelog/2026/5/7/pi-has-a-new-home). No live Pi session or model call was used to validate this recipe.

> **Advisory rules only, no runtime — outside the routed loop.** The first-class loop
> routes **Claude Code (implementer) + Codex (independent reviewer)**. Pi loads the
> skill text and `setup-models --host pi` still prints per-role `/model` commands, but
> none of the hook runtime (PreToolUse guard, Stop gate, SessionStart brief) runs in
> Pi, and the npm installer no longer offers Pi as an install target. Gates fire only
> if you run `python3 scripts/quality_loop.py …` yourself.

Pi loads skills as directories containing `SKILL.md` plus optional scripts/references/assets,
with progressive disclosure (metadata first, full instructions when relevant). Pi discovers
skills from `~/.pi/agent/skills/`, `~/.agents/skills/`, `.pi/skills/`, `.agents/skills/`, and
any directories listed under `skills` in settings. Each skill registers as `/skill:name`.
See https://pi.dev/docs/latest/skills

## Install

```bash
# Project-local: place the skill where Pi looks for it
mkdir -p .agents/skills
cp -r /path/to/coding-quality-loop .agents/skills/coding-quality-loop
# (this folder's .pi/settings.json already lists .agents/skills and .pi/skills)
```

For a user-level install, copy the skill into `~/.pi/agent/skills/coding-quality-loop` or
`~/.agents/skills/coding-quality-loop` instead.

## One-line usage

```text
/skill:coding-quality-loop implement the requested change with a validation contract and an independent review
```

Pi can also invoke the skill implicitly when a request matches its description. The bundled
`.pi/settings.json` shows the minimal `skills` configuration.

## Role wiring (right model per use case)

Pi lets you set a provider and model per role. Map each Quality Loop role to the model class
that fits it, following `assets/quality-loop.config.example.json`:

| Role | Model class | Pi config |
|---|---|---|
| context mapper (EXPLORE) | cheap/fast | `/model <cheap-fast-model>` before mapping |
| planner (MINIMALITY_GATE + PLAN) | strong reasoning | `/model <strong-reasoning-model>` for planning |
| implementer (IMPLEMENT_SLICE) | code-specialized | the main session model |
| reviewer (REVIEW) | strong reasoning, separate session | start a new Pi session or use a different provider for review |

To generate the `/model` commands and thinking levels for each role from your
config, fill the `model_routing` section in `quality-loop.config.json` and run:

```bash
python3 /path/to/coding-quality-loop/scripts/quality_loop.py setup-models --host pi
```

This prints the `/model` commands to run per role (no files written). Reviewers
still need a fresh Pi session so they do not inherit the implementer's context.

The implementer stays the main thread (single-threaded writes). The reviewer runs in a fresh
session so it does not inherit the implementer's confidence. This matches Cognition's 2026
finding: multi-agent works when writes stay single-threaded and other agents contribute
intelligence (https://cognition.com/blog/multi-agents-working).

For mission-class multi-day work with parallel workers, Pi's provider routing and session
management can carry the coordination cost without a custom runtime — but the routed v5 kernel
(Claude Code + Codex) is where enforced review independence lives.

## Resume with a read-only CQL brief

From the target project root, use a complete CQL source checkout (or an install
that includes its Python runtime) to inspect the persisted record before
continuing the Pi session. Copying only the skill instructions does not install
this CLI. Replace `/path/to/coding-quality-loop` with the checkout path:

```bash
python3 /path/to/coding-quality-loop/scripts/quality_loop.py brief --cwd "$PWD" --json
pi --continue                 # latest Pi session for this working directory
# or: pi --session <path-or-id>  # use a full path or exact ID to select the intended session
```

The brief reads `status`, `next_action`, open risks, escalation reason, and the progress note.
Its `recovery` field compares raw source, index, record and allowlist bytes with a *local* passing
`verify`; older markers without a bound record path and source snapshot report `unknown` until
verification is deliberately rerun. Matching bytes do not prove checks would still pass in the
current environment. Local records and markers are forgeable; a configured Git
clean/process filter makes passive review freshness `unknown`. The brief does not
inspect external effects or run any recorded command. A changed diff invalidates
old review and verification evidence. Inspect an interrupted external effect's
actual outcome before retrying it. Run `verify` deliberately after reconciliation; it
re-executes allowlisted commands. Pi's [`--continue` and `--session` options](https://github.com/earendil-works/pi/blob/ede2c9b468d8e061c557d16957513715e6d49cd6/packages/coding-agent/docs/cli.md#L79-L90) restore conversation history, not CQL verification.

If an optional extension reads the brief, handle all `session_start` reasons: `startup`,
`reload`, `new`, `resume`, and `fork`. A fresh process reopening history starts as `startup`;
`resume` can mean an in-process switch. Use [`getBranch()`](https://github.com/earendil-works/pi/blob/ede2c9b468d8e061c557d16957513715e6d49cd6/packages/coding-agent/docs/extensions.md#L346-L350) for the active branch; `getEntries()` includes abandoned branches. `session_start` can notify but cannot return prompt context. A concise `before_agent_start` message enters the next agent run; [`sendUserMessage()` starts a turn](https://github.com/earendil-works/pi/blob/ede2c9b468d8e061c557d16957513715e6d49cd6/packages/coding-agent/src/core/extensions/types.ts#L1740-L1749), so it is not passive recovery. Treat [`agent_settled`](https://github.com/earendil-works/pi/blob/ede2c9b468d8e061c557d16957513715e6d49cd6/packages/coding-agent/docs/extensions.md#L145-L167), not `agent_end`, as the no-more-automatic-continuation notification.

[Pi Durable](https://earendil.com/posts/pi-durable/) is a separate experimental framework,
not a Pi CLI plugin. Its [`structuredOutput` is not saved in model-issued transcript results](https://github.com/earendil-works/pi/blob/ede2c9b468d8e061c557d16957513715e6d49cd6/packages/durable/README.md#L275-L281); an application must persist needed evidence explicitly. Durable checkpoints still do not make an external effect safe to repeat without reconciliation or idempotency.
