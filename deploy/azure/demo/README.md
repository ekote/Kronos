# End-to-end demo — Kronos on Microsoft Fabric Real-Time Intelligence

A runnable, **zero-dependency** demo that plays the entire reference
architecture on a single synthetic trading session and renders the result as a
self-contained HTML report. It exists to answer one question concretely: *what
value does this pipeline bring?*

```bash
python deploy/azure/demo/run_demo.py            # writes output/kronos_fabric_demo.html
```

No `pip install` required — the demo runs on the Python standard library. Open
the generated HTML in any browser.

## What it shows (the story)

A synthetic **BTCUSDT** intraday session with genuine short-horizon momentum and
one scripted, *unpredictable* news shock. The pipeline forecasts the next 30
minutes on every candle, and the report narrates the day in three acts:

1. **The rally** — Kronos calls 30-minute direction correctly **~68%** of the
   time and fires momentum **signals** (Data Activator `SignalLargeMove`), most
   of which hit.
2. **The shock** — an unscheduled ~3% drop that *no* model can forecast; the
   forecast keeps projecting the prior trend while price dives.
3. **The guardrail** — forecast error spikes, and the model-health rule
   (`AlertForecastDrift`) **auto-detects the regime break within ~17 minutes**,
   before a human would notice.

That third act is the honest, load-bearing value: the system does not pretend to
predict shocks — it *knows when it has stopped tracking reality* and says so
automatically.

## How each stage maps to the architecture

| Demo module | Plays the role of | Architecture component |
|---|---|---|
| `synthetic.generate_ticks` | market feed | Azure Event Hubs / Fabric Eventstream |
| `synthetic.aggregate_ohlcv` | tick → candle | Eventhouse materialized view (`candles_1m`) |
| `forecaster.KronosAdapter` | model plane | Azure ML online endpoint (`predict_batch`) |
| `pipeline.run_rolling_forecasts` | orchestrator | Fabric notebook |
| `pipeline.evaluate` / forecast store | accuracy + persistence | Eventhouse `forecasts` + `ForecastAccuracy()` |
| `pipeline.detect_signals` | momentum signal | Data Activator `SignalLargeMove()` |
| `pipeline.detect_drift` | model-health alarm | Data Activator `AlertForecastDrift()` |
| `report.build_html` | dashboard | Real-Time Dashboard |

## Running with the real Kronos model

The forecaster is an adapter. To swap the transparent baseline for the real
foundation model, install the deps and enable it — **nothing else changes**:

```bash
pip install -r requirements.txt          # torch, etc.
KRONOS_ENABLE=1 python deploy/azure/demo/run_demo.py
```

With `KRONOS_ENABLE=1` and weights reachable, `KronosAdapter` loads
`NeoQuasar/Kronos-*` and calls `KronosPredictor.predict` — the same call the
Azure ML `score.py` endpoint makes in production.

## Files

```
synthetic.py    ticks + OHLCV candle aggregation (feed + Eventhouse MV)
forecaster.py   KronosAdapter (real Kronos, else baseline) — endpoint contract
pipeline.py     rolling forecasts, accuracy, signals, drift guardrail
report.py       self-contained, theme-aware HTML report (inline SVG + hover)
run_demo.py     narrated end-to-end runner
```

> The demo is illustrative. Numbers come from synthetic data with a fixed seed,
> so the story is reproducible; they are **not** a claim about live-market
> performance. See the production caveats in
> [`../../../docs/azure/kronos-on-azure-fabric-rta.md`](../../../docs/azure/kronos-on-azure-fabric-rta.md).
