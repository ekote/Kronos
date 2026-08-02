# Seller guide — Kronos on Azure & Microsoft Fabric

*A field companion to `solution-deck.pdf` for Microsoft sellers / CSAs / partners
positioning this solution with customers. Use the deck to present; use this to
qualify, handle objections, and land consumption.*

> **What this is:** a **reference architecture and accelerator** that runs the
> open-source **Kronos** forecasting model as a real-time decision loop on
> **Azure ML + Microsoft Fabric Real-Time Intelligence**. It is **not** a
> Microsoft product, and it is **not** trading/financial advice. Position it as a
> repeatable *pattern* that drives Fabric + Azure consumption — not a supported SKU.

---

## The one-line pitch

**"Turn a live data feed into forecasts you can act on — in seconds — with a
built-in alarm for when the model stops being right."**

Lead with the **decision loop + guardrail**, not "we predict the market." The
guardrail (auto-detecting when forecasts diverge from reality) is the credible,
differentiated hook. Prediction accuracy is the demo; **trustworthy real-time
operations** is the sale.

---

## Who to sell to (ideal customer profile)

Any customer with **high-volume, time-stamped data and a need to act on it now** —
this pattern generalizes well beyond finance.

| Strong fit | The signal that opens the door |
|---|---|
| Capital markets, trading desks, hedge funds, exchanges | "We forecast/monitor prices but our pipeline is batch/overnight." |
| Fintech, crypto, payments | "We need real-time signals and anomaly alerts at scale." |
| Energy & commodities trading | "We model price/load in real time and react to shocks." |
| **Adjacent (same pattern, different data):** IoT, telco, logistics, fraud, ops | "We have streams and a model, but no managed real-time loop." |

**Disqualifiers / slow down:** customers who want a *guaranteed profitable trading
strategy* (walk away — that's not this), or who need a regulated,
advice-generating system without their own compliance/risk ownership.

---

## The value, in the customer's words

1. **From overnight to real-time.** Batch forecasting → a streaming loop that
   scores on every new candle/event.
2. **Act, don't just chart.** Forecasts become **alerts and triggers**
   (Data Activator) — routed to Teams, a webhook, or a risk system.
3. **A safety net for AI in production.** The model-health guardrail flags regime
   change automatically (~minutes), so nobody trades on a stale model. *This is the
   line that lands with risk/ops buyers.*

---

## What lights up in Azure & Fabric (the consumption story)

This is the part that matters for your number. One solution, **multiple meters**:

| Component | Service | Consumption driver |
|---|---|---|
| Ingestion | **Azure Event Hubs** | throughput units / events per second |
| Real-time store, candles, dashboards, alerts | **Microsoft Fabric** (Eventhouse, Eventstream, Real-Time Dashboard, Data Activator) | **Fabric capacity (CUs)** — scales with symbols, query volume, users |
| Model serving | **Azure ML managed online endpoint (GPU)** | GPU instance hours (T4 → A100) |
| Training / fine-tuning | **Azure ML GPU clusters** | training job hours |
| Data lake | **OneLake / storage** | stored + processed data |
| Security/ops | **Entra ID, Key Vault, Azure Monitor** | platform pull-through |

**Talk track:** it's a **Fabric-anchored** win with an **Azure ML attach** — the
customer grows Fabric CUs as they add symbols and users, and adds GPU spend as they
move from the baseline to the real Kronos model and to fine-tuning on their own data.
Great for **Fabric adoption + MACC/ACR** motions.

---

## Discovery questions

- How fresh are your forecasts today — real-time, or batch/overnight?
- When a model goes stale or the market regime shifts, **how do you find out**, and
  how fast?
- Where do your market/stream events land now, and how do you act on them?
- Are you on Fabric yet? Where are you in your Fabric adoption?
- Do you fine-tune models on your own data? On what infrastructure?
- Who owns risk/compliance sign-off for model-driven decisions?

---

## Objection handling

| Objection | Response |
|---|---|
| *"Can it beat the market / guarantee returns?"* | No — and anyone who promises that is lying. It's a real-time forecasting **and monitoring** platform; the differentiator is knowing when the model is wrong. Alpha is the customer's strategy, not the tool. |
| *"We already have models."* | Great — bring your own. The value is the **managed real-time loop + guardrail**, not the model. Kronos is swappable; the Fabric/Azure ML plumbing is the asset. |
| *"Why not just build it ourselves?"* | You can — this *is* the blueprint. Fabric RTI removes the streaming/candle/dashboard/alert plumbing; Azure ML removes the serving/scaling/MLOps. Weeks, not quarters. |
| *"Why Fabric and not [other cloud]?"* | One governed platform (OneLake) from ingest to dashboard to action, with Data Activator turning analytics into automation — no glue code between five services. |
| *"Is this supported by Microsoft?"* | It's a reference accelerator using an open-source model. The **underlying services are fully supported**; the pattern is yours to own or have a partner implement. |

---

## Demo & assets to use

- **`solution-deck.pdf`** — the 9-slide story (open with this).
- **Live/HTML demo** — the end-to-end run: forecasts, the shock, the ~17-minute
  auto-detection. Concrete proof the loop works.
- **`deploy_to_fabric.py`** — one command provisions an Eventhouse and replays the
  whole thing into the customer's Fabric tenant. Powerful for a hands-on POC.
- **KQL round-trip** — shows it's genuinely Fabric-native, not a slideware demo.
- **`solution-deck-eli5.md`** — the no-jargon version for non-technical stakeholders.

**Suggested flow:** deck → live demo → "let's stand it up in *your* Fabric" (deploy
script POC) → scope a fine-tune on their data (Azure ML attach).

---

## Landmines — don't do this

- ❌ Don't promise trading profits or "alpha." Frame as tooling + safety, not advice.
- ❌ Don't present it as a Microsoft product or imply product-level support.
- ❌ Don't skip the customer's **risk/compliance** owner — model-driven financial
  decisions are regulated; keep a human/risk gate in the story.
- ❌ Don't quote the demo's numbers as live-market performance — they're from a
  fixed-seed synthetic session, illustrative only.

---

## Next steps / call to action

1. **Qualify** with the discovery questions (real-time gap? Fabric adoption? own data?).
2. **Show** the deck + live demo.
3. **Prove** with a Fabric POC via the deploy script in their tenant.
4. **Expand** into a fine-tune on their data (Azure ML GPU) and more symbols/users
   (Fabric CU growth).
5. **Bring a partner** for production hardening (networking, MLOps, compliance).

---

**Learn more:** official docs for every part of this — Kronos ([GitHub](https://github.com/shiyu-coder/Kronos), [paper](https://arxiv.org/abs/2508.02739), [models](https://huggingface.co/NeoQuasar)) and each Azure & Fabric service ([Microsoft Learn](https://learn.microsoft.com/fabric/real-time-intelligence/overview)) — are collected in [`../references.md`](../references.md).
