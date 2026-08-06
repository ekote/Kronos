"""
Emit the Open Mercato demo as KQL — runs against a Fabric Eventhouse OR Azure
Data Explorer (both speak KQL, so it's the same script either way).

Reuses the generic emitters from the markets demo (`forecasts`, `signals`,
`model_health_alerts` share schemas); only the source table (`orders_raw`) and
the sales-bar materialized view (`gmv_1m`) are commerce-specific.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "azure", "demo"))

import kql_emit as K   # noqa: E402


def emit_orders(orders, batch=1000):
    cols = [("tenant_id", "string"), ("event_time", "datetime"), ("order_id", "string"),
            ("amount", "real"), ("units", "int"), ("channel", "string")]
    rows = []
    for tenant, et, oid, amount, units, channel in orders:
        iso = et.isoformat().replace("+00:00", "Z")
        rows.append([K._s(tenant), f"datetime({iso})", K._s(oid), K._num(amount),
                     str(units), K._s(channel)])
    return K._datatable("orders_raw", cols, rows, batch)


_SETUP = """// Open Mercato demo — tables (Fabric Eventhouse OR Azure Data Explorer).
.create-merge table orders_raw (tenant_id:string, event_time:datetime, order_id:string, amount:real, units:int, channel:string)
.create-merge table forecasts (symbol:string, run_id:string, run_time:datetime, target_time:datetime, open:real, high:real, low:real, close:real, volume:real, amount:real, horizon_step:int, model_version:string, sampling:dynamic)
.create-merge table signals (symbol:string, origin_time:datetime, direction:string, expected_move_pct:real, realized_move_pct:real, hit:bool, model_version:string)
.create-merge table model_health_alerts (symbol:string, alert_time:datetime, kind:string, smoothed_mape:real, band:real, detail:string)
"""

# gmv_1m: per-minute sales bar. close = GMV (revenue); the lookback function
# projects the OHLCV shape Kronos consumes (a flat bar whose level is GMV/min).
_MV = """// Sales bars from the order stream (run AFTER orders are loaded).
.create-or-alter materialized-view with (backfill=true) gmv_1m on table orders_raw {
    orders_raw
    | summarize gmv = sum(amount), orders = todouble(count()), units = todouble(sum(units))
      by tenant_id, event_time = bin(event_time, 1m)
}

// Kronos lookback: latest N sales bars for a tenant, as OHLCV (close = GMV/min).
.create-or-alter function KronosSalesLookback(tenant:string, lookback:int) {
    materialized_view('gmv_1m')
    | where tenant_id == tenant and event_time < bin(now(), 1m)
    | top lookback by event_time desc
    | order by event_time asc
    | project event_time, open = gmv, high = gmv, low = gmv, close = gmv,
              volume = orders, amount = units
}
"""


def emit_verify(tenant):
    return f"""// --- Verify the round-trip ---
orders_raw | summarize orders = count(), first = min(event_time), last = max(event_time)
materialized_view('gmv_1m') | summarize bars = count() by tenant_id
forecasts | summarize forecast_rows = count(), runs = dcount(run_id)
model_health_alerts | summarize alerts = count(), first_alert = min(alert_time)

// Dashboard: actual GMV vs latest forecast for "{tenant}"
let latest = forecasts | summarize arg_max(run_time, *) by target_time
    | project event_time = target_time, gmv = close, series = "forecast";
let actual = materialized_view('gmv_1m') | where tenant_id == "{tenant}"
    | project event_time, gmv, series = "actual";
union actual, latest | order by event_time asc
"""


def iter_commands(result, include_orders=True):
    tenant = result["meta"]["symbol"]
    mv = K._model_version(result)
    sampling = K._sampling(result)
    for line in _SETUP.splitlines():
        if line.strip().startswith(".create-merge"):
            yield ("setup", line.strip())
    if include_orders and result.get("orders"):
        for b in K._batches(emit_orders(result["orders"])):
            yield ("orders", b)
    for cmd in _MV.split("\n\n"):
        cmd = "\n".join(l for l in cmd.splitlines() if not l.strip().startswith("//")).strip()
        if cmd:
            yield ("sales_view", cmd)
    for b in K._batches(K.emit_forecasts(result["runs"], tenant, mv, sampling)):
        yield ("forecasts", b)
    for b in K._batches(K.emit_signals(result["signals"], tenant, mv)):
        yield ("signals", b)
    for b in K._batches(K.emit_alerts(result["drift"], tenant, result["drift"]["band"])):
        yield ("model_health_alerts", b)


def write_kql_bundle(result, outdir, emit_orders_data=True):
    kql_dir = os.path.join(outdir, "kql")
    os.makedirs(kql_dir, exist_ok=True)
    tenant = result["meta"]["symbol"]
    mv = K._model_version(result)
    sampling = K._sampling(result)
    files = {}

    def _w(name, header, body):
        p = os.path.join(kql_dir, name)
        with open(p, "w") as f:
            f.write(f"// {header}\n// Open Mercato × Kronos — Fabric Eventhouse or Azure Data Explorer\n\n{body}\n")
        files[name] = os.path.getsize(p)

    _w("00_setup.kql", "Stage 0 — tables", _SETUP)
    if emit_orders_data and result.get("orders"):
        _w("10_replay_orders.kql", "Stage 1 — replay order events into orders_raw",
           emit_orders(result["orders"]))
    _w("15_sales_bars_view.kql", "Stage 2 — gmv_1m sales-bar materialized view", _MV)
    _w("20_forecasts.kql", "Stage 3-4 — Kronos demand forecasts",
       K.emit_forecasts(result["runs"], tenant, mv, sampling))
    _w("30_signals.kql", "Stage 6a — demand signals", K.emit_signals(result["signals"], tenant, mv))
    _w("40_model_health_alerts.kql", "Stage 6b — model-health alerts",
       K.emit_alerts(result["drift"], tenant, result["drift"]["band"]))
    _w("90_verify.kql", "Verify + dashboard query", emit_verify(tenant))

    order = ["00_setup.kql", "10_replay_orders.kql", "15_sales_bars_view.kql", "20_forecasts.kql",
             "30_signals.kql", "40_model_health_alerts.kql", "90_verify.kql"]
    combined = []
    for n in order:
        p = os.path.join(kql_dir, n)
        if os.path.exists(p):
            combined.append(open(p).read())
    with open(os.path.join(kql_dir, "replay_all.kql"), "w") as f:
        f.write("\n\n// " + "=" * 74 + "\n\n".join(combined))
    files["replay_all.kql"] = os.path.getsize(os.path.join(kql_dir, "replay_all.kql"))
    return {"dir": kql_dir, "files": files, "model_version": mv}
