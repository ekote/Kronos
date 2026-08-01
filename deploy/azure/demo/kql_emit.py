"""
Emit the demo's pipeline output as Fabric Eventhouse KQL.

Every stage becomes a `.set-or-append` batch against the exact table schemas
defined in `deploy/azure/fabric/eventhouse/*.kql`, so the offline demo genuinely
round-trips into a real Eventhouse:

    ticks_raw            <- raw feed              (candles_1m MV rebuilds candles)
    forecasts            <- Kronos model output
    signals              <- Data Activator SignalLargeMove event log
    model_health_alerts  <- Data Activator AlertForecastDrift event log

`.set-or-append` + `datatable(...)` is used (not `.ingest inline` CSV) because it
carries typed columns — including the `dynamic` sampling blob — natively and is
safe to paste straight into a Fabric KQL queryset.

Deterministic: no wall-clock calls, so the emitted script is byte-stable.
"""
from __future__ import annotations

import json
import os


# ---- literal formatting -----------------------------------------------------
def _dt(iso: str) -> str:
    """ISO string -> KQL datetime() literal."""
    return f"datetime({iso.replace('+00:00', 'Z')})"


def _s(v: str) -> str:
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _num(v) -> str:
    return repr(round(float(v), 6))


def _dyn(obj) -> str:
    return f"dynamic({json.dumps(obj, separators=(',', ':'))})"


def _b(v) -> str:
    return "true" if v else "false"


def _datatable(table: str, columns: list[tuple[str, str]], rows: list[list[str]],
               batch: int = 1000) -> str:
    """Render one or more `.set-or-append table <| datatable(...)[...]` batches."""
    header = ", ".join(f"{name}:{typ}" for name, typ in columns)
    out = []
    for i in range(0, len(rows), batch):
        chunk = rows[i:i + batch]
        body = ",\n  ".join(", ".join(r) for r in chunk)
        out.append(f".set-or-append {table} <|\ndatatable({header})\n[\n  {body}\n]")
    return "\n\n".join(out)


def _run_id(symbol: str, origin_index: int) -> str:
    return f"{symbol}-r{origin_index:05d}"


# ---- per-stage emitters -----------------------------------------------------
def emit_ticks(ticks, batch=1000) -> str:
    cols = [("symbol", "string"), ("event_time", "datetime"), ("price", "real"),
            ("size", "real"), ("source", "string"), ("ingest_time", "datetime")]
    rows = []
    for symbol, event_time, price, size in ticks:
        iso = event_time.isoformat().replace("+00:00", "Z")
        rows.append([_s(symbol), f"datetime({iso})", _num(price), _num(size),
                     _s("synthetic"), f"datetime({iso})"])
    return _datatable("ticks_raw", cols, rows, batch)


def emit_forecasts(runs, symbol, model_version, sampling) -> str:
    cols = [("symbol", "string"), ("run_id", "string"), ("run_time", "datetime"),
            ("target_time", "datetime"), ("open", "real"), ("high", "real"),
            ("low", "real"), ("close", "real"), ("volume", "real"), ("amount", "real"),
            ("horizon_step", "int"), ("model_version", "string"), ("sampling", "dynamic")]
    rows = []
    for run in runs:
        rid = _run_id(symbol, run["origin_index"])
        rt = _dt(run["origin_time"])
        for f in run["forecast"]:
            rows.append([
                _s(symbol), _s(rid), rt, _dt(f["target_time"]),
                _num(f["open"]), _num(f["high"]), _num(f["low"]), _num(f["close"]),
                _num(f["volume"]), _num(f["amount"]), str(f["horizon_step"]),
                _s(model_version), _dyn(sampling),
            ])
    return _datatable("forecasts", cols, rows)


def emit_signals(signals, symbol, model_version) -> str:
    cols = [("symbol", "string"), ("origin_time", "datetime"), ("direction", "string"),
            ("expected_move_pct", "real"), ("realized_move_pct", "real"),
            ("hit", "bool"), ("model_version", "string")]
    rows = [[
        _s(symbol), _dt(x["origin_time"]), _s(x["direction"]),
        _num(x["expected_move_pct"]), _num(x["realized_move_pct"]),
        _b(x["hit"]), _s(model_version),
    ] for x in signals]
    if not rows:
        return f"// no signals fired\n"
    return _datatable("signals", cols, rows)


