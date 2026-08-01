"""
Kronos on Azure / Microsoft Fabric RTI — end-to-end demo runner.

Runs the whole story offline and narrates each stage against the Azure/Fabric
component it stands in for, then writes a self-contained HTML report.

    python deploy/azure/demo/run_demo.py [--out DIR]

Set KRONOS_ENABLE=1 (with torch + weights installed) to swap the baseline
forecaster for the real Kronos foundation model — nothing else changes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from synthetic import generate_session
from forecaster import KronosAdapter
from pipeline import run_pipeline
from report import build_html


STAGES = [
    ("1  Feed", "Azure Event Hubs / Fabric Eventstream", "generate synthetic ticks"),
    ("2  Candles", "Eventhouse materialized view (candles_1m)", "aggregate ticks -> OHLCV"),
    ("3  Forecast", "Fabric notebook -> Azure ML endpoint (Kronos)", "rolling predict()"),
    ("4  Store", "Eventhouse forecasts table", "persist forecast runs"),
    ("5  Visualize", "Real-Time Dashboard", "actual vs forecast + accuracy"),
    ("6  Act", "Data Activator (Reflex)", "momentum signals + drift alerts"),
]


def narrate(line: str):
    print(line, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "output"))
    ap.add_argument("--lookback", type=int, default=120)
    ap.add_argument("--pred-len", type=int, default=30)
    ap.add_argument("--stride", type=int, default=3)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    narrate("\n\033[1mKronos on Azure — Fabric Real-Time Intelligence : end-to-end demo\033[0m")
    narrate("=" * 72)
    for tag, comp, what in STAGES:
        narrate(f"  {tag:14s} -> {comp:44s} | {what}")
    narrate("=" * 72 + "\n")

    # Stage 1-2: feed + candle building.
    candles, meta = generate_session()
    narrate(f"[1-2] {meta['n_ticks']:,} ticks -> {meta['n_candles']:,} 1m candles "
            f"for {meta['symbol']}; scripted news shock at {meta['shock_time']}")

    # Stage 3: the model plane.
    forecaster = KronosAdapter()
    narrate(f"[3]   forecaster engine = {forecaster.engine!r} ({forecaster.label})")

    # Stage 3-6: orchestrate, store, evaluate, act.
    result = run_pipeline(candles, meta, forecaster,
                          lookback=args.lookback, pred_len=args.pred_len, stride=args.stride)
    s = result["stats"]
    narrate(f"[3-4] {s['n_forecasts']} rolling forecasts "
            f"(lookback={s['lookback']}, horizon={s['pred_len']}m) stored")
    narrate(f"[5]   in-regime directional accuracy = {s['directional_accuracy']*100:.1f}% | "
            f"median MAPE = {s['in_regime_median_mape']*100:.2f}%")
    narrate(f"[6]   {s['n_signals']} momentum signals fired, "
            f"hit-rate = {s['signal_hit_rate']*100:.1f}%")
    if s["detection_latency_min"] is not None:
        narrate(f"[6]   MODEL-HEALTH ALERT: regime change auto-detected "
                f"{s['detection_latency_min']:.0f} min after the shock "
                f"(first breach {s['first_alert_time']})")

    # Write artifacts.
    json_path = os.path.join(args.out, "demo_result.json")
    with open(json_path, "w") as f:
        json.dump({k: result[k] for k in ("stats", "signals", "drift", "meta", "config")},
                  f, indent=2, default=str)
    html = build_html(result)
    html_path = os.path.join(args.out, "kronos_fabric_demo.html")
    with open(html_path, "w") as f:
        f.write(html)

    narrate(f"\n  wrote {json_path}")
    narrate(f"  wrote {html_path}\n")
    return html_path


if __name__ == "__main__":
    main()
