"""
Build the single continuous solution deck: 3 intro slides + the demo charts.

Reuses the demo's own chart builders (report.py) so the slides show the exact
same price/forecast and model-health visuals as the report, then adds the signal
and Fabric-round-trip slides. Output is one self-contained HTML deck that works
both on screen (keyboard/click navigation) and in print (each slide → one
1280×720 page), so it exports cleanly to PDF via headless Chromium.

    python deploy/azure/demo/build_deck.py --out output
    # then render PDF:
    /opt/pw-browsers/chromium --headless --print-to-pdf=output/solution-deck.pdf \
        --no-pdf-header-footer file://$PWD/output/solution-deck.html
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
from kql_emit import write_kql_bundle
import report as R


def _signal_rows(result):
    meta = result["meta"]
    pre = [x for x in result["signals"] if R._dt(x["origin_time"]) < R._dt(meta["shock_time"])][-7:]
    return "".join(
        f'<tr><td class="mono">{R._hhmm(x["origin_time"])}</td>'
        f'<td><span class="pill {"up" if x["direction"]=="UP" else "down"}">{x["direction"]}</span></td>'
        f'<td class="mono num">{x["expected_move_pct"]*100:+.2f}%</td>'
        f'<td class="mono num">{x["realized_move_pct"]*100:+.2f}%</td>'
        f'<td>{"&#10003; hit" if x["hit"] else "&middot; miss"}</td></tr>'
        for x in pre)


def _kql_snippet(result, model_version):
    run = result["runs"][0]
    rid = f'{result["meta"]["symbol"]}-r{run["origin_index"]:05d}'
    samp = json.dumps(result["config"]["sampling"], separators=(",", ":"))
    lines = [".set-or-append forecasts &lt;|",
             "datatable(symbol:string, run_id:string, run_time:datetime, target_time:datetime,",
             "          open:real, high:real, low:real, close:real, ..., sampling:dynamic)",
             "["]
    for f in run["forecast"][:2]:
        lines.append(
            f'  "{result["meta"]["symbol"]}","{rid}",datetime(...),'
            f'{f["open"]},{f["high"]},{f["low"]},{f["close"]},{f["horizon_step"]},'
            f'"{model_version}",dynamic({samp}),')
    lines += ["  ...", "]"]
    return "\n".join(lines)


def build_deck(result, kql_meta):
    s = result["stats"]
    meta = result["meta"]
    in_regime, crossing = R._select_overlays(result)
    price_svg, _ = R._price_chart(result, in_regime, crossing)
    guard_svg = R._guardrail_chart(result)
    shock_h = R._hhmm(meta["shock_time"])
    model_version = kql_meta["model_version"] if kql_meta else "baseline@demo"

    kql_order = ["00_setup.kql", "10_replay_ticks.kql", "15_candles_view.kql", "20_forecasts.kql",
                 "30_signals.kql", "40_model_health_alerts.kql", "90_verify.kql", "replay_all.kql"]
    kql_chips = "".join(
        f'<span class="kqf mono">{n}</span>'
        for n in kql_order if kql_meta and n in kql_meta["files"])

    return _DECK.format(
        symbol=s["symbol"], n_ticks=f"{s['n_ticks']:,}", n_candles=f"{s['n_candles']:,}",
        n_forecasts=s["n_forecasts"], lookback=s["lookback"], pred_len=s["pred_len"],
        dir_acc=f"{s['directional_accuracy']*100:.1f}", med_mape=f"{s['in_regime_median_mape']*100:.2f}",
        n_signals=s["n_signals"], hit_rate=f"{s['signal_hit_rate']*100:.1f}",
        latency=f"{s['detection_latency_min']:.0f}", band=f"{s['drift_band']*100:.2f}",
        base_mape=f"{s['baseline_mape']*100:.2f}", shock_h=shock_h,
        price_svg=price_svg, guard_svg=guard_svg, sig_rows=_signal_rows(result),
        kql_chips=kql_chips, kql_snippet=_kql_snippet(result, model_version),
        engine_label=s["engine_label"],
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "output"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    candles, meta, ticks = generate_session(return_ticks=True)
    result = run_pipeline(candles, meta, KronosAdapter())
    result["ticks"] = ticks
    kql_meta = write_kql_bundle(result, args.out, emit_ticks_data=True)

    html = build_deck(result, kql_meta)
    path = os.path.join(args.out, "solution-deck.html")
    with open(path, "w") as f:
        f.write(html)
    print("wrote", path)
    return path


# ---------------------------------------------------------------------------
_DECK = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Kronos on Microsoft Fabric — Solution Deck</title>
<style>
:root{{
  --bg:#F4F5F7; --panel:#FFFFFF; --panel-2:#FAFBFC;
  --ink:#141A26; --ink-2:#54607A; --ink-3:#8A93A8; --hair:#E4E7ED;
  --accent:#2E7FD6; --accent-soft:#2E7FD622; --glow:#2E7FD61f;
  --good:#1F9D63; --warn:#C77A15; --crit:#CC392E; --crit-soft:#CC392E1f;
  --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
}}
@media (prefers-color-scheme:dark){{:root{{
  --bg:#0B111C; --panel:#131A28; --panel-2:#0F1623;
  --ink:#EAEEF6; --ink-2:#9DA8BE; --ink-3:#5F6A83; --hair:#222B3C;
  --accent:#59A6F0; --accent-soft:#59A6F02b; --glow:#59A6F033;
  --good:#37C08A; --warn:#E0A040; --crit:#E85D51; --crit-soft:#E85D5122;
}}}}
:root[data-theme="light"]{{ --bg:#F4F5F7; --panel:#FFFFFF; --panel-2:#FAFBFC;
  --ink:#141A26; --ink-2:#54607A; --ink-3:#8A93A8; --hair:#E4E7ED;
  --accent:#2E7FD6; --accent-soft:#2E7FD622; --glow:#2E7FD61f;
  --good:#1F9D63; --warn:#C77A15; --crit:#CC392E; --crit-soft:#CC392E1f; }}
:root[data-theme="dark"]{{ --bg:#0B111C; --panel:#131A28; --panel-2:#0F1623;
  --ink:#EAEEF6; --ink-2:#9DA8BE; --ink-3:#5F6A83; --hair:#222B3C;
  --accent:#59A6F0; --accent-soft:#59A6F02b; --glow:#59A6F033;
  --good:#37C08A; --warn:#E0A040; --crit:#E85D51; --crit-soft:#E85D5122; }}
*{{box-sizing:border-box;}}
html,body{{margin:0;height:100%;}}
body{{background:var(--bg);color:var(--ink);font-family:var(--sans);overflow:hidden;
  -webkit-font-smoothing:antialiased;}}
.deck{{position:fixed;inset:0;}}
.slide{{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;
  padding:clamp(30px,5vw,80px);opacity:0;visibility:hidden;pointer-events:none;
  transition:opacity .45s ease;overflow:auto;}}
.slide.active{{opacity:1;visibility:visible;pointer-events:auto;}}
@media (prefers-reduced-motion:reduce){{.slide{{transition:none;}}}}
.stage{{max-width:1140px;width:100%;margin:0 auto;}}
.eyebrow{{font-family:var(--mono);font-size:clamp(11px,1.1vw,13px);letter-spacing:.2em;
  text-transform:uppercase;color:var(--ink-3);}}
.eyebrow b{{color:var(--accent);font-weight:600;}}
h1{{font-size:clamp(32px,5.6vw,70px);line-height:1.03;letter-spacing:-.025em;margin:.28em 0 .3em;
  text-wrap:balance;font-weight:650;}}
h2{{font-size:clamp(24px,3.8vw,44px);line-height:1.06;letter-spacing:-.02em;margin:.1em 0 .45em;
  text-wrap:balance;font-weight:650;}}
.lead{{font-size:clamp(15px,1.7vw,21px);line-height:1.5;color:var(--ink-2);max-width:60ch;}}
.u{{color:var(--ink);font-weight:600;}} .accent{{color:var(--accent);}}
.rise{{opacity:0;transform:translateY(12px);transition:opacity .5s ease,transform .5s ease;}}
.slide.active .rise{{opacity:1;transform:none;}}
.slide.active .d1{{transition-delay:.08s;}} .slide.active .d2{{transition-delay:.16s;}}
.slide.active .d3{{transition-delay:.24s;}} .slide.active .d4{{transition-delay:.32s;}}
@media (prefers-reduced-motion:reduce){{.rise{{opacity:1;transform:none;transition:none;}}}}

.s1 .stage{{display:grid;grid-template-columns:1.15fr .85fr;gap:44px;align-items:center;}}
@media (max-width:860px){{.s1 .stage{{grid-template-columns:1fr;}}}}
.chips{{display:flex;gap:10px;flex-wrap:wrap;margin-top:26px;}}
.chip{{font-family:var(--mono);font-size:13px;color:var(--ink-2);background:var(--panel);
  border:1px solid var(--hair);border-radius:8px;padding:8px 13px;}} .chip b{{color:var(--accent);}}
.klines{{width:100%;height:auto;filter:drop-shadow(0 22px 55px var(--glow));}}
.k-up{{fill:var(--good);stroke:var(--good);}} .k-dn{{fill:var(--crit);stroke:var(--crit);}}
.k-fc{{fill:none;stroke:var(--accent);}} .k-dot{{fill:var(--accent);}}
.k-lbl{{fill:var(--accent);font-family:var(--mono);font-size:11px;}}

.lane-label{{font-family:var(--mono);font-size:12px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--ink-3);margin-bottom:10px;display:flex;align-items:center;gap:9px;flex-wrap:wrap;}}
.dot-l{{width:9px;height:9px;border-radius:3px;background:var(--accent);}} .dot-l.ml{{background:var(--good);}}
.flow{{display:flex;align-items:stretch;gap:10px;flex-wrap:wrap;}}
.node{{flex:1 1 150px;background:var(--panel);border:1px solid var(--hair);border-radius:13px;
  padding:15px;position:relative;overflow:hidden;min-width:135px;}}
.node::before{{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--accent);}}
.node.ml::before{{background:var(--good);}}
.node .n{{font-family:var(--mono);font-size:11px;color:var(--ink-3);}}
.node .t{{font-size:16px;font-weight:640;margin:5px 0 3px;}}
.node .c{{font-family:var(--mono);font-size:11px;color:var(--ink-3);line-height:1.35;}}
.node .tag{{position:absolute;top:12px;right:12px;font-family:var(--mono);font-size:9px;
  letter-spacing:.07em;text-transform:uppercase;color:var(--accent);}} .node.ml .tag{{color:var(--good);}}
.arrow{{display:flex;align-items:center;color:var(--ink-3);font-size:18px;}}
@media (max-width:820px){{.arrow{{display:none;}}}}
.onelake{{margin-top:16px;font-family:var(--mono);font-size:12.5px;color:var(--ink-2);
  border-top:1px dashed var(--hair);padding-top:13px;}} .onelake b{{color:var(--ink);}}

.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:15px;margin-top:6px;}}
@media (max-width:820px){{.cards{{grid-template-columns:1fr;}}}}
.vcard{{background:var(--panel);border:1px solid var(--hair);border-radius:14px;padding:22px 20px;
  position:relative;overflow:hidden;}}
.vcard::before{{content:"";position:absolute;left:0;right:0;top:0;height:3px;background:var(--ink-3);}}
.vcard.g::before{{background:var(--good);}} .vcard.w::before{{background:var(--warn);}}
.vcard.c::before{{background:var(--crit);}}
.vk{{font-family:var(--mono);font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);}}
.vnum{{font-family:var(--mono);font-size:clamp(28px,4vw,42px);font-weight:650;letter-spacing:-.02em;
  margin:9px 0 4px;font-variant-numeric:tabular-nums;}}
.vcard.g .vnum{{color:var(--good);}} .vcard.w .vnum{{color:var(--warn);}} .vcard.c .vnum{{color:var(--crit);}}
.vt{{font-size:15px;font-weight:620;margin-bottom:5px;}} .vp{{font-size:13px;color:var(--ink-2);line-height:1.5;}}
.deploy{{margin-top:18px;display:flex;align-items:center;gap:13px;flex-wrap:wrap;
  font-family:var(--mono);font-size:13.5px;color:var(--ink-2);}}
.deploy code{{background:var(--panel-2);border:1px solid var(--hair);border-radius:7px;padding:6px 11px;
  color:var(--accent);}}
.note{{margin-top:12px;font-size:11.5px;color:var(--ink-3);}}

/* chart slides */
.divider .stage{{text-align:left;}}
.big{{font-family:var(--mono);font-size:clamp(46px,8vw,96px);font-weight:650;color:var(--accent);
  letter-spacing:-.03em;line-height:1;}}
.chart-card{{background:var(--panel);border:1px solid var(--hair);border-radius:14px;padding:18px 18px 12px;
  margin-top:12px;}}
.chart-head{{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;
  margin-bottom:10px;}}
.chart-head p{{margin:3px 0 0;color:var(--ink-2);font-size:13.5px;max-width:74ch;}}
.legend{{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--ink-2);font-family:var(--mono);}}
.legend span{{display:inline-flex;align-items:center;gap:6px;}}
.sw{{width:15px;height:0;border-top-width:3px;border-top-style:solid;display:inline-block;}}
.sw.actual{{border-color:var(--ink);}} .sw.fc{{border-color:var(--accent);border-top-style:dashed;}}
.sw.div{{height:11px;border:0;width:13px;background:var(--crit-soft);border-left:2px solid var(--crit);
  border-radius:2px;}}
.chart{{width:100%;height:auto;display:block;}}
.grid{{stroke:var(--hair);stroke-width:1;}} .grid.faint{{stroke:var(--hair);opacity:.5;}}
.ytick,.xtick{{fill:var(--ink-3);font-family:var(--mono);font-size:11px;}}
.ytick{{text-anchor:end;}} .xtick{{text-anchor:middle;}}
.actual{{fill:none;stroke:var(--ink);stroke-width:1.8;}}
.forecast{{fill:none;stroke:var(--accent);stroke-width:2;stroke-dasharray:4 3;}} .forecast.good{{opacity:.95;}}
.diverge{{fill:var(--crit-soft);stroke:none;}} .dot-cross{{fill:var(--crit);}}
.shock-band{{fill:var(--warn);opacity:.10;}} .band-label{{fill:var(--warn);font-family:var(--mono);font-size:11px;}}
.anno-good{{fill:var(--accent);font-family:var(--mono);font-size:11px;text-anchor:middle;}}
.anno-cross{{fill:var(--crit);font-family:var(--mono);font-size:11px;text-anchor:end;}}
.alert-line{{stroke:var(--crit);stroke-width:1.4;stroke-dasharray:3 3;}}
.alert-anno{{fill:var(--crit);font-family:var(--mono);font-size:11.5px;font-weight:600;}}
.mape-raw{{fill:none;stroke:var(--ink-3);stroke-width:1;opacity:.55;}}
.mape-smooth{{fill:none;stroke:var(--accent);stroke-width:2.2;}} .mape-alert{{fill:var(--crit);}}
.band-line{{stroke:var(--warn);stroke-width:1.4;stroke-dasharray:5 3;}}
.band-txt{{fill:var(--warn);font-family:var(--mono);font-size:11px;text-anchor:end;}}
.statrow{{display:flex;gap:26px;flex-wrap:wrap;margin-top:14px;}}
.stat .v{{font-family:var(--mono);font-size:26px;font-weight:650;font-variant-numeric:tabular-nums;}}
.stat .k{{font-family:var(--mono);font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-3);}}
.stat.good .v{{color:var(--good);}} .stat.warn .v{{color:var(--warn);}} .stat.crit .v{{color:var(--crit);}}

table{{width:100%;border-collapse:collapse;font-size:14px;margin-top:6px;}}
th{{text-align:left;font-family:var(--mono);font-size:11px;letter-spacing:.06em;text-transform:uppercase;
  color:var(--ink-3);font-weight:500;padding:7px 10px;border-bottom:1px solid var(--hair);}}
td{{padding:8px 10px;border-bottom:1px solid var(--hair);}}
.mono{{font-family:var(--mono);}} .num{{text-align:right;font-variant-numeric:tabular-nums;}}
.pill{{font-family:var(--mono);font-size:11px;padding:2px 7px;border-radius:5px;}}
.pill.up{{color:var(--good);background:color-mix(in srgb,var(--good) 14%,transparent);}}
.pill.down{{color:var(--crit);background:var(--crit-soft);}}
.kqf{{display:inline-block;background:var(--panel-2);border:1px solid var(--hair);border-radius:7px;
  padding:6px 10px;font-size:12px;color:var(--ink-2);margin:0 7px 7px 0;}}
.kql-snip{{margin:12px 0 0;background:var(--panel-2);border:1px solid var(--hair);border-radius:10px;
  padding:13px 15px;overflow-x:auto;font-family:var(--mono);font-size:11.5px;line-height:1.5;color:var(--ink-2);}}
.kql-snip code{{white-space:pre;}}

.progress{{position:fixed;top:0;left:0;height:3px;background:var(--accent);transition:width .4s ease;z-index:10;}}
.hud{{position:fixed;left:0;right:0;bottom:0;display:flex;align-items:center;justify-content:space-between;
  padding:16px clamp(22px,5vw,52px);z-index:10;pointer-events:none;}}
.hud .brand{{font-family:var(--mono);font-size:11px;letter-spacing:.13em;text-transform:uppercase;color:var(--ink-3);}}
.dots{{display:flex;gap:8px;pointer-events:auto;}}
.dot{{width:8px;height:8px;border-radius:50%;background:var(--hair);border:0;padding:0;cursor:pointer;
  transition:background .3s,transform .3s;}} .dot.on{{background:var(--accent);transform:scale(1.3);}}
.counter{{font-family:var(--mono);font-size:12px;color:var(--ink-3);font-variant-numeric:tabular-nums;}}
.counter b{{color:var(--ink);}}
.corner{{position:fixed;top:20px;right:clamp(22px,5vw,52px);font-family:var(--mono);font-size:11px;
  color:var(--ink-3);z-index:10;}}

@media print{{
  @page{{size:1280px 720px;margin:0;}}
  html,body{{overflow:visible;height:auto;background:#fff;}}
  :root{{ --bg:#FFFFFF; --panel:#FFFFFF; --panel-2:#FAFBFC; --ink:#141A26; --ink-2:#54607A;
    --ink-3:#8A93A8; --hair:#E4E7ED; --accent:#2E7FD6; --good:#1F9D63; --warn:#C77A15; --crit:#CC392E;
    --accent-soft:#2E7FD622; --crit-soft:#CC392E1f; --glow:#2E7FD61f; }}
  .progress,.hud,.corner{{display:none!important;}}
  .deck{{position:static;}}
  .slide{{position:relative;inset:auto;width:1280px;height:720px;opacity:1!important;
    visibility:visible!important;page-break-after:always;break-after:page;overflow:hidden;
    transition:none;}}
  .slide:last-child{{page-break-after:auto;break-after:auto;}}
  .rise{{opacity:1!important;transform:none!important;}}
  .slide{{padding:46px 60px;}}
  .chart-card{{max-width:960px;margin:0 auto;}}
  .statrow{{margin-top:10px;gap:20px;}} .stat .v{{font-size:22px;}}
}}
</style></head><body>

<div class="progress" id="prog"></div>
<div class="corner">Kronos × Fabric RTI</div>
<div class="deck" id="deck">

  <section class="slide s1 active" data-i="0">
    <div class="stage">
      <div>
        <div class="eyebrow rise"><b>Kronos</b> &nbsp;·&nbsp; a foundation model for financial markets</div>
        <h1 class="rise">A model that<br>forecasts.<br>A system that<span class="accent"> acts.</span></h1>
        <p class="lead rise">Kronos turns candlesticks into forecasts. Turning that into value needs live
          market data, GPU serving, and action — in <span class="u">seconds, not batches</span>. This is
          how it runs on Azure &amp; Microsoft Fabric.</p>
        <div class="chips rise">
          <span class="chip"><b>45+</b> exchanges</span>
          <span class="chip">OHLCV K-lines</span>
          <span class="chip">real-time, not batch</span>
        </div>
      </div>
      <div class="rise" aria-hidden="true">
        <svg class="klines" viewBox="0 0 320 240" preserveAspectRatio="xMidYMid meet">
          <g stroke-width="2">
            <g class="k-up">
              <line x1="26" y1="150" x2="26" y2="196"/><rect x="20" y="162" width="12" height="26" rx="2"/>
              <line x1="58" y1="132" x2="58" y2="182"/><rect x="52" y="146" width="12" height="28" rx="2"/>
              <line x1="90" y1="120" x2="90" y2="168"/><rect x="84" y="130" width="12" height="30" rx="2"/>
              <line x1="122" y1="104" x2="122" y2="150"/><rect x="116" y="114" width="12" height="28" rx="2"/>
              <line x1="154" y1="92" x2="154" y2="132"/><rect x="148" y="100" width="12" height="26" rx="2"/>
            </g>
            <g class="k-dn">
              <line x1="186" y1="96" x2="186" y2="150"/><rect x="180" y="104" width="12" height="34" rx="2"/>
              <line x1="218" y1="120" x2="218" y2="188"/><rect x="212" y="128" width="12" height="48" rx="2"/>
            </g>
            <path class="k-fc" d="M154 116 L186 122 L218 150 L250 150 L282 148" stroke-width="2.5" stroke-dasharray="4 3"/>
            <circle class="k-dot" cx="282" cy="148" r="4"/>
          </g>
          <text class="k-lbl" x="248" y="176">forecast</text>
        </svg>
      </div>
    </div>
  </section>

  <section class="slide s2" data-i="1">
    <div class="stage">
      <div class="eyebrow rise">The architecture</div>
      <h2 class="rise">Two planes. One streaming loop.</h2>
      <p class="lead rise" style="max-width:64ch;margin-bottom:20px;">Microsoft Fabric owns
        <span class="u">data, time and action</span>; Azure ML owns <span class="u">the model</span>.
        Every candle flows through one managed pipeline.</p>
      <div class="rise d1"><div class="lane-label"><span class="dot-l"></span>Microsoft Fabric — RTI
        &nbsp;·&nbsp; <span class="dot-l ml"></span>Azure ML — model plane</div></div>
      <div class="flow">
        <div class="node rise d1"><div class="n">01</div><div class="t">Ingest</div>
          <div class="c">Event Hubs → Eventstream</div><div class="tag">Fabric</div></div>
        <div class="arrow rise d1">→</div>
        <div class="node rise d2"><div class="n">02</div><div class="t">Candles</div>
          <div class="c">Eventhouse<br>materialized view</div><div class="tag">Fabric</div></div>
        <div class="arrow rise d2">→</div>
        <div class="node ml rise d3"><div class="n">03</div><div class="t">Forecast</div>
          <div class="c">Kronos on an<br>Azure ML endpoint</div><div class="tag">Azure ML</div></div>
        <div class="arrow rise d3">→</div>
        <div class="node rise d4"><div class="n">04</div><div class="t">Act</div>
          <div class="c">Dashboard +<br>Data Activator</div><div class="tag">Fabric</div></div>
      </div>
      <div class="onelake rise d4">Shared substrate: <b>OneLake</b> — one copy of data &amp; models, read by
        every engine. Secured with Entra ID &amp; managed identities.</div>
    </div>
  </section>

  <section class="slide s3" data-i="2">
    <div class="stage">
      <div class="eyebrow rise">What it delivers</div>
      <h2 class="rise">Forecast in-regime — and know the instant it breaks.</h2>
      <div class="cards">
        <div class="vcard g rise d1"><div class="vk">Signals that pay</div><div class="vnum">~{dir_acc}%</div>
          <div class="vt">Directional accuracy</div><div class="vp">30-minute horizon, in-regime. Momentum
            calls become Data&nbsp;Activator signals — most of them right.</div></div>
        <div class="vcard w rise d2"><div class="vk">Honest about limits</div><div class="vnum">0</div>
          <div class="vt">Shocks predicted</div><div class="vp">No model forecasts an unscheduled news shock.
            The forecast keeps projecting the trend while price dives — as it should.</div></div>
        <div class="vcard c rise d3"><div class="vk">The guardrail</div><div class="vnum">~{latency} min</div>
          <div class="vt">To auto-detect the break</div><div class="vp">Forecast-vs-reality error breaches its
            learned band and fires automatically — a regime change flagged before a human notices.</div></div>
      </div>
      <div class="deploy rise d4"><span>Ingest → forecast → act, one managed loop.</span>
        <code>python deploy_to_fabric.py</code><span>stands it up in Fabric.</span></div>
    </div>
  </section>

  <section class="slide divider" data-i="3">
    <div class="stage">
      <div class="eyebrow rise">Live demo</div>
      <div class="big rise">See it run.</div>
      <p class="lead rise d1" style="margin-top:18px;">A synthetic <b>{symbol}</b> session runs the whole
        pipeline end-to-end: <span class="u">{n_ticks} ticks → {n_candles} candles</span>, a Kronos forecast
        on every candle ({n_forecasts} rolling runs, {pred_len}-min horizon), and an automatic model-health
        guardrail. The next slides are the actual output.</p>
      <div class="note rise d2">Forecaster: {engine_label}. Fixed-seed synthetic data — illustrative of the
        pipeline, not a live-market performance claim.</div>
    </div>
  </section>

  <section class="slide" data-i="4">
    <div class="stage">
      <div class="chart-card">
        <div class="chart-head">
          <div><h2 style="font-size:22px;margin:0 0 2px;">Price &amp; forecast — {symbol}</h2>
            <p>The in-regime forecast tracks; the one issued just before the <b>{shock_h}</b> shock (red
              divergence) is exactly what the guardrail is built to catch.</p></div>
          <div class="legend"><span><i class="sw actual"></i>actual</span>
            <span><i class="sw fc"></i>forecast</span><span><i class="sw div"></i>error</span></div>
        </div>
        {price_svg}
      </div>
      <div class="statrow">
        <div class="stat good"><div class="v">{dir_acc}%</div><div class="k">Directional accuracy</div></div>
        <div class="stat"><div class="v">{med_mape}%</div><div class="k">Median error (MAPE)</div></div>
        <div class="stat good"><div class="v">{hit_rate}%</div><div class="k">Signal hit-rate · {n_signals}</div></div>
      </div>
    </div>
  </section>

  <section class="slide" data-i="5">
    <div class="stage">
      <div class="chart-card">
        <div class="chart-head">
          <div><h2 style="font-size:22px;margin:0 0 2px;">Model-health guardrail</h2>
            <p>Rolling forecast error vs a band learned from the calm regime. The shock pushes error far past
              it; the sustained breach is the auto-detection. Baseline {base_mape}% · band {band}%.</p></div>
          <div class="legend"><span><i class="sw" style="border-color:var(--accent)"></i>error</span>
            <span><i class="sw" style="border-color:var(--warn);border-top-style:dashed"></i>band</span>
            <span style="color:var(--crit)">● breach</span></div>
        </div>
        {guard_svg}
      </div>
      <div class="statrow">
        <div class="stat crit"><div class="v">+{latency} min</div><div class="k">To auto-detect the shock</div></div>
        <div class="stat"><div class="v">{shock_h}</div><div class="k">News shock</div></div>
      </div>
    </div>
  </section>

  <section class="slide" data-i="6">
    <div class="stage">
      <div class="eyebrow rise">Act on it</div>
      <h2 class="rise">Momentum signals become actions.</h2>
      <p class="lead rise d1" style="max-width:70ch;">Data Activator raises a signal when the forecast expects
        a move over the horizon. Sample from the rally — overall {n_signals} signals at {hit_rate}% hit-rate.</p>
      <table class="rise d2"><thead><tr><th>Time</th><th>Call</th><th class="num">Expected</th>
        <th class="num">Realized</th><th>Result</th></tr></thead><tbody>{sig_rows}</tbody></table>
    </div>
  </section>

  <section class="slide" data-i="7">
    <div class="stage">
      <div class="eyebrow rise">Fabric-native</div>
      <h2 class="rise">The whole run round-trips as KQL.</h2>
      <p class="lead rise d1" style="max-width:72ch;">Every stage is emitted as <code>.set-or-append</code>
        against the real Eventhouse schemas. Paste one script into a Fabric queryset and the candles view,
        forecasts, signals and alerts all rebuild — then <code>deploy_to_fabric.py</code> does it for you.</p>
      <div class="rise d2" style="margin-top:6px;">{kql_chips}</div>
      <pre class="kql-snip rise d3"><code>{kql_snippet}</code></pre>
    </div>
  </section>

  <section class="slide divider" data-i="8">
    <div class="stage">
      <div class="eyebrow rise">In one line</div>
      <h1 class="rise" style="font-size:clamp(30px,5vw,60px);">Ingest → forecast → act.<br>
        <span class="accent">One managed, observable loop.</span></h1>
      <div class="deploy rise d1" style="font-size:15px;"><span>Provision &amp; run in Fabric:</span>
        <code>python deploy_to_fabric.py</code></div>
      <p class="note rise d2">Fabric RTI owns data, time and action; Azure ML owns the model. Same
        <span class="u">forecasts</span> schema whether the engine is the baseline or the real Kronos model.</p>
    </div>
  </section>

</div>

<div class="hud">
  <div class="brand">Kronos on Azure · Fabric RTI</div>
  <div class="dots" id="dots"></div>
  <div class="counter"><b id="cur">01</b> / 09</div>
</div>

<script>
(function(){{
  var slides=[].slice.call(document.querySelectorAll('.slide'));
  var dotsWrap=document.getElementById('dots'), prog=document.getElementById('prog'), cur=document.getElementById('cur');
  var i=0, n=slides.length;
  slides.forEach(function(_,k){{var b=document.createElement('button');b.className='dot'+(k===0?' on':'');
    b.setAttribute('aria-label','Slide '+(k+1));b.onclick=function(e){{e.stopPropagation();show(k);}};dotsWrap.appendChild(b);}});
  var dots=[].slice.call(dotsWrap.children);
  function show(k){{i=(k+n)%n;slides.forEach(function(s,x){{s.classList.toggle('active',x===i);}});
    dots.forEach(function(d,x){{d.classList.toggle('on',x===i);}});
    prog.style.width=((i+1)/n*100)+'%';cur.textContent=('0'+(i+1)).slice(-2);}}
  show(0);
  document.addEventListener('keydown',function(e){{
    if(e.key==='ArrowRight'||e.key==='PageDown'||e.key===' '){{show(i+1);e.preventDefault();}}
    else if(e.key==='ArrowLeft'||e.key==='PageUp'){{show(i-1);e.preventDefault();}}
    else if(e.key==='Home'){{show(0);}} else if(e.key==='End'){{show(n-1);}}
  }});
  document.getElementById('deck').addEventListener('click',function(e){{if(e.target.closest('.dot'))return;show(i+1);}});
}})();
</script>
</body></html>
"""


if __name__ == "__main__":
    main()
