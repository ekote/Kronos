# You've heard of Fabric and Kronos. Here's what they do together.

*A short, no-pressure primer that goes with `solution-deck.pdf`. For someone who
knows the two names and wants to understand the solution — what it is, whether
it's for you, and what the catch is.*

---

## First, the two names — placed correctly

**Microsoft Fabric** is Microsoft's all-in-one data platform. The part this
solution uses is **Real-Time Intelligence (RTI)** — the piece built for data that
*keeps arriving* (market ticks, sensor readings, events) and needs to be stored,
watched, and acted on *right now*, not in tomorrow's report.

**Kronos** here is a **forecasting AI model for financial markets** — an
open-source "foundation model" trained on price candlesticks (open/high/low/close)
from 45+ exchanges. Given recent price history, it forecasts what the next candles
might look like.
*(Note: this is the open-source markets model, not the workforce/HR product that
shares the name.)*

**The solution** is these two working as one system: Fabric RTI moves and watches
the live data; Kronos (served on **Azure Machine Learning**) does the forecasting;
Fabric turns the results into dashboards and automatic alerts.

---

## What you get when they work together

A **real-time loop**: live prices come in → Fabric shapes them into candles →
Kronos forecasts the next stretch → Fabric shows it and can **raise an alert** —
continuously, in seconds.

Three outcomes worth caring about:

1. **Real-time instead of overnight.** Forecasts update on every new candle, not in
   a nightly batch.
2. **It acts, not just charts.** A forecast can trigger an alert to a person, a
   Teams channel, or another system — automatically.
3. **It watches itself.** The standout feature: when the model's forecasts stop
   matching reality (a market shock, a regime change), the system **notices and
   flags it automatically** — usually within minutes.

That third one is the real point. Any model can be wrong; **a system that tells you
the moment it's wrong** is what makes this safe to run in production.

---

## A day in the life (what the deck shows)

The deck walks through one simulated trading day so you can see the loop working:

- **The calm morning** — prices trend, and Kronos forecasts direction correctly
  about two times in three. It sends "momentum" signals, most of which pan out.
- **The shock** — an unexpected news event drops the price sharply. *No model can
  predict that* — and the deck is honest that the forecast doesn't.
- **The guardrail** — within ~17 minutes, the system detects that forecasts have
  broken from reality and **fires an automatic alert**, before a human would notice.

*(Those numbers come from a fixed, made-up demo day — they show the machine works,
they are not a promise about live markets.)*

---

## Is this for you?

Likely **yes** if you recognize any of these:

- "Our forecasting or monitoring is batch/overnight, and we wish it were live."
- "When our models drift or the market shifts, we find out too late."
- "We have streams of time-stamped data and want to *act* on them, not just report."
- "We're adopting (or curious about) Fabric and want a concrete, high-value use case."

And the pattern isn't finance-only — the same loop fits **any high-volume,
time-stamped data** (IoT, energy, logistics, fraud), just with a different model.

Probably **not** what you want if you're looking for a guaranteed money-making
trading strategy — that's not what this is (see below).

---

## What it is — and isn't (the honest part)

- ✅ It **is** a **reference architecture and working demo** you can stand up and
  build on. The Azure and Fabric services underneath are fully supported products.
- ❌ It **isn't** a finished, off-the-shelf Microsoft product — it's a proven
  *blueprint* you (or a partner) tailor to your data and needs.
- ❌ It **isn't** financial or trading advice, and it makes **no promise of profit**.
  Forecasts are inputs for your own strategy and risk controls, with a human in the
  loop.
- 🔓 Kronos is **open-source** and **swappable** — you can fine-tune it on your own
  data, or bring a different model; the real-time plumbing stays the same.

---

## Trying it — the small first step

You don't have to commit to a big project to see it work:

1. **Watch the demo** (in the deck, or run the live one) — the whole loop end-to-end.
2. **Stand it up in your own Fabric** — a single script provisions the real-time
   database and replays the demo into your tenant, so you see it with Microsoft's
   own tools, on your side.
3. **Point it at your data** — fine-tune the model and add your real feeds when
   you're ready.

Step 2 is a low-risk afternoon, not a program.

---

## Where to go next

- **`solution-deck.pdf`** — the 9-slide visual story (start here).
- **The architecture doc** — how it's built, service by service, for your engineers.
- **`solution-deck-eli5.md`** — an even simpler, no-jargon version to share widely.

Bring your engineers for the architecture, and your risk/compliance people early —
anything that informs financial decisions should have their sign-off from day one.
