"""
Build the Open Mercato × Kronos × Azure deck (single continuous slide deck).

Reuses the shared chart builders (report.py) so the demand/forecast and
model-health slides show the real demo output, then wraps them in
commerce-framed slides. Works on screen (nav) and in print (one 1280×720 page
per slide) for clean PDF export.

    python deploy/openmercato/build_om_deck.py --out output
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "azure", "demo"))

from marketplace import generate_session       # noqa: E402
from forecaster import KronosAdapter            # noqa: E402
from pipeline import run_pipeline                # noqa: E402
import report as R                               # noqa: E402


def _sig_rows(result):
    meta = result["meta"]
    flash = [x for x in result["signals"] if x["direction"] == "UP"][-7:]
    return "".join(
        f'<tr><td class="mono">{R._hhmm(x["origin_time"])}</td>'
        f'<td><span class="pill up">{x["direction"]}</span></td>'
        f'<td class="mono num">{x["expected_move_pct"]*100:+.1f}%</td>'
        f'<td class="mono num">{x["realized_move_pct"]*100:+.1f}%</td>'
        f'<td>{"&#10003; hit" if x["hit"] else "&middot; miss"}</td></tr>'
        for x in flash)


def build(result):
    s = result["stats"]
    meta = result["meta"]
    in_regime, crossing = R._select_overlays(result)
    price_svg, _ = R._price_chart(result, in_regime, crossing, shock_label="checkout outage")
    guard_svg = R._guardrail_chart(result)
    repl = {
        "@@TENANT@@": s["symbol"], "@@ORDERS@@": f"{s['n_ticks']:,}",
        "@@BARS@@": f"{s['n_candles']:,}", "@@FORECASTS@@": str(s["n_forecasts"]),
        "@@PRED@@": str(s["pred_len"]),
        "@@DIRACC@@": f"{s['directional_accuracy']*100:.1f}",
        "@@MAPE@@": f"{s['in_regime_median_mape']*100:.2f}",
        "@@NSIG@@": str(s["n_signals"]), "@@HIT@@": f"{s['signal_hit_rate']*100:.1f}",
        "@@LAT@@": f"{s['detection_latency_min']:.0f}",
        "@@BAND@@": f"{s['drift_band']*100:.2f}",
        "@@SHOCK@@": R._hhmm(meta["shock_time"]),
        "@@PRICE_SVG@@": price_svg, "@@GUARD_SVG@@": guard_svg, "@@SIG_ROWS@@": _sig_rows(result),
    }
    html = _DECK
    for k, v in repl.items():
        html = html.replace(k, v)
    return html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    bars, meta, orders = generate_session(return_orders=True)
    result = run_pipeline(bars, meta, KronosAdapter(), signal_threshold=0.015)
    result["orders"] = orders
    path = os.path.join(args.out, "openmercato-deck.html")
    with open(path, "w") as f:
        f.write(build(result))
    print("wrote", path)
    return path


# CSS/JS reused from the markets deck (single-brace; token replacement, no .format).
_DECK = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Open Mercato x Kronos x Azure - Solution Deck</title>
<style>
:root{
  --bg:#F4F5F7; --panel:#FFFFFF; --panel-2:#FAFBFC;
  --ink:#141A26; --ink-2:#54607A; --ink-3:#8A93A8; --hair:#E4E7ED;
  --accent:#2E7FD6; --accent-soft:#2E7FD622; --glow:#2E7FD61f;
  --good:#1F9D63; --warn:#C77A15; --crit:#CC392E; --crit-soft:#CC392E1f;
  --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
}
@media (prefers-color-scheme:dark){:root{
  --bg:#0B111C; --panel:#131A28; --panel-2:#0F1623;
  --ink:#EAEEF6; --ink-2:#9DA8BE; --ink-3:#5F6A83; --hair:#222B3C;
  --accent:#59A6F0; --accent-soft:#59A6F02b; --glow:#59A6F033;
  --good:#37C08A; --warn:#E0A040; --crit:#E85D51; --crit-soft:#E85D5122;
}}
:root[data-theme="light"]{ --bg:#F4F5F7; --panel:#FFFFFF; --panel-2:#FAFBFC;
  --ink:#141A26; --ink-2:#54607A; --ink-3:#8A93A8; --hair:#E4E7ED; --accent:#2E7FD6;
  --accent-soft:#2E7FD622; --glow:#2E7FD61f; --good:#1F9D63; --warn:#C77A15; --crit:#CC392E; --crit-soft:#CC392E1f; }
:root[data-theme="dark"]{ --bg:#0B111C; --panel:#131A28; --panel-2:#0F1623;
  --ink:#EAEEF6; --ink-2:#9DA8BE; --ink-3:#5F6A83; --hair:#222B3C; --accent:#59A6F0;
  --accent-soft:#59A6F02b; --glow:#59A6F033; --good:#37C08A; --warn:#E0A040; --crit:#E85D51; --crit-soft:#E85D5122; }
*{box-sizing:border-box;}
html,body{margin:0;height:100%;}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);overflow:hidden;-webkit-font-smoothing:antialiased;}
.deck{position:fixed;inset:0;}
.slide{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;
  padding:clamp(30px,5vw,80px);opacity:0;visibility:hidden;pointer-events:none;transition:opacity .45s ease;overflow:auto;}
.slide.active{opacity:1;visibility:visible;pointer-events:auto;}
@media (prefers-reduced-motion:reduce){.slide{transition:none;}}
.stage{max-width:1140px;width:100%;margin:0 auto;}
.eyebrow{font-family:var(--mono);font-size:clamp(11px,1.1vw,13px);letter-spacing:.2em;text-transform:uppercase;color:var(--ink-3);}
.eyebrow b{color:var(--accent);font-weight:600;}
h1{font-size:clamp(32px,5.6vw,68px);line-height:1.03;letter-spacing:-.025em;margin:.28em 0 .3em;text-wrap:balance;font-weight:650;}
h2{font-size:clamp(24px,3.8vw,44px);line-height:1.06;letter-spacing:-.02em;margin:.1em 0 .45em;text-wrap:balance;font-weight:650;}
.lead{font-size:clamp(15px,1.7vw,21px);line-height:1.5;color:var(--ink-2);max-width:62ch;}
.u{color:var(--ink);font-weight:600;} .accent{color:var(--accent);}
.rise{opacity:0;transform:translateY(12px);transition:opacity .5s ease,transform .5s ease;}
.slide.active .rise{opacity:1;transform:none;}
.slide.active .d1{transition-delay:.08s;} .slide.active .d2{transition-delay:.16s;}
.slide.active .d3{transition-delay:.24s;} .slide.active .d4{transition-delay:.32s;}
@media (prefers-reduced-motion:reduce){.rise{opacity:1;transform:none;transition:none;}}
.chips{display:flex;gap:10px;flex-wrap:wrap;margin-top:26px;}
.chip{font-family:var(--mono);font-size:13px;color:var(--ink-2);background:var(--panel);border:1px solid var(--hair);border-radius:8px;padding:8px 13px;}
.chip b{color:var(--accent);}
.lane-label{font-family:var(--mono);font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);margin-bottom:10px;display:flex;align-items:center;gap:9px;flex-wrap:wrap;}
.dot-l{width:9px;height:9px;border-radius:3px;background:var(--accent);} .dot-l.ml{background:var(--good);}
.flow{display:flex;align-items:stretch;gap:10px;flex-wrap:wrap;}
.node{flex:1 1 150px;background:var(--panel);border:1px solid var(--hair);border-radius:13px;padding:15px;position:relative;overflow:hidden;min-width:130px;}
.node::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--accent);}
.node.ml::before{background:var(--good);}
.node .n{font-family:var(--mono);font-size:11px;color:var(--ink-3);}
.node .t{font-size:15px;font-weight:640;margin:5px 0 3px;}
.node .c{font-family:var(--mono);font-size:10.5px;color:var(--ink-3);line-height:1.35;}
.node .tag{position:absolute;top:11px;right:11px;font-family:var(--mono);font-size:9px;letter-spacing:.06em;text-transform:uppercase;color:var(--accent);}
.node.ml .tag{color:var(--good);}
.arrow{display:flex;align-items:center;color:var(--ink-3);font-size:17px;}
@media (max-width:820px){.arrow{display:none;}}
.onelake{margin-top:16px;font-family:var(--mono);font-size:12.5px;color:var(--ink-2);border-top:1px dashed var(--hair);padding-top:13px;} .onelake b{color:var(--ink);}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:15px;margin-top:6px;}
@media (max-width:820px){.cards{grid-template-columns:1fr;}}
.vcard{background:var(--panel);border:1px solid var(--hair);border-radius:14px;padding:22px 20px;position:relative;overflow:hidden;}
.vcard::before{content:"";position:absolute;left:0;right:0;top:0;height:3px;background:var(--ink-3);}
.vcard.g::before{background:var(--good);} .vcard.w::before{background:var(--warn);} .vcard.c::before{background:var(--crit);}
.vk{font-family:var(--mono);font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);}
.vnum{font-family:var(--mono);font-size:clamp(28px,4vw,42px);font-weight:650;letter-spacing:-.02em;margin:9px 0 4px;font-variant-numeric:tabular-nums;}
.vcard.g .vnum{color:var(--good);} .vcard.w .vnum{color:var(--warn);} .vcard.c .vnum{color:var(--crit);}
.vt{font-size:15px;font-weight:620;margin-bottom:5px;} .vp{font-size:13px;color:var(--ink-2);line-height:1.5;}
.deploy{margin-top:18px;display:flex;align-items:center;gap:13px;flex-wrap:wrap;font-family:var(--mono);font-size:13.5px;color:var(--ink-2);}
.deploy code{background:var(--panel-2);border:1px solid var(--hair);border-radius:7px;padding:6px 11px;color:var(--accent);}
.note{margin-top:12px;font-size:11.5px;color:var(--ink-3);}
.divider .big{font-family:var(--mono);font-size:clamp(46px,8vw,92px);font-weight:650;color:var(--accent);letter-spacing:-.03em;line-height:1;}
.chart-card{background:var(--panel);border:1px solid var(--hair);border-radius:14px;padding:18px 18px 12px;margin-top:12px;}
.chart-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:10px;}
.chart-head p{margin:3px 0 0;color:var(--ink-2);font-size:13.5px;max-width:74ch;}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--ink-2);font-family:var(--mono);}
.legend span{display:inline-flex;align-items:center;gap:6px;}
.sw{width:15px;height:0;border-top-width:3px;border-top-style:solid;display:inline-block;}
.sw.actual{border-color:var(--ink);} .sw.fc{border-color:var(--accent);border-top-style:dashed;}
.sw.div{height:11px;border:0;width:13px;background:var(--crit-soft);border-left:2px solid var(--crit);border-radius:2px;}
.chart{width:100%;height:auto;display:block;}
.grid{stroke:var(--hair);stroke-width:1;} .grid.faint{stroke:var(--hair);opacity:.5;}
.ytick,.xtick{fill:var(--ink-3);font-family:var(--mono);font-size:11px;} .ytick{text-anchor:end;} .xtick{text-anchor:middle;}
.actual{fill:none;stroke:var(--ink);stroke-width:1.8;}
.forecast{fill:none;stroke:var(--accent);stroke-width:2;stroke-dasharray:4 3;} .forecast.good{opacity:.95;}
.diverge{fill:var(--crit-soft);stroke:none;} .dot-cross{fill:var(--crit);}
.shock-band{fill:var(--warn);opacity:.10;} .band-label{fill:var(--warn);font-family:var(--mono);font-size:11px;}
.anno-good{fill:var(--accent);font-family:var(--mono);font-size:11px;text-anchor:middle;}
.anno-cross{fill:var(--crit);font-family:var(--mono);font-size:11px;text-anchor:end;}
.alert-line{stroke:var(--crit);stroke-width:1.4;stroke-dasharray:3 3;}
.alert-anno{fill:var(--crit);font-family:var(--mono);font-size:11.5px;font-weight:600;}
.mape-raw{fill:none;stroke:var(--ink-3);stroke-width:1;opacity:.55;}
.mape-smooth{fill:none;stroke:var(--accent);stroke-width:2.2;} .mape-alert{fill:var(--crit);}
.band-line{stroke:var(--warn);stroke-width:1.4;stroke-dasharray:5 3;}
.band-txt{fill:var(--warn);font-family:var(--mono);font-size:11px;text-anchor:end;}
.statrow{display:flex;gap:26px;flex-wrap:wrap;margin-top:14px;}
.stat .v{font-family:var(--mono);font-size:26px;font-weight:650;font-variant-numeric:tabular-nums;}
.stat .k{font-family:var(--mono);font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-3);}
.stat.good .v{color:var(--good);} .stat.warn .v{color:var(--warn);} .stat.crit .v{color:var(--crit);}
table{width:100%;border-collapse:collapse;font-size:14px;margin-top:6px;}
th{text-align:left;font-family:var(--mono);font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-3);font-weight:500;padding:7px 10px;border-bottom:1px solid var(--hair);}
td{padding:8px 10px;border-bottom:1px solid var(--hair);}
.mono{font-family:var(--mono);} .num{text-align:right;font-variant-numeric:tabular-nums;}
.pill{font-family:var(--mono);font-size:11px;padding:2px 7px;border-radius:5px;}
.pill.up{color:var(--good);background:color-mix(in srgb,var(--good) 14%,transparent);}
.twocol{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:10px;}
@media (max-width:820px){.twocol{grid-template-columns:1fr;}}
.opt{background:var(--panel);border:1px solid var(--hair);border-radius:13px;padding:18px 20px;}
.opt h3{font-size:15px;margin:0 0 8px;} .opt p{margin:0;font-size:13px;color:var(--ink-2);line-height:1.5;}
.opt.a{border-top:3px solid var(--accent);} .opt.b{border-top:3px solid var(--good);}
.progress{position:fixed;top:0;left:0;height:3px;background:var(--accent);transition:width .4s ease;z-index:10;}
.hud{position:fixed;left:0;right:0;bottom:0;display:flex;align-items:center;justify-content:space-between;padding:16px clamp(22px,5vw,52px);z-index:10;pointer-events:none;}
.hud .brand{font-family:var(--mono);font-size:11px;letter-spacing:.13em;text-transform:uppercase;color:var(--ink-3);}
.dots{display:flex;gap:8px;pointer-events:auto;}
.dot{width:8px;height:8px;border-radius:50%;background:var(--hair);border:0;padding:0;cursor:pointer;transition:background .3s,transform .3s;}
.dot.on{background:var(--accent);transform:scale(1.3);}
.counter{font-family:var(--mono);font-size:12px;color:var(--ink-3);font-variant-numeric:tabular-nums;} .counter b{color:var(--ink);}
.corner{position:fixed;top:20px;right:clamp(22px,5vw,52px);font-family:var(--mono);font-size:11px;color:var(--ink-3);z-index:10;}
@media print{
  @page{size:1280px 720px;margin:0;}
  html,body{overflow:visible;height:auto;background:#fff;}
  :root{ --bg:#FFFFFF; --panel:#FFFFFF; --panel-2:#FAFBFC; --ink:#141A26; --ink-2:#54607A; --ink-3:#8A93A8;
    --hair:#E4E7ED; --accent:#2E7FD6; --good:#1F9D63; --warn:#C77A15; --crit:#CC392E;
    --accent-soft:#2E7FD622; --crit-soft:#CC392E1f; --glow:#2E7FD61f; }
  .progress,.hud,.corner{display:none!important;}
  .deck{position:static;}
  .slide{position:relative;inset:auto;width:1280px;height:720px;opacity:1!important;visibility:visible!important;
    page-break-after:always;break-after:page;overflow:hidden;transition:none;padding:46px 60px;}
  .slide:last-child{page-break-after:auto;break-after:auto;}
  .rise{opacity:1!important;transform:none!important;}
  .chart-card{max-width:960px;margin:0 auto;} .statrow{margin-top:10px;gap:20px;} .stat .v{font-size:22px;}
}
</style></head><body>
<div class="progress" id="prog"></div>
<div class="corner">Open Mercato x Kronos x Azure</div>
<div class="deck" id="deck">

  <section class="slide active" data-i="0">
    <div class="stage">
      <div class="eyebrow rise"><b>Open Mercato</b> &nbsp;x&nbsp; Kronos &nbsp;x&nbsp; Azure</div>
      <h1 class="rise">Your storefront already<br>streams the future.<br><span class="accent">Forecast it. Act on it.</span></h1>
      <p class="lead rise">Every order in Open Mercato is a live event. Turn that stream into
        <span class="u">real-time demand forecasts</span> with Kronos on Azure &mdash; and get an
        <span class="u">automatic alarm</span> the moment the model stops matching reality.</p>
      <div class="chips rise">
        <span class="chip"><b>order.*</b> events</span>
        <span class="chip">GMV / minute</span>
        <span class="chip">Fabric RTI or Azure-only</span>
      </div>
    </div>
  </section>

  <section class="slide" data-i="1">
    <div class="stage">
      <div class="eyebrow rise">The architecture</div>
      <h2 class="rise">One event bridge. Then the same real-time loop.</h2>
      <p class="lead rise" style="max-width:66ch;margin-bottom:18px;">Open Mercato publishes domain events;
        a small <span class="u">bridge</span> forwards them to Azure. From there it's the markets pattern,
        retargeted to demand.</p>
      <div class="rise d1"><div class="lane-label"><span class="dot-l"></span>Fabric / Azure data plane
        &nbsp;&middot;&nbsp; <span class="dot-l ml"></span>Azure ML model plane</div></div>
      <div class="flow">
        <div class="node rise d1"><div class="n">01</div><div class="t">Events</div><div class="c">Open Mercato order.*<br>&rarr; bridge &rarr; Event Hubs</div><div class="tag">Bridge</div></div>
        <div class="arrow rise d1">&rarr;</div>
        <div class="node rise d2"><div class="n">02</div><div class="t">Sales bars</div><div class="c">Eventhouse OR ADX<br>gmv_1m view</div><div class="tag">KQL</div></div>
        <div class="arrow rise d2">&rarr;</div>
        <div class="node ml rise d3"><div class="n">03</div><div class="t">Forecast</div><div class="c">Kronos on an<br>Azure ML endpoint</div><div class="tag">Azure ML</div></div>
        <div class="arrow rise d3">&rarr;</div>
        <div class="node rise d4"><div class="n">04</div><div class="t">Act</div><div class="c">Dashboard + alerts<br>&rarr; back into Mercato</div><div class="tag">Activator</div></div>
      </div>
      <div class="twocol">
        <div class="opt a rise d3"><h3>Option A &middot; Microsoft Fabric RTI</h3><p>Eventstream &rarr; Eventhouse &rarr;
          Real-Time Dashboard &rarr; Data Activator. No-code, governed, one platform.</p></div>
        <div class="opt b rise d4"><h3>Option B &middot; Azure-only</h3><p>Event Hubs &rarr; Azure Data Explorer &rarr;
          Azure Functions &rarr; Monitor. <span class="u">Same KQL scripts</span> &mdash; ADX and Eventhouse both speak it.</p></div>
      </div>
    </div>
  </section>

  <section class="slide" data-i="2">
    <div class="stage">
      <div class="eyebrow rise">What it delivers</div>
      <h2 class="rise">Forecast demand &mdash; and know the instant it breaks.</h2>
      <div class="cards">
        <div class="vcard g rise d1"><div class="vk">Demand you can trust</div><div class="vnum">~@@DIRACC@@%</div>
          <div class="vt">Directional accuracy</div><div class="vp">30-min GMV horizon, in-regime, at ~@@MAPE@@% median error.
            Surges become <b>signals</b> &mdash; pre-stock, pre-scale.</div></div>
        <div class="vcard w rise d2"><div class="vk">Honest about limits</div><div class="vnum">0</div>
          <div class="vt">Outages predicted</div><div class="vp">No model foresees a checkout outage or a viral spike.
            The forecast keeps projecting normal demand &mdash; as it should.</div></div>
        <div class="vcard c rise d3"><div class="vk">The guardrail</div><div class="vnum">~@@LAT@@ min</div>
          <div class="vt">To auto-detect the break</div><div class="vp">Forecast-vs-reality error breaches its learned band
            and fires automatically &mdash; a stockout, outage or fraud wave, flagged fast.</div></div>
      </div>
      <div class="deploy rise d4"><span>Events &rarr; forecast &rarr; act, one managed loop.</span>
        <code>run_openmercato_demo.py</code><span>runs it end-to-end.</span></div>
    </div>
  </section>

  <section class="slide divider" data-i="3">
    <div class="stage">
      <div class="eyebrow rise">Live demo</div>
      <div class="big rise">One store-day.</div>
      <p class="lead rise d1" style="margin-top:18px;">A synthetic Open Mercato tenant <b>@@TENANT@@</b>:
        <span class="u">@@ORDERS@@ order events &rarr; @@BARS@@ sales bars</span>, a Kronos forecast every minute
        (@@FORECASTS@@ runs, @@PRED@@-min horizon), a <b>flash sale</b>, and a <b>checkout outage</b>. The next
        slides are the real output.</p>
      <div class="note rise d2">Fixed-seed synthetic data &mdash; illustrative of the loop, not a live-store
        performance claim.</div>
    </div>
  </section>

  <section class="slide" data-i="4">
    <div class="stage">
      <div class="chart-card">
        <div class="chart-head">
          <div><h2 style="font-size:22px;margin:0 0 2px;">GMV / minute &mdash; actual vs forecast</h2>
            <p>Kronos tracks demand in-regime; the forecast issued just before the <b>@@SHOCK@@</b> checkout
              outage (red divergence) is exactly what the guardrail is built to catch.</p></div>
          <div class="legend"><span><i class="sw actual"></i>actual GMV</span>
            <span><i class="sw fc"></i>forecast</span><span><i class="sw div"></i>error</span></div>
        </div>
        @@PRICE_SVG@@
      </div>
      <div class="statrow">
        <div class="stat good"><div class="v">@@DIRACC@@%</div><div class="k">Directional accuracy</div></div>
        <div class="stat"><div class="v">@@MAPE@@%</div><div class="k">Median error (MAPE)</div></div>
        <div class="stat good"><div class="v">@@HIT@@%</div><div class="k">Signal hit-rate &middot; @@NSIG@@</div></div>
      </div>
    </div>
  </section>

  <section class="slide" data-i="5">
    <div class="stage">
      <div class="chart-card">
        <div class="chart-head">
          <div><h2 style="font-size:22px;margin:0 0 2px;">Model-health guardrail</h2>
            <p>Rolling forecast error vs a band learned from calm trading. The outage pushes error far past it;
              the sustained breach is the auto-detection. Band @@BAND@@%.</p></div>
          <div class="legend"><span><i class="sw" style="border-color:var(--accent)"></i>error</span>
            <span><i class="sw" style="border-color:var(--warn);border-top-style:dashed"></i>band</span>
            <span style="color:var(--crit)">&#9679; breach</span></div>
        </div>
        @@GUARD_SVG@@
      </div>
      <div class="statrow">
        <div class="stat crit"><div class="v">+@@LAT@@ min</div><div class="k">To auto-detect the outage</div></div>
        <div class="stat"><div class="v">@@SHOCK@@</div><div class="k">Checkout outage</div></div>
      </div>
    </div>
  </section>

  <section class="slide" data-i="6">
    <div class="stage">
      <div class="eyebrow rise">Act on it</div>
      <h2 class="rise">A flash sale becomes a signal.</h2>
      <p class="lead rise d1" style="max-width:70ch;">Data Activator raises a demand signal when the forecast
        expects a large move &mdash; a surge to pre-stock and pre-scale for, a drop to investigate. Sample of the
        flash-sale surge (of @@NSIG@@ signals @ @@HIT@@% hit).</p>
      <table class="rise d2"><thead><tr><th>Time</th><th>Call</th><th class="num">Expected</th>
        <th class="num">Realized</th><th>Result</th></tr></thead><tbody>@@SIG_ROWS@@</tbody></table>
    </div>
  </section>

  <section class="slide divider" data-i="7">
    <div class="stage">
      <div class="eyebrow rise">In one line</div>
      <h1 class="rise" style="font-size:clamp(28px,4.6vw,56px);">Orders &rarr; forecast &rarr; act.<br>
        <span class="accent">One loop, on Fabric or Azure.</span></h1>
      <div class="deploy rise d1" style="font-size:15px;"><span>Replays into Fabric Eventhouse or Azure Data Explorer:</span>
        <code>replay_all.kql</code></div>
      <p class="note rise d2">Kronos runs on commerce <span class="u">sales bars</span> (fine-tune for accuracy);
        the durable value is the real-time loop + guardrail. Not a Microsoft or Open Mercato product.</p>
    </div>
  </section>

</div>
<div class="hud"><div class="brand">Open Mercato x Kronos x Azure</div>
  <div class="dots" id="dots"></div><div class="counter"><b id="cur">01</b> / 08</div></div>
<script>
(function(){
  var slides=[].slice.call(document.querySelectorAll('.slide'));
  var dotsWrap=document.getElementById('dots'),prog=document.getElementById('prog'),cur=document.getElementById('cur');
  var i=0,n=slides.length;
  slides.forEach(function(_,k){var b=document.createElement('button');b.className='dot'+(k===0?' on':'');
    b.setAttribute('aria-label','Slide '+(k+1));b.onclick=function(e){e.stopPropagation();show(k);};dotsWrap.appendChild(b);});
  var dots=[].slice.call(dotsWrap.children);
  function show(k){i=(k+n)%n;slides.forEach(function(s,x){s.classList.toggle('active',x===i);});
    dots.forEach(function(d,x){d.classList.toggle('on',x===i);});prog.style.width=((i+1)/n*100)+'%';cur.textContent=('0'+(i+1)).slice(-2);}
  show(0);
  document.addEventListener('keydown',function(e){
    if(e.key==='ArrowRight'||e.key==='PageDown'||e.key===' '){show(i+1);e.preventDefault();}
    else if(e.key==='ArrowLeft'||e.key==='PageUp'){show(i-1);e.preventDefault();}
    else if(e.key==='Home'){show(0);}else if(e.key==='End'){show(n-1);}});
  document.getElementById('deck').addEventListener('click',function(e){if(e.target.closest('.dot'))return;show(i+1);});
})();
</script>
</body></html>
"""


if __name__ == "__main__":
    main()