def emit_alerts(drift, symbol, band_val) -> str:
    cols = [("symbol", "string"), ("alert_time", "datetime"), ("kind", "string"),
            ("smoothed_mape", "real"), ("band", "real"), ("detail", "string")]
    rows = []
    for pt in drift["series"]:
        if pt.get("alert"):
            rows.append([
                _s(symbol), _dt(pt["eval_time"]), _s("drift"),
                _num(pt["smoothed"]), _num(band_val),
                _s(f"forecast error {pt['smoothed']*100:.2f}% > band {band_val*100:.2f}%"),
            ])
    if not rows:
        return "// no model-health alerts fired\n"
    return _datatable("model_health_alerts", cols, rows)


# ---- setup + verify ---------------------------------------------------------
_SETUP = """// Idempotent table setup for the Kronos-on-Fabric demo round-trip.
// Run once in your Eventhouse (or run the canonical scripts under
// deploy/azure/fabric/eventhouse/). Order matters: create ticks_raw, load ticks,
// then create the candles_1m materialized view with backfill=true.

.create-merge table ticks_raw (symbol:string, event_time:datetime, price:real, size:real, source:string, ingest_time:datetime)
.create-merge table forecasts (symbol:string, run_id:string, run_time:datetime, target_time:datetime, open:real, high:real, low:real, close:real, volume:real, amount:real, horizon_step:int, model_version:string, sampling:dynamic)
.create-merge table signals (symbol:string, origin_time:datetime, direction:string, expected_move_pct:real, realized_move_pct:real, hit:bool, model_version:string)
.create-merge table model_health_alerts (symbol:string, alert_time:datetime, kind:string, smoothed_mape:real, band:real, detail:string)
"""

_MV = """// Build OHLCV candles from the replayed ticks (run AFTER ticks are loaded).
.create-or-alter materialized-view with (backfill=true) candles_1m on table ticks_raw {
    ticks_raw
    | summarize open = arg_min(event_time, price), high = max(price), low = min(price),
                close = arg_max(event_time, price), volume = sum(size),
                amount = sum(price * size), ticks = count()
      by symbol, event_time = bin(event_time, 1m)
}
"""


def emit_verify(symbol, stats) -> str:
    return f"""// --- Verify the round-trip -------------------------------------------------
ticks_raw | summarize ticks = count(), first = min(event_time), last = max(event_time)
materialized_view('candles_1m') | summarize candles = count() by symbol
forecasts | summarize forecast_rows = count(), runs = dcount(run_id)
signals | summarize signals = count(), hits = countif(hit)
model_health_alerts | summarize alerts = count(), first_alert = min(alert_time)

// Dashboard: actual vs latest forecast for {symbol}
let latest = forecasts | summarize arg_max(run_time, *) by target_time
    | project event_time = target_time, close, series = "forecast";
let actual = materialized_view('candles_1m') | where symbol == "{symbol}"
    | project event_time, close, series = "actual";
union actual, latest | order by event_time asc
"""


def _model_version(result):
    return "kronos-base@demo" if result["stats"]["engine"] == "kronos" else "baseline@demo"


def _sampling(result):
    return result["config"].get("sampling") or {"T": 1.0, "top_p": 0.9, "top_k": 0, "sample_count": 1}


def _batches(text):
    """Split an emitter's multi-batch output into individual, runnable commands."""
    for block in text.split("\n\n"):
        block = block.strip()
        if block and not block.startswith("//"):
            yield block


