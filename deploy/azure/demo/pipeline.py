"""
End-to-end pipeline — the orchestration + action plane, offline.

Plays the role of the Fabric notebook orchestrator + Data Activator:
  * rolling forecasts   -> Fabric notebook calling the AML endpoint per candle
  * forecast store      -> Eventhouse `forecasts` table
  * accuracy tracking   -> ForecastAccuracy() KQL function
  * momentum signals    -> Data Activator SignalLargeMove()
  * model-health drift  -> Data Activator AlertForecastDrift()

Everything here is deterministic given the synthetic session, so the demo tells
the same story every run.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timedelta


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def _future_times(last_iso: str, pred_len: int, step_min: int = 1) -> list[str]:
    base = _dt(last_iso)
    return [(base + timedelta(minutes=step_min * (i + 1))).isoformat() for i in range(pred_len)]


def run_rolling_forecasts(candles, forecaster, lookback=120, pred_len=30, stride=3,
                          sampling=None):
    """For each origin candle (every `stride`), forecast the next `pred_len`."""
    runs = []
    n = len(candles)
    for origin in range(lookback, n, stride):
        window = candles[origin - lookback:origin]
        future_times = _future_times(window[-1]["event_time"], pred_len)
        forecast = forecaster.forecast(window, pred_len, future_times, sampling)
        runs.append({
            "origin_index": origin,
            "origin_time": window[-1]["event_time"],
            "origin_close": window[-1]["close"],
            "forecast": forecast,
        })
    return runs


def evaluate(runs, candles, pred_len):
    """Join each forecast horizon to realized candles and score it."""
    close_by_time = {c["event_time"]: c["close"] for c in candles}
    for run in runs:
        realized, abs_pct = [], []
        for f in run["forecast"]:
            actual = close_by_time.get(f["target_time"])
            realized.append(actual)
            if actual:
                abs_pct.append(abs(f["close"] - actual) / actual)
        run["realized"] = realized
        run["mape"] = statistics.mean(abs_pct) if abs_pct else None

        # Directional skill over the full horizon.
        f_end = run["forecast"][-1]["close"]
        a_end = realized[-1]
        run["expected_move_pct"] = (f_end - run["origin_close"]) / run["origin_close"]
        if a_end is not None:
            realized_move = (a_end - run["origin_close"]) / run["origin_close"]
            run["realized_move_pct"] = realized_move
            run["direction_hit"] = (f_end > run["origin_close"]) == (a_end > run["origin_close"])
            # Evaluation completes when the last horizon candle closes.
            run["eval_time"] = run["forecast"][-1]["target_time"]
        else:
            run["realized_move_pct"] = None
            run["direction_hit"] = None
            run["eval_time"] = None
    return runs


def detect_signals(runs, threshold_pct=0.006):
    """Data Activator SignalLargeMove: forecast expects a move >= threshold."""
    signals = []
    for run in runs:
        if abs(run["expected_move_pct"]) >= threshold_pct and run["realized_move_pct"] is not None:
            signals.append({
                "origin_time": run["origin_time"],
                "direction": "UP" if run["expected_move_pct"] > 0 else "DOWN",
                "expected_move_pct": run["expected_move_pct"],
                "realized_move_pct": run["realized_move_pct"],
                "hit": run["direction_hit"],
            })
    return signals


def _rolling_mean(xs, w):
    out = []
    for i in range(len(xs)):
        window = xs[max(0, i - w + 1):i + 1]
        out.append(sum(window) / len(window))
    return out


def detect_drift(runs, shock_time, baseline_frac=0.30, band_mult=3.0, smooth_w=5,
                 sustain=2, warmup=8):
    """Data Activator AlertForecastDrift: rolling forecast error breaches a band.

    The band is learned from the calm pre-shock regime. To behave like a real
    monitor (and not trip on single-run noise) the error is smoothed over a
    short window and the alert requires a *sustained* breach. A short `warmup` is
    excluded up front — a monitor cannot alert before it has established a stable
    baseline. The first sustained breach is the automatically-detected regime
    change.
    """
    scored = [r for r in runs if r["mape"] is not None and r["eval_time"] is not None]
    scored.sort(key=lambda r: r["eval_time"])
    scored = scored[warmup:]
    raw = [r["mape"] for r in scored]
    smooth = _rolling_mean(raw, smooth_w)

    n_base = max(5, int(len(scored) * baseline_frac))
    base_vals = sorted(smooth[:n_base])
    base_med = statistics.median(base_vals)
    base_p90 = base_vals[int(0.9 * (len(base_vals) - 1))]
    band = max(base_p90 * 1.4, base_med * band_mult)

    series, run_len, first_alert = [], 0, None
    for r, m, sm in zip(scored, raw, smooth):
        breach = sm > band
        run_len = run_len + 1 if breach else 0
        alert = breach and run_len >= sustain
        if alert and first_alert is None:
            first_alert = r["eval_time"]
        series.append({"eval_time": r["eval_time"], "mape": m,
                       "smoothed": sm, "breach": breach, "alert": alert})

    detection_latency_min = None
    if first_alert and shock_time:
        detection_latency_min = round(
            (_dt(first_alert) - _dt(shock_time)).total_seconds() / 60.0, 1)

    return {
        "series": series,
        "baseline_mape": base_med,
        "band": band,
        "first_alert_time": first_alert,
        "detection_latency_min": detection_latency_min,
    }


def summarize(runs, signals, drift, meta, forecaster, config):
    scored = [r for r in runs if r["direction_hit"] is not None]
    in_regime = [r for r in scored if r["mape"] is not None and r["mape"] <= drift["band"]]
    dir_acc = statistics.mean([1.0 if r["direction_hit"] else 0.0 for r in in_regime]) if in_regime else 0.0
    sig_hits = [s for s in signals if s["hit"]]
    sig_hit_rate = len(sig_hits) / len(signals) if signals else 0.0
    med_mape = statistics.median([r["mape"] for r in in_regime]) if in_regime else 0.0
    return {
        "engine": forecaster.engine,
        "engine_label": forecaster.label,
        "symbol": meta["symbol"],
        "n_candles": meta["n_candles"],
        "n_ticks": meta["n_ticks"],
        "n_forecasts": len(runs),
        "lookback": config["lookback"],
        "pred_len": config["pred_len"],
        "directional_accuracy": dir_acc,
        "in_regime_median_mape": med_mape,
        "n_signals": len(signals),
        "signal_hit_rate": sig_hit_rate,
        "baseline_mape": drift["baseline_mape"],
        "drift_band": drift["band"],
        "detection_latency_min": drift["detection_latency_min"],
        "first_alert_time": drift["first_alert_time"],
        "shock_time": meta["shock_time"],
    }


def run_pipeline(candles, meta, forecaster, lookback=120, pred_len=30, stride=3,
                 signal_threshold=0.010, sampling=None):
    config = {"lookback": lookback, "pred_len": pred_len, "stride": stride}
    runs = run_rolling_forecasts(candles, forecaster, lookback, pred_len, stride, sampling)
    runs = evaluate(runs, candles, pred_len)
    signals = detect_signals(runs, signal_threshold)
    drift = detect_drift(runs, meta["shock_time"])
    stats = summarize(runs, signals, drift, meta, forecaster, config)
    return {"candles": candles, "runs": runs, "signals": signals,
            "drift": drift, "stats": stats, "meta": meta, "config": config}
