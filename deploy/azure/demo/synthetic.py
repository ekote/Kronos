"""
Synthetic market data for the Kronos-on-Fabric demo.

Stage 1-2 of the architecture, offline: it plays the role of the market feed
(Azure Event Hubs / Fabric Eventstream) by generating raw ticks, then plays the
Eventhouse OHLCV *materialized view* by aggregating those ticks into 1-minute
candles with exactly the arg_min/arg_max/max/min/sum logic used in
`deploy/azure/fabric/eventhouse/02_ohlcv_materialized_views.kql`.

The price process has genuine short-horizon structure (drift + AR(1) momentum),
so a forecaster has real signal to exploit — and a scripted, *unpredictable*
news shock mid-session, so the demo can honestly show the difference between
"forecasting well in-regime" and "detecting when the model stops tracking".

Pure standard library: no numpy/pandas required.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone


@dataclass
class Candle:
    symbol: str
    event_time: str          # ISO-8601 (UTC), candle open time
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float

    def as_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Stage 1: the "feed" — generate raw ticks for one intraday session.
# ---------------------------------------------------------------------------
def generate_ticks(
    symbol: str = "BTCUSDT",
    start: datetime | None = None,
    minutes: int = 540,
    ticks_per_minute: int = 12,
    start_price: float = 62_000.0,
    drift_per_min: float = 0.00018,      # gentle upward session bias
    ar1: float = 0.42,                   # momentum: returns are autocorrelated
    vol_per_min: float = 0.0013,         # ~0.13% per-minute stdev in calm regime
    shock_minute: int = 360,             # scripted news shock (unpredictable)
    shock_return: float = -0.030,        # one-off -3.0% jump
    shock_vol_mult: float = 3.0,         # volatility spike around the shock
    shock_decay_min: int = 15,           # minutes for volatility to normalize
    seed: int = 7,
):
    """Yield (Tick) rows: (symbol, event_time ISO, price, size). One session."""
    rng = random.Random(seed)
    if start is None:
        # Fixed, tz-aware start so the demo is fully deterministic.
        start = datetime(2025, 3, 3, 8, 0, 0, tzinfo=timezone.utc)

    price = start_price
    prev_ret = 0.0
    ticks = []
    for m in range(minutes):
        # Regime: elevated volatility for a window after the shock.
        if 0 <= m - shock_minute < shock_decay_min:
            decay = 1.0 - (m - shock_minute) / shock_decay_min
            vol = vol_per_min * (1.0 + (shock_vol_mult - 1.0) * decay)
        else:
            vol = vol_per_min

        # AR(1) minute return around the drift, plus the one-off shock jump.
        eps = rng.gauss(0.0, vol)
        ret = drift_per_min + ar1 * (prev_ret - drift_per_min) + eps
        if m == shock_minute:
            ret += shock_return
        prev_ret = ret

        minute_open_price = price
        minute_close_price = price * math.exp(ret)

        # Sub-minute ticks interpolate open->close with noise (builds real OHLC).
        minute_start = start + timedelta(minutes=m)
        for t in range(ticks_per_minute):
            frac = (t + 1) / ticks_per_minute
            base = minute_open_price * math.exp(ret * frac)
            jitter = base * rng.gauss(0.0, vol * 0.35)
            tick_price = max(1.0, base + jitter)
            size = abs(rng.gauss(1.0, 0.4)) * (1.0 + (vol / vol_per_min - 1.0))
            event_time = minute_start + timedelta(seconds=int(60 * frac) - 1)
            ticks.append((symbol, event_time, round(tick_price, 2), round(size, 4)))
        price = minute_close_price

    return ticks, start


# ---------------------------------------------------------------------------
# Stage 2: the Eventhouse materialized view — ticks -> 1m OHLCV candles.
# Mirrors candles_1m in 02_ohlcv_materialized_views.kql.
# ---------------------------------------------------------------------------
def aggregate_ohlcv(ticks, bar_seconds: int = 60) -> list[Candle]:
    """Aggregate raw ticks into OHLCV candles (arg_min open / arg_max close)."""
    buckets: dict[tuple[str, int], list] = {}
    for symbol, event_time, price, size in ticks:
        epoch = int(event_time.replace(tzinfo=timezone.utc).timestamp())
        bin_start = epoch - (epoch % bar_seconds)
        buckets.setdefault((symbol, bin_start), []).append((event_time, price, size))

    candles: list[Candle] = []
    for (symbol, bin_start), rows in sorted(buckets.items(), key=lambda k: (k[0][0], k[0][1])):
        rows.sort(key=lambda r: r[0])
        prices = [r[1] for r in rows]
        sizes = [r[2] for r in rows]
        open_p = rows[0][1]                     # arg_min(event_time, price)
        close_p = rows[-1][1]                    # arg_max(event_time, price)
        candles.append(Candle(
            symbol=symbol,
            event_time=datetime.fromtimestamp(bin_start, tz=timezone.utc).isoformat(),
            open=round(open_p, 2),
            high=round(max(prices), 2),
            low=round(min(prices), 2),
            close=round(close_p, 2),
            volume=round(sum(sizes), 4),
            amount=round(sum(p * s for p, s in zip(prices, sizes)), 2),
        ))
    return candles


def generate_session(**kwargs):
    """Convenience: full Stage 1+2 → (candles, meta)."""
    shock_minute = kwargs.get("shock_minute", 360)
    ticks, start = generate_ticks(**kwargs)
    candles = [c.as_dict() for c in aggregate_ohlcv(ticks)]
    meta = {
        "symbol": kwargs.get("symbol", "BTCUSDT"),
        "n_ticks": len(ticks),
        "n_candles": len(candles),
        "session_start": start.isoformat(),
        "shock_index": shock_minute,
        "shock_time": candles[shock_minute]["event_time"] if shock_minute < len(candles) else None,
    }
    return candles, meta
