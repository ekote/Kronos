"""
Forecaster adapter — the model plane, offline.

`KronosAdapter` presents the same "give me a lookback window, get N future
candles" contract the Azure ML endpoint exposes (see
`deploy/azure/azureml/score.py`). It uses the **real Kronos foundation model**
when torch + weights are available (and `KRONOS_ENABLE=1`), and otherwise falls
back to a transparent statistical `BaselineForecaster` so the end-to-end demo
runs anywhere with zero dependencies.

The baseline is a legitimate short-horizon model (drift + AR(1) on log-returns),
not a cheat: it has real directional skill on data with momentum, and — like any
model — it cannot predict the unscripted news shock. That honest gap is exactly
what the demo's model-health guardrail is built to catch.
"""
from __future__ import annotations

import os
import math
import statistics
from datetime import datetime, timedelta


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


class BaselineForecaster:
    """Drift + AR(1) log-return projection with realistic OHLC/volume synthesis."""

    engine = "baseline"
    label = "Baseline (drift + AR(1)) — Kronos-compatible interface"

    def forecast(self, lookback: list[dict], pred_len: int, future_times: list[str],
                 sampling: dict | None = None) -> list[dict]:
        closes = [c["close"] for c in lookback]
        symbol = lookback[-1]["symbol"]
        rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
        if len(rets) < 3:
            rets = [0.0, 0.0, 0.0]

        mu = _mean(rets)
        sigma = statistics.pstdev(rets) or 1e-6
        # Lag-1 autocorrelation → AR(1) coefficient (clamped for stability).
        num = sum((rets[i] - mu) * (rets[i - 1] - mu) for i in range(1, len(rets)))
        den = sum((r - mu) ** 2 for r in rets) or 1e-9
        phi = max(-0.6, min(0.6, num / den))

        # Recent bar geometry, used to synthesize plausible OHLC around the path.
        rng_ratio = _mean([(c["high"] - c["low"]) / c["close"] for c in lookback[-30:]]) or 0.001
        body_ratio = _mean([abs(c["close"] - c["open"]) / c["close"] for c in lookback[-30:]]) or 0.0005
        vol_ewma = closes and _ewma([c["volume"] for c in lookback[-30:]], 0.3)

        out = []
        prev_close = closes[-1]
        prev_ret = rets[-1]
        for k in range(pred_len):
            ret = mu + phi * (prev_ret - mu)          # expected next return
            prev_ret = ret
            close = prev_close * math.exp(ret)
            open_ = prev_close
            half = 0.5 * rng_ratio * close
            hi = max(open_, close) + half * 0.6
            lo = min(open_, close) - half * 0.6
            out.append({
                "symbol": symbol,
                "target_time": future_times[k],
                "horizon_step": k + 1,
                "open": round(open_, 2),
                "high": round(hi, 2),
                "low": round(lo, 2),
                "close": round(close, 2),
                "volume": round(vol_ewma or 0.0, 4),
                "amount": round(close * (vol_ewma or 0.0), 2),
            })
            prev_close = close
        return out


def _ewma(xs, alpha):
    if not xs:
        return 0.0
    acc = xs[0]
    for x in xs[1:]:
        acc = alpha * x + (1 - alpha) * acc
    return acc


class KronosAdapter:
    """Same call shape as the AML endpoint; real Kronos when available."""

    def __init__(self, model_id="NeoQuasar/Kronos-base",
                 tokenizer_id="NeoQuasar/Kronos-Tokenizer-base", max_context=512):
        self.model_id = model_id
        self.tokenizer_id = tokenizer_id
        self.max_context = max_context
        self._predictor = None
        self.engine = "baseline"
        self.label = BaselineForecaster.label
        self._baseline = BaselineForecaster()
        if os.getenv("KRONOS_ENABLE") == "1":
            self._try_load_kronos()

    def _try_load_kronos(self):
        try:
            import torch  # noqa
            from model import Kronos, KronosTokenizer, KronosPredictor
            tok = KronosTokenizer.from_pretrained(self.tokenizer_id)
            mdl = Kronos.from_pretrained(self.model_id)
            self._predictor = KronosPredictor(mdl, tok, max_context=self.max_context)
            self.engine = "kronos"
            self.label = f"Kronos foundation model ({self.model_id})"
        except Exception as e:  # pragma: no cover - depends on optional deps
            print(f"[KronosAdapter] real model unavailable ({type(e).__name__}: {e}); "
                  f"using baseline forecaster.")

    def forecast(self, lookback, pred_len, future_times, sampling=None):
        if self._predictor is None:
            return self._baseline.forecast(lookback, pred_len, future_times, sampling)
        return self._forecast_kronos(lookback, pred_len, future_times, sampling or {})

    def _forecast_kronos(self, lookback, pred_len, future_times, sampling):  # pragma: no cover
        import pandas as pd
        cols = ["open", "high", "low", "close", "volume", "amount"]
        df = pd.DataFrame([[c[k] for k in cols] for c in lookback], columns=cols)
        x_ts = pd.Series(pd.to_datetime([c["event_time"] for c in lookback]))
        y_ts = pd.Series(pd.to_datetime(future_times))
        pred = self._predictor.predict(
            df=df, x_timestamp=x_ts, y_timestamp=y_ts, pred_len=pred_len,
            T=sampling.get("T", 1.0), top_p=sampling.get("top_p", 0.9),
            top_k=sampling.get("top_k", 0), sample_count=sampling.get("sample_count", 1),
            verbose=False,
        )
        symbol = lookback[-1]["symbol"]
        out = []
        for k, (ts, row) in enumerate(zip(future_times, pred.itertuples(index=False))):
            out.append({
                "symbol": symbol, "target_time": ts, "horizon_step": k + 1,
                "open": float(row.open), "high": float(row.high),
                "low": float(row.low), "close": float(row.close),
                "volume": float(getattr(row, "volume", 0.0)),
                "amount": float(getattr(row, "amount", 0.0)),
            })
        return out
