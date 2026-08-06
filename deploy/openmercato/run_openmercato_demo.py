"""
Open Mercato × Kronos × Azure — end-to-end demo runner.

Runs the commerce loop offline and narrates each stage against the Azure/Fabric
(or Azure-only) component it stands in for, then emits KQL that replays into a
Fabric Eventhouse OR Azure Data Explorer.

    python deploy/openmercato/run_openmercato_demo.py [--out DIR]

Reuses the markets demo's pipeline, forecaster and guardrail unchanged — only the
data source (synthetic Open Mercato order stream) is new.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "azure", "demo"))

from marketplace import generate_session          # noqa: E402
from forecaster import KronosAdapter               # noqa: E402
from pipeline import run_pipeline                   # noqa: E402
from kql_emit_om import write_kql_bundle            # noqa: E402


STAGES = [
    ("1  Events", "Open Mercato order.* / sales.* (Redis bus)", "synthetic order stream"),
    ("2  Bridge", "subscriber -> Azure Event Hubs", "forward domain events"),
    ("3  Bars", "Eventhouse / ADX materialized view (gmv_1m)", "orders -> sales bars"),
    ("4  Forecast", "Fabric NB / Azure Function -> Azure ML (Kronos)", "rolling demand forecast"),
    ("5  Visualize", "Real-Time Dashboard / ADX dashboard", "actual vs forecast GMV"),
    ("6  Act", "Data Activator / Functions", "demand signals + model-health alerts"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--no-kql", action="store_true")
    ap.add_argument("--signal-threshold", type=float, default=0.015)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    print("\n\033[1mOpen Mercato x Kronos x Azure — real-time demand demo\033[0m")
    print("=" * 74)
    for tag, comp, what in STAGES:
        print(f"  {tag:12s} -> {comp:46s} | {what}")
    print("=" * 74 + "\n")

    bars, meta, orders = generate_session(return_orders=True)
    print(f"[1-3] {meta['n_ticks']:,} order events -> {meta['n_candles']:,} 1m sales bars "
          f"for '{meta['symbol']}'; checkout outage at {meta['shock_time']}")

    forecaster = KronosAdapter()
    print(f"[4]   forecaster engine = {forecaster.engine!r} ({forecaster.label})")

    result = run_pipeline(bars, meta, forecaster, signal_threshold=args.signal_threshold)
    result["orders"] = orders
    s = result["stats"]
    print(f"[4]   {s['n_forecasts']} rolling demand forecasts (lookback={s['lookback']}, "
          f"horizon={s['pred_len']}m)")
    print(f"[5]   in-regime directional accuracy = {s['directional_accuracy']*100:.1f}% | "
          f"median MAPE = {s['in_regime_median_mape']*100:.2f}%")
    print(f"[6]   {s['n_signals']} demand signals, hit-rate = {s['signal_hit_rate']*100:.1f}% "
          f"(flash sale -> surge signals)")
    if s["detection_latency_min"] is not None:
        print(f"[6]   MODEL-HEALTH ALERT: checkout outage auto-detected "
              f"{s['detection_latency_min']:.0f} min after it began "
              f"(first breach {s['first_alert_time']})")

    if not args.no_kql:
        km = write_kql_bundle(result, args.out)
        kb = sum(km["files"].values()) / 1024
        print(f"[KQL] round-trip bundle -> {km['dir']} ({len(km['files'])} files, {kb:.0f} KB): "
              f"paste replay_all.kql into Fabric Eventhouse OR Azure Data Explorer")

    with open(os.path.join(args.out, "demo_result.json"), "w") as f:
        json.dump({k: result[k] for k in ("stats", "signals", "drift", "meta", "config")},
                  f, indent=2, default=str)
    print(f"\n  wrote {os.path.join(args.out, 'demo_result.json')}\n")


if __name__ == "__main__":
    main()
