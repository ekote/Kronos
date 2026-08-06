"""
Synthetic Open Mercato commerce stream for the Kronos demo.

Plays the role of an Open Mercato event source: it emits `order.paid` events for
one store-day, then aggregates them into per-minute **sales bars** with the exact
OHLCV shape Kronos consumes — so the same pipeline, forecaster, and guardrail as
the markets demo work unchanged.

The demand series is what matters, so we map it onto `close`:

    close = GMV per minute (revenue)     open = high = low = close  (flat bar)
    volume = orders in the minute        amount = units in the minute

The day has genuine structure (diurnal shape + AR(1) demand) plus two scripted
events: a **flash sale** (a demand surge → momentum signals) and a **checkout
outage** (orders collapse → the shock the model-health guardrail must catch).

Pure standard library.
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone


def generate_orders(
    tenant="store_hydra",
    minutes=540,
    base_gmv=5200.0,          # baseline GMV per minute (USD)
    aov=58.0,                 # average order value (USD)
    drift=0.0006,             # gentle session uptrend
    ar1=0.45,                 # demand momentum — AR(1) on GMV log-returns
    vol=0.005,                # per-minute GMV volatility (calm regime)
    diurnal_amp=0.35,         # intraday shape
    flash_minute=285, flash_dur=20, flash_mult=1.6,   # flash sale (surge)
    outage_minute=390, outage_dur=15, outage_drop=0.15,  # checkout outage (shock)
    seed=11,
):
    """Emit order events matching a forecastable GMV series (AR(1) returns + diurnal)."""
    rng = random.Random(seed)
    start = datetime(2025, 3, 3, 8, 0, 0, tzinfo=timezone.utc)
    channels = ["web", "web", "web", "mobile", "b2b"]
    orders = []
    walk = base_gmv
    prev_ret = 0.0
    oid = 0
    for m in range(minutes):
        # GMV log-returns are AR(1) around a drift -> genuine short-horizon momentum.
        ret = drift + ar1 * (prev_ret - drift) + rng.gauss(0, vol)
        prev_ret = ret
        walk *= math.exp(ret)
        diurnal = 1.0 + diurnal_amp * math.sin(math.pi * m / minutes)
        target = walk * diurnal
        if flash_minute <= m < flash_minute + flash_dur:
            target *= flash_mult
        if outage_minute <= m < outage_minute + outage_dur:
            target *= outage_drop

        # Emit orders whose GMV reconstructs the target (tight amounts -> low added noise).
        count = max(1, int(round(target / aov)))
        minute_start = start + timedelta(minutes=m)
        for _ in range(count):
            oid += 1
            sec = rng.randint(0, 59)
            amount = round(rng.lognormvariate(math.log(aov), 0.15), 2)
            units = 1 + int(rng.random() < 0.4) + int(rng.random() < 0.15)
            orders.append((tenant, minute_start + timedelta(seconds=sec),
                           f"o_{oid:06d}", amount, units, rng.choice(channels)))
    return orders, start


def aggregate_bars(orders, start, minutes=540, tenant="store_hydra", floor=1.0):
    """Contiguous per-minute sales bars: close = GMV/min (floored), volume=orders, amount=units."""
    gmv = [0.0] * minutes
    ordc = [0] * minutes
    unitc = [0] * minutes
    for _, et, _oid, amount, units, _ch in orders:
        idx = int((et - start).total_seconds() // 60)
        if 0 <= idx < minutes:
            gmv[idx] += amount
            ordc[idx] += 1
            unitc[idx] += units

    bars = []
    for m in range(minutes):
        g = max(gmv[m], floor)   # floor keeps the series log-safe during the outage
        ts = (start + timedelta(minutes=m)).isoformat()
        bars.append({
            "symbol": tenant, "event_time": ts,
            "open": round(g, 2), "high": round(g, 2), "low": round(g, 2), "close": round(g, 2),
            "volume": float(ordc[m]), "amount": float(unitc[m]),
        })
    return bars


def generate_session(return_orders=False, **kwargs):
    """Full stream + aggregation → (bars, meta[, orders])."""
    tenant = kwargs.get("tenant", "store_hydra")
    minutes = kwargs.get("minutes", 540)
    outage_minute = kwargs.get("outage_minute", 390)
    orders, start = generate_orders(**kwargs)
    bars = aggregate_bars(orders, start, minutes, tenant)
    meta = {
        "symbol": tenant,
        "n_ticks": len(orders),           # (orders) — keeps the pipeline's field name
        "n_candles": len(bars),
        "session_start": start.isoformat(),
        "shock_index": outage_minute,     # the checkout outage is the shock to detect
        "shock_time": bars[outage_minute]["event_time"] if outage_minute < len(bars) else None,
    }
    if return_orders:
        return bars, meta, orders
    return bars, meta
