"""
Self-contained HTML report for the Kronos-on-Fabric demo.

Renders the end-to-end story as a single, dependency-free, theme-aware page:
hero metrics, the trading-day narrative, an interactive price+forecast chart,
the model-health guardrail chart, the signal panel, and the Azure/Fabric value
chain. No external assets (CSP-safe): all CSS/JS/SVG inline.
"""
from __future__ import annotations

import json
from datetime import datetime


# ---- small helpers ----------------------------------------------------------
def _dt(iso):
    return datetime.fromisoformat(iso)


def _min_index(iso, start):
    return (_dt(iso) - start).total_seconds() / 60.0


def _fmt_price(v):
    return f"{v:,.0f}"


def _hhmm(iso):
    return _dt(iso).strftime("%H:%M")


# ---- overlay + geometry selection ------------------------------------------
def _select_overlays(result):
    runs = result["runs"]
    shock_idx = result["meta"]["shock_index"]
    pred_len = result["config"]["pred_len"]

    pre = [r for r in runs if r["origin_index"] + pred_len <= shock_idx and r["mape"] is not None]
    in_regime = min(pre, key=lambda r: r["mape"]) if pre else None

    crossing_cands = [r for r in runs if r["origin_index"] <= shock_idx - 3]
    crossing = max(crossing_cands, key=lambda r: r["origin_index"]) if crossing_cands else None
    return in_regime, crossing


# ---- SVG plumbing -----------------------------------------------------------
class Plot:
    def __init__(self, w, h, padl, padr, padt, padb, n, ymin, ymax):
        self.w, self.h = w, h
        self.padl, self.padr, self.padt, self.padb = padl, padr, padt, padb
        self.n, self.ymin, self.ymax = n, ymin, ymax

    def x(self, idx):
        return self.padl + (idx / max(1, self.n - 1)) * (self.w - self.padl - self.padr)

    def y(self, v):
        t = (v - self.ymin) / (self.ymax - self.ymin or 1)
        return self.padt + (1 - t) * (self.h - self.padt - self.padb)

    def poly(self, pts):
        return " ".join(f"{self.x(i):.1f},{self.y(v):.1f}" for i, v in pts)


