# Routing variants — the intelligence ↔ speed/cost knob

Three pre-validated `model_routing` blocks. Pick one, paste it over the
`model_routing` section of your `quality-loop.config.json`, then:

```bash
python3 scripts/quality_loop.py setup-models   # applies file hosts, prints codex/pi
python3 scripts/quality_loop.py check-config quality-loop.config.json
```

| Variant | Plan / review reasoning | Implementer | Independent reviewer | When |
|---|---|---|---|---|
| `max-intelligence.json` | Claude Fable 5 | Claude Fable 5 (Claude Code) | GPT-5.6 Sol (Codex) | Quality ceiling; routing only guards review independence |
| `balanced.json` | Claude Fable 5 | GLM-5.2 Fast (Droid) | GPT-5.6 Sol (Codex) | Default: frontier judgment, open-weight bulk execution |
| `max-throughput.json` | Claude Sonnet 5 | GLM-5.2 Fast (Droid) | GPT-5.6 Terra (Codex) | Cost-lean; floors still hold |

Every variant holds the floors the knob can never lower. Two are enforced by
`check-config` on any config: the reviewer resolves to a **different model
family** than the implementer (`allow_same_family` stays false), and reasoning
effort above `high` is rejected without `allow_overthink` (plus PLAN/ORCHESTRATE
must carry the `strong_reasoning` class). Two are held **by construction and
pinned by eval**, not judged by check-config: the strong-tier model choice for
the `strong_reasoning` class, and the security reviewer staying on it — no gate
grades which model counts as "strong" (that would need the model catalog this
repo deliberately doesn't ship).

These files are **documentation-grade data**: no gate reads the menu below,
so a stale price can never fail a build. The variants themselves are pinned
by eval (`evals/run_routing_evals.py` splices each into the example config
and requires `check-config` to pass).

## Model menu (as of 2026-07-11 — prices move, re-check before trusting)

List prices per million tokens (input/output), standard tier. Per-task costs
compress sticker gaps: cheaper models typically spend 2–4x the tokens per
accepted change, so **steer by cost per accepted completion record**
(`models_used[].cost_usd` over records with an approving review), never by
price per token.

| Model | $/MTok in/out | Coding standing | Access | Notes |
|---|---|---|---|---|
| Claude Fable 5 | 10 / 50 | SWE-bench Pro leader | Claude Code | Priciest; spend on plan/review, not bulk |
| Claude Opus 4.8 | 5 / 25 | Strong all-round | Claude Code | Natural escalation tier above Sonnet |
| Claude Sonnet 5 | 3 / 15 | Strong balance tier | Claude Code | Intro pricing ($2/$10) ends 2026-08-31 |
| Claude Haiku 4.5 | 1 / 5 | Explore/summarize tier | Claude Code | `cheap_fast` workhorse |
| GPT-5.6 Sol | 5 / 30 | Terminal-Bench leader | Codex CLI | METR (2026-06-26) flagged the highest detected eval-gaming rate of any public model it has evaluated: keep Sol reviews **advisory beneath deterministic gates** and verify findings locally |
| GPT-5.6 Terra | 2.50 / 15 | Near-Sol at half price | Codex CLI | Cost-lean reviewer tier |
| GPT-5.6 Luna | 1 / 6 | Classifier/explore tier | Codex CLI | |
| GLM-5.2 / Fast | 1.40/4.40 · 2.10/6.60 | Best open coding model | Droid (Factory), z.ai API, MIT weights | Supply-risk note below |
| Grok 4.5 | 2 / 6 | ~1pt behind frontier at ~1/5 the per-task cost | xAI API | Non-Chinese executor fallback |
| Muse Spark 1.1 | 1.25 / 4.25 | Competent, multimodal | Meta Model API (preview) | Non-Chinese executor fallback; preview pricing |

**GLM supply-risk note (2026-07):** Reuters reports Beijing is weighing
restrictions on overseas access to top Chinese models (regulators met
Alibaba/ByteDance/Z.ai), and Qwen's flagship already went closed. Released
MIT GLM-5.2 weights are irrevocable and re-hostable on US infrastructure,
so the risk applies to *future* versions — but name a non-Chinese fallback
for the executor leg (Grok 4.5 or Muse Spark 1.1 above) and avoid
Z.ai-exclusive features.

**Why the reviewer is always another family:** judges measurably favor their
own family's output, and a different id is not a different reviewer when
both ids alias the same model — `check-config` compares resolved families
(explicit `family` field, else a well-known-prefix match; unknown ids are
skipped, never failed).

**Escalation doctrine (not config):** when the cheap executor fails the same
verified check twice, escalate the implementer a tier (GLM → Opus → Fable)
and record it in the agent record's `escalations` array citing the failing
commands — `verify-gates` rejects escalations that cite no recorded failing
check. CQL never triggers escalation; the host does. Cost query when tuning:

```bash
# cost per model over ACCEPTED records, attributed per models_used entry
jq -s '[.[] | select(.status=="done" and (.independent_review.verdict|tostring|test("approve")))
        | .models_used[]?]
       | group_by(.model)
       | map({model: .[0].model, roles: (map(.role) | unique),
              entries: length, cost_usd: (map(.cost_usd // 0) | add)})' docs/records/*.json
```