def iter_commands(result, include_ticks=True):
    """Yield ordered (stage, kql_command) pairs for programmatic execution.

    Each yielded command is a single control command safe to pass to
    KustoClient.execute_mgmt — in the correct order (tables, ticks, then the
    candles_1m materialized view with backfill, then forecasts/signals/alerts).
    """
    symbol = result["meta"]["symbol"]
    mv = _model_version(result)
    sampling = _sampling(result)

    for line in _SETUP.splitlines():
        if line.strip().startswith(".create-merge"):
            yield ("setup", line.strip())

    if include_ticks and result.get("ticks"):
        for b in _batches(emit_ticks(result["ticks"])):
            yield ("ticks", b)

    mv_cmd = "\n".join(l for l in _MV.splitlines() if not l.strip().startswith("//")).strip()
    yield ("candles_view", mv_cmd)

    for b in _batches(emit_forecasts(result["runs"], symbol, mv, sampling)):
        yield ("forecasts", b)
    for b in _batches(emit_signals(result["signals"], symbol, mv)):
        yield ("signals", b)
    for b in _batches(emit_alerts(result["drift"], symbol, result["drift"]["band"])):
        yield ("model_health_alerts", b)


def verify_queries(symbol):
    """Read-only queries to confirm the round-trip landed (run with execute)."""
    return [
        ("ticks_raw", "ticks_raw | summarize rows=count(), first=min(event_time), last=max(event_time)"),
        ("candles_1m", "materialized_view('candles_1m') | summarize candles=count() by symbol"),
        ("forecasts", "forecasts | summarize rows=count(), runs=dcount(run_id)"),
        ("signals", "signals | summarize rows=count(), hits=countif(hit)"),
        ("model_health_alerts",
         "model_health_alerts | summarize rows=count(), first_alert=min(alert_time)"),
    ]


# ---- bundle -----------------------------------------------------------------
def write_kql_bundle(result, outdir, emit_ticks_data=True, tick_batch=1000):
    """Write the full KQL replay bundle; return {filename: row_count/bytes} meta."""
    kql_dir = os.path.join(outdir, "kql")
    os.makedirs(kql_dir, exist_ok=True)

    meta = result["meta"]
    stats = result["stats"]
    symbol = meta["symbol"]
    model_version = "kronos-base@demo" if stats["engine"] == "kronos" else "baseline@demo"
    sampling = result["config"].get("sampling") or {"T": 1.0, "top_p": 0.9, "top_k": 0, "sample_count": 1}

    files = {}

    def _write(name, header, body):
        path = os.path.join(kql_dir, name)
        with open(path, "w") as f:
            f.write(f"// {header}\n// Generated by deploy/azure/demo — Kronos on Fabric RTI\n\n{body}\n")
        files[name] = os.path.getsize(path)
        return path

    _write("00_setup.kql", "Stage 0 — create demo tables", _SETUP)
    if emit_ticks_data and result.get("ticks"):
        _write("10_replay_ticks.kql", "Stage 1 — replay raw ticks into ticks_raw",
               emit_ticks(result["ticks"], tick_batch))
    _write("15_candles_view.kql", "Stage 2 — materialized view builds candles_1m", _MV)
    _write("20_forecasts.kql", "Stage 3-4 — Kronos forecasts",
           emit_forecasts(result["runs"], symbol, model_version, sampling))
    _write("30_signals.kql", "Stage 6a — momentum signals",
           emit_signals(result["signals"], symbol, model_version))
    _write("40_model_health_alerts.kql", "Stage 6b — model-health alerts",
           emit_alerts(result["drift"], symbol, result["drift"]["band"]))
    _write("90_verify.kql", "Verify the round-trip + dashboard query",
           emit_verify(symbol, stats))

    # One-shot combined script (skips the heavy tick replay by default note).
    order = ["00_setup.kql", "10_replay_ticks.kql", "15_candles_view.kql",
             "20_forecasts.kql", "30_signals.kql", "40_model_health_alerts.kql", "90_verify.kql"]
    combined = []
    for name in order:
        p = os.path.join(kql_dir, name)
        if os.path.exists(p):
            with open(p) as f:
                combined.append(f.read())
    with open(os.path.join(kql_dir, "replay_all.kql"), "w") as f:
        f.write("\n\n// " + "=" * 74 + "\n\n".join(combined))
    files["replay_all.kql"] = os.path.getsize(os.path.join(kql_dir, "replay_all.kql"))

    return {"dir": kql_dir, "files": files, "model_version": model_version}
