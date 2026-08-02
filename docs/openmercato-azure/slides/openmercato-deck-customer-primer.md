# You've heard of Open Mercato and Kronos. Here's what they do together.

*A short, no-pressure primer that goes with `openmercato-deck.pdf`. For someone
who knows the two names and wants to understand the solution — what it is, whether
it's for you, and what the catch is.*

---

## First, the two names — placed correctly

**Open Mercato** is an open-source, **event-driven commerce/ERP framework** (CRM,
Sales, OMS, ERP modules). Every order, sale, and inventory change it processes is
published as a **domain event** — a live stream of what's happening in your store.

**Kronos** is an open-source **AI time-series forecasting model**. It reads a
recent series and forecasts the next stretch. It was trained on financial price
candlesticks — which matters (see the catch below).
*(Note: the open-source markets model, not the workforce/HR product of the same
name.)*

**The solution** connects them: Open Mercato's order events flow to **Azure**,
get aggregated into **per-minute "sales bars"** (like candlesticks, but for GMV),
Kronos **forecasts demand**, and the system **shows it and raises alerts** — in
seconds, continuously.

---

## What you get when they work together

A **real-time demand loop**: orders come in → they become sales bars → Kronos
forecasts the next stretch of GMV → a dashboard shows it and can **trigger an
action** (including back into Open Mercato — e.g. a restock workflow).

Three outcomes worth caring about:

1. **Real-time instead of end-of-day.** Demand forecasts update on every minute of
   orders, not in a nightly report.
2. **It acts, not just charts.** A forecast can pre-warn ops to scale, pre-stock a
   SKU, or flag an anomaly — automatically.
3. **It watches itself.** When forecasts stop matching reality — a flash sale, a
   stockout, a **checkout outage**, a fraud wave — the system **detects it
   automatically**, usually within minutes.

That third one is the real point. Any forecast can be wrong; **a system that tells
you the moment it's wrong** is what makes it safe to run.

---

## A day in the life (what the deck shows)

One simulated store-day for a tenant:

- **Calm trading** — Kronos forecasts GMV/minute; ~**70%** directional accuracy
  over a 30-minute horizon, ~**2.8%** median error. Momentum **signals** fire.
- **Flash sale** — demand surges; the signals light up so ops can prepare.
- **Checkout outage** — orders collapse ~85%. *No model predicts that* — but the
  **guardrail auto-detects it in ~5 minutes**.

*(Numbers are from a fixed, synthetic demo day — they show the loop works, not a
promise about your store.)*

---

## Is this for you?

Likely **yes** if you recognize any of these:

- "Our demand/ops forecasting is batch or end-of-day, and we wish it were live."
- "When demand shifts or something breaks (stockout, outage), we find out too late."
- "We already emit order/inventory events and want to *act* on them in real time."
- "We run (or are curious about) Open Mercato and want a high-value use case."

The same loop also fits non-commerce streams (IoT, logistics, energy) with a
different model. Probably **not** what you want if you expect a guaranteed
sales-prediction oracle — that's not this (see below).

---

## What it is — and isn't (the honest part)

- ✅ It **is** a **reference architecture and working demo** you can stand up and
  build on. The Azure/Fabric services underneath are fully supported.
- ⚠️ Kronos was pre-trained on **financial** data, so on your commerce data it
  works best after **fine-tuning on your own sales bars**. Zero-shot is a starting
  point, not the finished accuracy.
- ❌ It **isn't** an off-the-shelf Microsoft or Open Mercato product — it's a
  blueprint you (or a partner) tailor.
- ❌ It makes **no promise of perfect demand prediction**. The durable value is the
  **real-time loop + automatic guardrail**, not a crystal ball.

---

## Trying it — the small first step

1. **Watch the demo** (deck, or run it) — the whole loop end-to-end.
2. **Stand it up in your own Azure** — one script replays it into **Microsoft
   Fabric or Azure Data Explorer** (your choice), with your own tools.
3. **Point it at your data** — connect the Open Mercato **event bridge** and
   fine-tune Kronos on your history when ready.

Step 2 is a low-risk afternoon, not a program.

---

## Where to go next

- **`openmercato-deck.pdf`** — the 8-slide visual story (start here).
- **[`../architecture.md`](../architecture.md)** — how it's built, both the Fabric
  and Azure-only options, for your engineers.
- **`openmercato-deck-eli5.md`** — an even simpler version to share widely.

Bring your engineers for the architecture; loop in ops and (if orders carry PII)
your data-protection owner early.

---

**Learn more:** [Open Mercato](https://github.com/open-mercato/open-mercato),
[Kronos](https://github.com/shiyu-coder/Kronos) ·
[models](https://huggingface.co/NeoQuasar), and each Azure & Fabric service
([Microsoft Learn](https://learn.microsoft.com/fabric/real-time-intelligence/overview)) —
collected in [`../../azure/references.md`](../../azure/references.md).
