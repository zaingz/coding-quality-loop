# Coding Quality Loop (Pi)

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
