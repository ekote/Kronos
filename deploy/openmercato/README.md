# Open Mercato × Kronos × Azure — runnable demo

Zero-dependency demo of the commerce loop: a synthetic **[Open Mercato](https://github.com/open-mercato/open-mercato)**
order stream → **sales bars** → **Kronos** demand forecast → **model-health
guardrail**, emitting KQL that replays into a **Fabric Eventhouse OR Azure Data
Explorer** (same script).

```bash
python deploy/openmercato/run_openmercato_demo.py     # writes output/ (JSON + kql/)
```

No `pip install` — standard library only. It reuses the markets demo's
`pipeline.py`, `forecaster.py`, and `kql_emit.py` unchanged; only the data source
(`marketplace.py`) is new.

## The story it runs

One store-day for tenant `store_hydra`:

1. **Calm trading** — Kronos forecasts GMV/minute; ~**70%** 30-min directional
   accuracy, ~**2.8%** median error. Momentum **signals** fire (most correct).
2. **Flash sale** — a demand surge → the signals light up (opportunity).
3. **Checkout outage** — orders collapse ~85%. No model predicts it, but the
   **model-health guardrail auto-detects it within ~5 minutes** — the operational
   payoff.

*(Numbers are from fixed-seed synthetic data — illustrative of the loop, not a
live-store performance claim.)*

## How each stage maps

| Demo module | Plays the role of | Fabric option | Azure-only option |
|---|---|---|---|
| `marketplace.generate_orders` | Open Mercato event source | (via bridge) → Event Hubs | (via bridge) → Event Hubs |
| `marketplace.aggregate_bars` | sales-bar builder | Eventhouse `gmv_1m` MV | ADX `gmv_1m` MV |
| `forecaster.KronosAdapter` | model plane | Azure ML endpoint | Azure ML endpoint |
| `pipeline.run_pipeline` | orchestrator | Fabric notebook | Azure Function |
| `pipeline.detect_signals` / `detect_drift` | action plane | Data Activator | Functions + Monitor |
| `kql_emit_om.write_kql_bundle` | round-trip | Fabric Eventhouse | Azure Data Explorer |

## Files

```
marketplace.py            Open Mercato order stream -> per-minute GMV sales bars
run_openmercato_demo.py   narrated end-to-end runner (+ KQL bundle)
kql_emit_om.py            orders_raw + gmv_1m view; reuses generic forecasts/signals/alerts KQL
bridge/                   Open Mercato event subscriber -> Azure Event Hubs (Node + Python)
```

## Real Kronos + real Open Mercato

- **Real Kronos:** `KRONOS_ENABLE=1` (with torch + weights) swaps the baseline for
  the real model — same interface. For accuracy on commerce data, **fine-tune**
  Kronos on the merchant's own `gmv_1m` bars (repo `finetune/`).
- **Real Open Mercato:** replace the synthetic stream with the event **bridge**
  (`bridge/`) that subscribes to Open Mercato domain events and forwards them to
  Event Hubs. Everything downstream is identical.

See the design in [`../../docs/openmercato-azure/`](../../docs/openmercato-azure/).
