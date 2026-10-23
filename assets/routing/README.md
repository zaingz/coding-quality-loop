# Routing variants

Three pinned `model_routing` blocks for Claude Code (plan + implement) and Codex (cross-family review). Pick one, paste it over the `model_routing` section of your `quality-loop.config.json`, then:

```bash
python3 scripts/quality_loop.py setup-models   # applies file hosts, prints codex
python3 scripts/quality_loop.py check-config quality-loop.config.json
```

| Variant | Plan / orchestrate | Implementer | Independent reviewer |
|---|---|---|---|
| `max-intelligence.json` | Claude Fable 5 | Claude Fable 5 | GPT-5.6 Sol (Codex) |
| `balanced.json` | Claude Opus 4.8 | Claude Sonnet 5 | GPT-5.6 Sol (Codex) |
| `max-throughput.json` | Claude Sonnet 5 | Claude Sonnet 5 | GPT-5.6 Terra (Codex) |

`check-config` requires a different reviewer and implementer model family when both resolve (unless `allow_same_family` is true), rejects reasoning effort above `high` without `allow_overthink`, and requires PLAN to use `strong_reasoning`. Routing evals check that the shipped variants pass `check-config`, disable same-family review, and set effort no higher than `high`. These checks do not establish model capability or account access.

Each variant carries an `"as_of": "YYYY-MM-DD"` field naming when its model choices were last reviewed; once your pasted `model_routing` block's `as_of` is more than 90 days old, `brief` prints a one-line "model menu may be stale" warning.

## Check models and cost before use

These presets were last reviewed on 2026-07-12. As of 2026-10-23, newer models are listed by both providers. The pinned IDs are examples, not a guarantee of access or the best choice for your account. Check [Claude Code model availability](https://code.claude.com/docs/en/model-config) and [Codex models](https://developers.openai.com/codex/models), then update the IDs in your chosen variant if needed.

Check [Anthropic API prices](https://platform.claude.com/docs/en/about-claude/pricing) and [Claude Code billing](https://code.claude.com/docs/en/costs), or [OpenAI API prices](https://developers.openai.com/api/docs/pricing) and [Codex billing](https://developers.openai.com/codex/pricing), for your actual payment method. API token prices do not describe included subscription usage. Compare measured cost or usage per accepted change for your own workload.

Preset escalation path on a recorded failing check: Sonnet 5 → Opus 4.8 → Fable 5 (implement/plan); Terra → Sol (review). Record the escalation and the failing command in the agent record.
