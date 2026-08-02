# Open Mercato × Kronos × Azure — real-time demand intelligence

A reference solution for turning a live **[Open Mercato](https://github.com/open-mercato/open-mercato)**
commerce stream (orders, sales, inventory events) into **real-time demand
forecasts you can act on**, using the **Kronos** time-series foundation model on
**Azure** — shown both with **Microsoft Fabric Real-Time Intelligence** and
**Azure-only** (Azure Data Explorer + Functions).

It's the commerce sibling of the markets solution in [`../azure/`](../azure/):
same real-time loop and model-health guardrail, different data source.

## Start here

- **[architecture.md](./architecture.md)** — the full design: the honest
  Kronos-fit note, Open Mercato events → OHLC "sales bars", the event bridge, and
  **both** the Fabric and Azure-only variants (they share the same KQL).
- **[slides/openmercato-deck.html](./slides/openmercato-deck.html)** /
  **[.pdf](./slides/openmercato-deck.pdf)** — the 8-slide deck (the gap, the
  architecture with both options, the value, and the live demo charts). Regenerate
  with `python deploy/openmercato/build_om_deck.py`.

## The idea in one picture

```
Open Mercato events ─▶ bridge ─▶ Event Hubs ─▶  [ Fabric Eventhouse  OR  Azure Data Explorer ]
 order.* / sales.*                                   orders_raw → gmv_1m (sales bars)
                                                              │  latest N bars
                                                              ▼
                                        orchestrator ──▶ Azure ML endpoint (Kronos)
                                                              │  forecast bars
                                                              ▼
                                                  forecasts + model-health alerts
                                                     │                    │
                                                     ▼                    ▼
                                             dashboard            act (Teams / webhook /
                                                                   back into Open Mercato)
```

## Reference implementation

- **[`../../deploy/openmercato/`](../../deploy/openmercato/)** — a runnable,
  zero-dependency demo: a synthetic Open Mercato order stream (flash-sale surge +
  checkout-outage shock) → sales bars → Kronos forecast → guardrail, emitting KQL
  that replays into **Fabric Eventhouse or Azure Data Explorer** (same scripts).
- **[`../../deploy/openmercato/bridge/`](../../deploy/openmercato/bridge/)** — the
  Open Mercato event subscriber → Event Hubs (Node + Python references).

## The honest fit

Kronos is pre-trained on **financial** candlesticks. Here it runs on **commerce
sales bars** (same OHLCV shape). Zero-shot is a working baseline; **fine-tune on
the merchant's own bars** for accuracy. The durable value is the **real-time loop
+ automatic model-health guardrail** (catch flash sales, stockouts, checkout
outages, fraud waves), not a promise of perfect demand prediction. Not a Microsoft
or Open Mercato product — a reference pattern on supported Azure services.