def _price_chart(result, in_regime, crossing):
    candles = result["candles"]
    start = _dt(result["meta"]["session_start"])
    shock_idx = result["meta"]["shock_index"]
    pred_len = result["config"]["pred_len"]
    closes = [c["close"] for c in candles]
    n = len(closes)
    lo, hi = min(closes), max(closes)
    pad = (hi - lo) * 0.08
    P = Plot(1000, 430, 64, 20, 24, 46, n, lo - pad, hi + pad)

    def series_pts(run):
        return [(run["origin_index"] + k, f["close"]) for k, f in enumerate(run["forecast"])]

    # gridlines (price) + hour ticks
    grid, ylabels = [], []
    for g in range(5):
        val = (lo - pad) + (g / 4) * ((hi + pad) - (lo - pad))
        yy = P.y(val)
        grid.append(f'<line x1="{P.padl}" y1="{yy:.1f}" x2="{P.w-P.padr}" y2="{yy:.1f}" class="grid"/>')
        ylabels.append(f'<text x="{P.padl-8}" y="{yy+3:.1f}" class="ytick">{_fmt_price(val)}</text>')
    xticks = []
    for idx in range(0, n, 60):
        xx = P.x(idx)
        xticks.append(f'<line x1="{xx:.1f}" y1="{P.padt}" x2="{xx:.1f}" y2="{P.h-P.padb}" class="grid faint"/>')
        xticks.append(f'<text x="{xx:.1f}" y="{P.h-P.padb+18:.1f}" class="xtick">'
                      f'{(start.hour + idx//60)%24:02d}:00</text>')

    # shock band
    sx0, sx1 = P.x(shock_idx), P.x(shock_idx + 15)
    shock = (f'<rect x="{sx0:.1f}" y="{P.padt}" width="{sx1-sx0:.1f}" height="{P.h-P.padt-P.padb}" '
             f'class="shock-band"/>'
             f'<text x="{sx0+4:.1f}" y="{P.padt+14}" class="band-label">news shock '
             f'{_hhmm(candles[shock_idx]["event_time"])}</text>')

    # actual close line
    actual = f'<polyline points="{P.poly(list(enumerate(closes)))}" class="actual"/>'

    # divergence fill + shock-crossing forecast
    diverge, cross_line, cross_lbl = "", "", ""
    if crossing:
        cpts = series_pts(crossing)
        cpts = [(i, v) for i, v in cpts if i < n]
        actual_seg = [(i, closes[i]) for i, _ in cpts]
        area = ([f"{P.x(i):.1f},{P.y(v):.1f}" for i, v in cpts] +
                [f"{P.x(i):.1f},{P.y(closes[i]):.1f}" for i, _ in reversed(cpts)])
        diverge = f'<polygon points="{" ".join(area)}" class="diverge"/>'
        cross_line = f'<polyline points="{P.poly(cpts)}" class="forecast cross"/>'
        ex, ey = P.x(cpts[-1][0]), P.y(cpts[-1][1])
        cross_lbl = (f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="3.5" class="dot-cross"/>'
                     f'<text x="{ex-6:.1f}" y="{ey-8:.1f}" class="anno-cross">forecast held up — reality didn\'t</text>')

    # in-regime forecast overlay
    in_line, in_lbl = "", ""
    if in_regime:
        ipts = [(i, v) for i, v in series_pts(in_regime) if i < n]
        in_line = f'<polyline points="{P.poly(ipts)}" class="forecast good"/>'
        mx, my = P.x(ipts[len(ipts)//2][0]), P.y(max(v for _, v in ipts)) - 10
        in_lbl = f'<text x="{mx:.1f}" y="{my:.1f}" class="anno-good">in-regime forecast tracks</text>'

    # auto-detection marker
    alert = result["drift"]["first_alert_time"]
    amark = ""
    if alert:
        ax = P.x(_min_index(alert, start))
        amark = (f'<line x1="{ax:.1f}" y1="{P.padt}" x2="{ax:.1f}" y2="{P.h-P.padb}" class="alert-line"/>'
                 f'<text x="{ax+5:.1f}" y="{P.padt+30}" class="alert-anno">◆ guardrail auto-detect '
                 f'{_hhmm(alert)} (+{result["stats"]["detection_latency_min"]:.0f}m)</text>')

    hover_data = json.dumps({
        "closes": closes, "n": n,
        "startMs": int(start.timestamp() * 1000),
        "ymin": P.ymin, "ymax": P.ymax,
        "padl": P.padl, "padr": P.padr, "padt": P.padt, "padb": P.padb,
        "w": P.w, "h": P.h,
    })

    svg = f'''<svg viewBox="0 0 {P.w} {P.h}" class="chart" preserveAspectRatio="none" aria-hidden="true">
      {''.join(xticks)}{''.join(grid)}
      {shock}{diverge}{actual}{in_line}{cross_line}{in_lbl}{cross_lbl}{amark}
      {''.join(ylabels)}
    </svg>'''
    return svg, hover_data


def _guardrail_chart(result):
    series = result["drift"]["series"]
    start = _dt(result["meta"]["session_start"])
    band = result["drift"]["band"] * 100
    n = result["meta"]["n_candles"]
    xs = [(_min_index(s["eval_time"], start), s["mape"] * 100, s["smoothed"] * 100, s["alert"]) for s in series]
    ymax = max(band * 1.15, max(v[2] for v in xs) * 1.1)
    P = Plot(1000, 240, 64, 20, 20, 40, n, 0, ymax)

    grid = []
    for g in range(4):
        val = (g / 3) * ymax
        yy = P.y(val)
        grid.append(f'<line x1="{P.padl}" y1="{yy:.1f}" x2="{P.w-P.padr}" y2="{yy:.1f}" class="grid"/>')
        grid.append(f'<text x="{P.padl-8}" y="{yy+3:.1f}" class="ytick">{val:.1f}%</text>')

    raw = f'<polyline points="{" ".join(f"{P.x(i):.1f},{P.y(m):.1f}" for i,m,_,_ in xs)}" class="mape-raw"/>'
    smooth = f'<polyline points="{" ".join(f"{P.x(i):.1f},{P.y(s):.1f}" for i,_,s,_ in xs)}" class="mape-smooth"/>'
    by = P.y(band)
    bandline = (f'<line x1="{P.padl}" y1="{by:.1f}" x2="{P.w-P.padr}" y2="{by:.1f}" class="band-line"/>'
                f'<text x="{P.w-P.padr:.1f}" y="{by-6:.1f}" class="band-txt">alert band {band:.2f}%</text>')
    dots = "".join(f'<circle cx="{P.x(i):.1f}" cy="{P.y(s):.1f}" r="2.6" class="mape-alert"/>'
                   for i, _, s, a in xs if a)

    shock_idx = result["meta"]["shock_index"]
    sx = P.x(shock_idx)
    shock = f'<line x1="{sx:.1f}" y1="{P.padt}" x2="{sx:.1f}" y2="{P.h-P.padb}" class="alert-line"/>'
    return f'''<svg viewBox="0 0 {P.w} {P.h}" class="chart" preserveAspectRatio="none" aria-hidden="true">
      {''.join(grid)}{shock}{raw}{smooth}{bandline}{dots}
    </svg>'''


def _html_escape(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fabric_card(result, kql_meta):
    if not kql_meta:
        return ""
    order = ["00_setup.kql", "10_replay_ticks.kql", "15_candles_view.kql", "20_forecasts.kql",
             "30_signals.kql", "40_model_health_alerts.kql", "90_verify.kql", "replay_all.kql"]
    chips = "".join(
        f'<div class="kql-chip"><span class="mono kf">{name}</span>'
        f'<span class="mono ks">{kql_meta["files"][name]/1024:.1f} KB</span></div>'
        for name in order if name in kql_meta["files"])

    # A real 2-row snippet from the emitted forecasts.
    run = result["runs"][0]
    rid = f'{result["meta"]["symbol"]}-r{run["origin_index"]:05d}'
    samp = json.dumps(result["config"]["sampling"], separators=(",", ":"))
    lines = [".set-or-append forecasts <|",
             "datatable(symbol:string, run_id:string, run_time:datetime, target_time:datetime,",
             "          open:real, high:real, low:real, close:real, volume:real, amount:real,",
             "          horizon_step:int, model_version:string, sampling:dynamic)",
             "["]
    for f in run["forecast"][:2]:
        lines.append(
            f'  "{result["meta"]["symbol"]}","{rid}",datetime({_dt(run["origin_time"]).strftime("%Y-%m-%dT%H:%M:%SZ")}),'
            f'datetime({_dt(f["target_time"]).strftime("%Y-%m-%dT%H:%M:%SZ")}),'
            f'{f["open"]},{f["high"]},{f["low"]},{f["close"]},{f["volume"]},{f["amount"]},'
            f'{f["horizon_step"]},"{kql_meta["model_version"]}",dynamic({samp}),')
    lines.append("  ...")
    lines.append("]")
    snippet = _html_escape("\n".join(lines))

    return f'''<div class="card">
      <div class="card-head"><div><h2>Fabric-ready — the demo round-trips as KQL</h2>
        <p>Every stage is emitted as <code>.set-or-append</code> batches against the real Eventhouse
          schemas. Paste <code>replay_all.kql</code> into a Fabric KQL queryset and the
          <code>candles_1m</code> materialized view, <code>forecasts</code>, <code>signals</code> and
          <code>model_health_alerts</code> all rebuild — same tables the production pipeline writes.</p></div></div>
      <div class="kql-grid">{chips}</div>
      <pre class="kql-snip"><code>{snippet}</code></pre>
    </div>'''


# ---- page -------------------------------------------------------------------
def build_html(result, kql_meta=None) -> str:
    s = result["stats"]
    meta = result["meta"]
    in_regime, crossing = _select_overlays(result)
    price_svg, hover_data = _price_chart(result, in_regime, crossing)
    guard_svg = _guardrail_chart(result)

    engine_is_real = s["engine"] == "kronos"
    engine_badge = ("LIVE · Kronos model" if engine_is_real
                    else "OFFLINE · baseline forecaster")
    signals = result["signals"]
    n_hit = sum(1 for x in signals if x["hit"])

    def tile(label, value, sub, tone=""):
        return (f'<div class="tile {tone}"><div class="tile-label">{label}</div>'
                f'<div class="tile-value">{value}</div><div class="tile-sub">{sub}</div></div>')

    tiles = "".join([
        tile("Directional accuracy", f"{s['directional_accuracy']*100:.1f}%",
             f"30-min horizon · in-regime", "good"),
        tile("Signal hit-rate", f"{s['signal_hit_rate']*100:.1f}%",
             f"{s['n_signals']} momentum signals fired", "good"),
        tile("Median forecast error", f"{s['in_regime_median_mape']*100:.2f}%",
             "MAPE vs realized close", ""),
        tile("Shock detection", f"+{s['detection_latency_min']:.0f} min",
             "auto-flagged after news shock", "warn"),
    ])

    # a few illustrative pre-shock signals
    pre_signals = [x for x in signals if _dt(x["origin_time"]) < _dt(meta["shock_time"])][-6:]
    sig_rows = "".join(
        f'<tr><td class="mono">{_hhmm(x["origin_time"])}</td>'
        f'<td><span class="pill {"up" if x["direction"]=="UP" else "down"}">{x["direction"]}</span></td>'
        f'<td class="mono num">{x["expected_move_pct"]*100:+.2f}%</td>'
        f'<td class="mono num">{x["realized_move_pct"]*100:+.2f}%</td>'
        f'<td>{"✓ hit" if x["hit"] else "· miss"}</td></tr>'
        for x in pre_signals)

    chain = "".join(
        f'<div class="stage"><div class="stage-n mono">{i+1}</div>'
        f'<div class="stage-b"><div class="stage-t">{t}</div>'
        f'<div class="stage-c mono">{c}</div></div></div>'
        + ('<div class="stage-arrow">→</div>' if i < 5 else '')
        for i, (t, c) in enumerate([
            ("Ingest", "Event Hubs · Eventstream"),
            ("Candles", "Eventhouse materialized view"),
            ("Forecast", "Fabric NB → Azure ML (Kronos)"),
            ("Store", "Eventhouse · forecasts"),
            ("Visualize", "Real-Time Dashboard"),
            ("Act", "Data Activator alerts"),
        ]))

    shock_h = _hhmm(meta["shock_time"])
    return _TEMPLATE.format(
        fabric_card=_fabric_card(result, kql_meta),
        engine_cls=("live" if engine_is_real else "warn"),
        engine_badge=engine_badge, engine_label=s["engine_label"],
        symbol=s["symbol"], n_ticks=f"{s['n_ticks']:,}", n_candles=f"{s['n_candles']:,}",
        tiles=tiles, price_svg=price_svg, guard_svg=guard_svg, sig_rows=sig_rows,
        n_signals=s["n_signals"], n_hit=n_hit, chain=chain,
        shock_h=shock_h, latency=f"{s['detection_latency_min']:.0f}",
        dir_acc=f"{s['directional_accuracy']*100:.1f}",
        band=f"{s['drift_band']*100:.2f}", base_mape=f"{s['baseline_mape']*100:.2f}",
        lookback=s["lookback"], pred_len=s["pred_len"],
        hover_data=hover_data,
    )


_TEMPLATE = r"""<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Kronos on Microsoft Fabric — Real-Time Intelligence demo</title>
<style>
:root {{
  --bg:#F4F5F7; --surface:#FFFFFF; --surface-2:#FAFBFC;
  --ink:#161B26; --ink-2:#55607A; --ink-3:#8A93A8; --hair:#E4E7ED;
  --accent:#2E7FD6; --accent-soft:#2E7FD622;
  --good:#1F9D63; --warn:#C77A15; --crit:#CC392E; --crit-soft:#CC392E1f;
  --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg:#0C111C; --surface:#141B2A; --surface-2:#101725;
    --ink:#E8ECF4; --ink-2:#9BA6BD; --ink-3:#616C85; --hair:#232C3E;
    --accent:#4C9EEA; --accent-soft:#4C9EEA2b;
    --good:#34B87C; --warn:#E0A040; --crit:#E85D51; --crit-soft:#E85D5122;
  }}
}}
:root[data-theme="light"] {{
  --bg:#F4F5F7; --surface:#FFFFFF; --surface-2:#FAFBFC;
  --ink:#161B26; --ink-2:#55607A; --ink-3:#8A93A8; --hair:#E4E7ED;
  --accent:#2E7FD6; --accent-soft:#2E7FD622;
  --good:#1F9D63; --warn:#C77A15; --crit:#CC392E; --crit-soft:#CC392E1f;
}}
:root[data-theme="dark"] {{
  --bg:#0C111C; --surface:#141B2A; --surface-2:#101725;
  --ink:#E8ECF4; --ink-2:#9BA6BD; --ink-3:#616C85; --hair:#232C3E;
  --accent:#4C9EEA; --accent-soft:#4C9EEA2b;
  --good:#34B87C; --warn:#E0A040; --crit:#E85D51; --crit-soft:#E85D5122;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font-family:var(--sans);
  line-height:1.55; -webkit-font-smoothing:antialiased; }}
.wrap {{ max-width:1120px; margin:0 auto; padding:40px 24px 72px; }}
.eyebrow {{ font-family:var(--mono); font-size:12px; letter-spacing:.16em; text-transform:uppercase;
  color:var(--ink-3); }}
h1 {{ font-size:clamp(28px,4vw,44px); line-height:1.08; margin:.3em 0 .2em; text-wrap:balance;
  letter-spacing:-.02em; }}
h2 {{ font-size:20px; letter-spacing:-.01em; margin:0 0 4px; }}
.dek {{ color:var(--ink-2); font-size:17px; max-width:64ch; }}
.badges {{ display:flex; gap:10px; flex-wrap:wrap; margin:18px 0 4px; align-items:center; }}
.badge {{ font-family:var(--mono); font-size:12px; padding:5px 10px; border-radius:6px;
  border:1px solid var(--hair); color:var(--ink-2); background:var(--surface); }}
.badge.live {{ color:var(--good); border-color:color-mix(in srgb,var(--good) 45%,var(--hair)); }}
.badge.warn {{ color:var(--warn); border-color:color-mix(in srgb,var(--warn) 45%,var(--hair)); }}
.hr {{ height:1px; background:var(--hair); border:0; margin:32px 0; }}

.tiles {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-top:22px; }}
.tile {{ background:var(--surface); border:1px solid var(--hair); border-radius:12px; padding:16px 16px 14px;
  position:relative; overflow:hidden; }}
.tile::before {{ content:""; position:absolute; left:0; top:0; bottom:0; width:3px; background:var(--ink-3); }}
.tile.good::before {{ background:var(--good); }} .tile.warn::before {{ background:var(--warn); }}
.tile-label {{ font-family:var(--mono); font-size:11px; letter-spacing:.08em; text-transform:uppercase;
  color:var(--ink-3); }}
.tile-value {{ font-family:var(--mono); font-size:30px; font-weight:600; margin:6px 0 2px;
  font-variant-numeric:tabular-nums; letter-spacing:-.01em; }}
.tile.good .tile-value {{ color:var(--good); }} .tile.warn .tile-value {{ color:var(--warn); }}
.tile-sub {{ font-size:12.5px; color:var(--ink-2); }}

.card {{ background:var(--surface); border:1px solid var(--hair); border-radius:14px; padding:22px 22px 18px;
  margin-top:22px; }}
.card-head {{ display:flex; justify-content:space-between; align-items:baseline; gap:12px; flex-wrap:wrap;
  margin-bottom:14px; }}
.card-head p {{ margin:2px 0 0; color:var(--ink-2); font-size:14px; max-width:70ch; }}
.legend {{ display:flex; gap:16px; flex-wrap:wrap; font-size:12.5px; color:var(--ink-2);
  font-family:var(--mono); }}
.legend span {{ display:inline-flex; align-items:center; gap:6px; }}
.sw {{ width:16px; height:0; border-top-width:3px; border-top-style:solid; display:inline-block; }}
.sw.actual {{ border-color:var(--ink); }} .sw.fc {{ border-color:var(--accent); border-top-style:dashed; }}
.sw.div {{ height:11px; border:0; width:14px; background:var(--crit-soft);
  border-left:2px solid var(--crit); border-radius:2px; }}

.chart-wrap {{ position:relative; width:100%; }}
.chart {{ width:100%; height:auto; display:block; touch-action:none; }}
.grid {{ stroke:var(--hair); stroke-width:1; }} .grid.faint {{ stroke:var(--hair); opacity:.5; }}
.ytick,.xtick {{ fill:var(--ink-3); font-family:var(--mono); font-size:11px; }}
.ytick {{ text-anchor:end; }} .xtick {{ text-anchor:middle; }}
.actual {{ fill:none; stroke:var(--ink); stroke-width:1.8; }}
.forecast {{ fill:none; stroke:var(--accent); stroke-width:2; stroke-dasharray:4 3; }}
.forecast.good {{ opacity:.95; }}
.diverge {{ fill:var(--crit-soft); stroke:none; }}
.dot-cross {{ fill:var(--crit); }}
.shock-band {{ fill:var(--warn); opacity:.10; }}
.band-label {{ fill:var(--warn); font-family:var(--mono); font-size:11px; }}
.anno-good {{ fill:var(--accent); font-family:var(--mono); font-size:11px; text-anchor:middle; }}
.anno-cross {{ fill:var(--crit); font-family:var(--mono); font-size:11px; text-anchor:end; }}
.alert-line {{ stroke:var(--crit); stroke-width:1.4; stroke-dasharray:3 3; }}
.alert-anno {{ fill:var(--crit); font-family:var(--mono); font-size:11.5px; font-weight:600; }}
.mape-raw {{ fill:none; stroke:var(--ink-3); stroke-width:1; opacity:.55; }}
.mape-smooth {{ fill:none; stroke:var(--accent); stroke-width:2.2; }}
.mape-alert {{ fill:var(--crit); }}
.band-line {{ stroke:var(--warn); stroke-width:1.4; stroke-dasharray:5 3; }}
.band-txt {{ fill:var(--warn); font-family:var(--mono); font-size:11px; text-anchor:end; }}

.cross-line {{ position:absolute; top:0; width:1px; background:var(--accent); opacity:.6; pointer-events:none;
  display:none; }}
.cross-dot {{ position:absolute; width:9px; height:9px; margin:-4.5px 0 0 -4.5px; border-radius:50%;
  background:var(--accent); box-shadow:0 0 0 3px var(--accent-soft); pointer-events:none; display:none; }}
.tip {{ position:absolute; pointer-events:none; background:var(--surface); border:1px solid var(--hair);
  border-radius:8px; padding:7px 9px; font-family:var(--mono); font-size:12px; color:var(--ink);
  box-shadow:0 6px 20px rgba(0,0,0,.14); display:none; white-space:nowrap; transform:translate(-50%,-120%);
  z-index:5; }}
.tip b {{ color:var(--accent); }}

.story {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }}
.act {{ border-left:2px solid var(--hair); padding:2px 0 2px 16px; }}
.act h3 {{ font-family:var(--mono); font-size:12px; letter-spacing:.08em; text-transform:uppercase;
  color:var(--ink-3); margin:0 0 6px; }}
.act p {{ margin:0; font-size:14.5px; color:var(--ink-2); }}
.act.a1 {{ border-color:var(--good); }} .act.a2 {{ border-color:var(--warn); }}
.act.a3 {{ border-color:var(--crit); }}
.act b {{ color:var(--ink); }}

table {{ width:100%; border-collapse:collapse; font-size:13.5px; }}
th {{ text-align:left; font-family:var(--mono); font-size:11px; letter-spacing:.06em; text-transform:uppercase;
  color:var(--ink-3); font-weight:500; padding:6px 10px; border-bottom:1px solid var(--hair); }}
td {{ padding:7px 10px; border-bottom:1px solid var(--hair); }}
.mono {{ font-family:var(--mono); }} .num {{ text-align:right; font-variant-numeric:tabular-nums; }}
.pill {{ font-family:var(--mono); font-size:11px; padding:2px 7px; border-radius:5px; }}
.pill.up {{ color:var(--good); background:color-mix(in srgb,var(--good) 14%,transparent); }}
.pill.down {{ color:var(--crit); background:var(--crit-soft); }}

.chain {{ display:flex; align-items:stretch; gap:8px; flex-wrap:wrap; }}
.stage {{ display:flex; gap:10px; align-items:center; background:var(--surface-2); border:1px solid var(--hair);
  border-radius:10px; padding:10px 12px; flex:1 1 150px; }}
.stage-n {{ width:22px; height:22px; border-radius:6px; background:var(--accent); color:#fff;
  display:flex; align-items:center; justify-content:center; font-size:12px; flex:none; }}
.stage-t {{ font-size:13.5px; font-weight:600; }}
.stage-c {{ font-size:11px; color:var(--ink-3); }}
.stage-arrow {{ display:flex; align-items:center; color:var(--ink-3); font-size:15px; }}
@media (max-width:900px) {{ .stage-arrow {{ display:none; }} }}

.kql-grid {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:16px; }}
.kql-chip {{ display:flex; align-items:center; gap:8px; background:var(--surface-2);
  border:1px solid var(--hair); border-radius:8px; padding:7px 11px; }}
.kql-chip .kf {{ font-size:12.5px; color:var(--ink); }}
.kql-chip .ks {{ font-size:11px; color:var(--ink-3); }}
.kql-snip {{ margin:0; background:var(--surface-2); border:1px solid var(--hair); border-radius:10px;
  padding:14px 16px; overflow-x:auto; font-family:var(--mono); font-size:12px; line-height:1.5;
  color:var(--ink-2); }}
.kql-snip code {{ white-space:pre; }}

.foot {{ margin-top:30px; color:var(--ink-3); font-size:13px; }}
.foot code {{ font-family:var(--mono); background:var(--surface-2); padding:2px 6px; border-radius:5px;
  border:1px solid var(--hair); color:var(--ink-2); }}
@media (max-width:820px) {{ .tiles{{grid-template-columns:repeat(2,1fr);}} .story{{grid-template-columns:1fr;}} }}
</style>

<div class="wrap">
  <div class="eyebrow">Kronos × Microsoft Fabric · Real-Time Intelligence</div>
  <h1>From a live market feed to acted-on forecasts — in one streaming loop</h1>
  <p class="dek">A synthetic {symbol} trading session runs the full reference architecture end-to-end:
    ticks become OHLCV candles, Kronos forecasts the next {pred_len} minutes on every candle, and
    Data&nbsp;Activator turns those forecasts into signals — and into an automatic model-health alarm
    when reality breaks from the model.</p>
  <div class="badges">
    <span class="badge {engine_cls}">{engine_badge}</span>
    <span class="badge">{engine_label}</span>
    <span class="badge">{n_ticks} ticks → {n_candles} candles</span>
    <span class="badge">lookback {lookback} · horizon {pred_len}m</span>
  </div>

  <div class="tiles">{tiles}</div>

  <hr class="hr"/>
  <h2>The trading day, in three acts</h2>
  <div class="story" style="margin-top:14px">
    <div class="act a1"><h3>Act I · the rally</h3><p>Through the morning, momentum in the tape is real.
      Kronos calls direction correctly <b>{dir_acc}% of the time</b> over a 30-minute horizon, and the
      pipeline fires <b>{n_signals} momentum signals</b> — most of them right.</p></div>
    <div class="act a2"><h3>Act II · the shock</h3><p>At <b>{shock_h}</b> an unscheduled news shock knocks
      the market down ~3% in minutes. No model can forecast the jump itself — the forecast keeps projecting
      the prior trend while price dives.</p></div>
    <div class="act a3"><h3>Act III · the guardrail</h3><p>Forecast error spikes. The Data&nbsp;Activator rule
      watching realized-vs-forecast error breaches its learned band and <b>auto-fires within
      {latency} minutes</b> — a regime break flagged before a human would notice.</p></div>
  </div>

  <div class="card">
    <div class="card-head">
      <div><h2>Price &amp; forecast — {symbol}</h2>
        <p>Actual close vs Kronos forecasts. The in-regime forecast tracks; the one issued just before the
          shock (red divergence) shows exactly what the guardrail is built to catch.</p></div>
      <div class="legend">
        <span><i class="sw actual"></i>actual close</span>
        <span><i class="sw fc"></i>Kronos forecast</span>
        <span><i class="sw div"></i>forecast error</span>
      </div>
    </div>
    <div class="chart-wrap" id="pw">
      {price_svg}
      <div class="cross-line" id="cl"></div><div class="cross-dot" id="cd"></div>
      <div class="tip" id="tip"></div>
    </div>
  </div>

  <div class="card">
    <div class="card-head">
      <div><h2>Model-health guardrail — forecast error vs alert band</h2>
        <p>Rolling forecast error (smoothed). The band is learned from the calm regime; the shock (dashed) pushes
          error far past it, and the sustained breach is the auto-detection. Error recovers as Kronos re-anchors
          to the new price level. Baseline error {base_mape}% · band {band}%.</p></div>
      <div class="legend">
        <span><i class="sw" style="border-color:var(--accent)"></i>smoothed error</span>
        <span><i class="sw" style="border-color:var(--warn);border-top-style:dashed"></i>alert band</span>
        <span style="color:var(--crit)">● breach</span>
      </div>
    </div>
    <div class="chart-wrap">{guard_svg}</div>
  </div>

  <div class="card">
    <div class="card-head"><div><h2>Momentum signals before the shock</h2>
      <p>Data Activator SignalLargeMove — sample of high-conviction calls from the rally.
        Overall {n_hit} of {n_signals} signals hit.</p></div></div>
    <table><thead><tr><th>Time</th><th>Call</th><th class="num">Expected</th>
      <th class="num">Realized</th><th>Result</th></tr></thead><tbody>{sig_rows}</tbody></table>
  </div>

  <div class="card">
    <div class="card-head"><div><h2>The value chain</h2>
      <p>Every stage above maps to a managed Azure / Fabric component — Fabric owns data, time and action;
        Azure ML owns the model.</p></div></div>
    <div class="chain">{chain}</div>
  </div>

  {fabric_card}

  <p class="foot">Runs fully offline on the Python standard library — the forecaster shown is a transparent
    baseline with the same interface as the model endpoint. Set <code>KRONOS_ENABLE=1</code> (with torch +
    weights) to swap in the real Kronos foundation model; nothing else changes. Reproduce with
    <code>python deploy/azure/demo/run_demo.py</code>.</p>
</div>

<script>
(function() {{
  var D = {hover_data};
  var wrap = document.getElementById('pw'), cl = document.getElementById('cl'),
      cd = document.getElementById('cd'), tip = document.getElementById('tip');
  if (!wrap) return;
  function fmt(v) {{ return v.toLocaleString(undefined, {{maximumFractionDigits:0}}); }}
  function move(ev) {{
    var r = wrap.getBoundingClientRect();
    var cx = (ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left;
    var fx = cx / r.width;
    var L = D.padl / D.w, R = (D.w - D.padr) / D.w;
    var t = (fx - L) / (R - L);
    if (t < 0 || t > 1) {{ hide(); return; }}
    var idx = Math.round(t * (D.n - 1));
    var price = D.closes[idx];
    var px = (D.padl + (idx/(D.n-1))*(D.w-D.padl-D.padr)) / D.w * r.width;
    var yfrac = (price - D.ymin) / (D.ymax - D.ymin);
    var sy = D.padt + (1 - yfrac) * (D.h - D.padt - D.padb);
    var py = sy / D.h * r.height;
    cl.style.display = cd.style.display = tip.style.display = 'block';
    cl.style.left = px + 'px'; cl.style.height = r.height + 'px';
    cd.style.left = px + 'px'; cd.style.top = py + 'px';
    var ts = new Date(D.startMs + idx*60000);
    var hh = ('0'+ts.getUTCHours()).slice(-2), mm = ('0'+ts.getUTCMinutes()).slice(-2);
    tip.innerHTML = hh+':'+mm+' &nbsp; <b>'+fmt(price)+'</b>';
    tip.style.left = px + 'px'; tip.style.top = py + 'px';
  }}
  function hide() {{ cl.style.display = cd.style.display = tip.style.display = 'none'; }}
  wrap.addEventListener('mousemove', move);
  wrap.addEventListener('touchmove', move);
  wrap.addEventListener('mouseleave', hide);
}})();
</script>
"""
