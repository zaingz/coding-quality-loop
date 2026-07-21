# Routing variants — the intelligence ↔ cost knob

Three pre-validated `model_routing` blocks. **Anthropic + OpenAI only, two hosts: Claude Code (plan + implement) and Codex (cross-family review).** Pick one, paste it over the `model_routing` section of your `quality-loop.config.json`, then:

```bash
python3 scripts/quality_loop.py setup-models   # applies file hosts, prints codex
python3 scripts/quality_loop.py check-config quality-loop.config.json
```

| Variant | Plan / orchestrate | Implementer | Independent reviewer | When |
|---|---|---|---|---|
| `max-intelligence.json` | Claude Fable 5 | Claude Fable 5 | GPT-5.6 Sol (Codex) | Quality ceiling |
| `balanced.json` | Claude Opus 4.8 | Claude Sonnet 5 | GPT-5.6 Sol (Codex) | Default |
| `max-throughput.json` | Claude Sonnet 5 | Claude Sonnet 5 | GPT-5.6 Terra (Codex) | Cost-lean; floors still hold |

Floors the knob can never lower — two enforced by `check-config` on any config: the reviewer resolves to a **different model family** than the implementer (`allow_same_family` stays false), and reasoning effort above `high` is rejected without `allow_overthink` (plus PLAN must carry the `strong_reasoning` class). Two held by construction and pinned by eval (`evals/run_routing_evals.py`): the strong-tier model choice for `strong_reasoning`, and the security reviewer staying on it.

Each variant carries an `"as_of": "YYYY-MM-DD"` field naming when this menu was last reviewed; once your pasted `model_routing` block's `as_of` is more than 90 days old, `brief` prints a one-line "model menu may be stale" warning.

## Model menu (as of 2026-07-12 — prices move, re-check before trusting)

List prices per MTok in/out, standard tier. Cheaper models typically spend 2–4x the tokens per accepted change, so steer by **cost per accepted completion record** (`models_used[].cost_usd` over records with an approving review), never by price per token.

| Model | $/MTok in/out | Coding standing | Access | Notes |
|---|---|---|---|---|
| Claude Fable 5 | 10 / 50 | SWE-bench Pro leader | Claude Code | Priciest; spend on plan/review, not bulk |
| Claude Opus 4.8 | 5 / 25 | Strong all-round | Claude Code | Natural escalation tier above Sonnet |
| Claude Sonnet 5 | 3 / 15 | Strong balance tier | Claude Code | Intro pricing ($2/$10) ends 2026-08-31 |
| Claude Haiku 4.5 | 1 / 5 | Explore/summarize tier | Claude Code | `cheap_fast` workhorse |
| GPT-5.6 Sol | 5 / 30 | Terminal-Bench leader | Codex CLI | METR (2026-06-26) flagged the highest detected eval-gaming rate of any public model it has evaluated: keep Sol reviews **advisory beneath deterministic gates** and verify findings locally |
| GPT-5.6 Terra | 2.50 / 15 | Near-Sol at half price | Codex CLI | Cost-lean reviewer tier |

Escalation path on a recorded failing check: Sonnet 5 → Opus 4.8 → Fable 5 (implement/plan); Terra → Sol (review). Record the escalation and the failing command in the agent record.
