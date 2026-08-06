# Databricks notebook source
# MAGIC %md
# MAGIC # Vestacy monthly volume — WMAPE benchmark: Kronos (degenerate-bar) vs statsforecast vs TimesFM
# MAGIC
# MAGIC Tests the bootstrap assumptions from the Kronos fit-assessment with **numbers, not argument**.
# MAGIC Runs on **Azure Databricks serverless**; single-node/driver pandas for the arms (production would
# MAGIC parallelize across SKUs with Spark / Databricks MMF).
# MAGIC
# MAGIC **Contract:** target = monthly UK shipment volume (eaches); grain = `vestacy_sku × calendar month`;
# MAGIC metric = **WMAPE**; horizons **N+1, N+3, N+6, N+12, N+24**; **calendar rolling-origin** validation.
# MAGIC
# MAGIC **Arms**
# MAGIC | Arm | Tests |
# MAGIC |---|---|
# MAGIC | `seasonal_naive` (baseline floor) | the bar every model must clear |
# MAGIC | `statsforecast` (AutoETS + Croston for intermittent) | the classical GO candidate; routes intermittent SKUs out-of-band (**A3**) |
# MAGIC | `timesfm` (zero-shot) | general-purpose TS foundation model — the fair FM comparison |
# MAGIC | `kronos_degenerate` (zero-shot, `open=high=low=close=volume`) | **A1** (degenerate-bar encoding). This is the *lower bound* — **A2** (cross-SKU pooled fine-tune) is out of scope for a short notebook and flagged as the next step. **A4** = does serverless even run it. |
# MAGIC
# MAGIC > Honesty: this notebook was authored, not executed by its author (no Databricks/torch/data at write
# MAGIC > time). Arms with a missing library report `SKIPPED` + an install hint rather than failing the run.
# MAGIC > Any arm's numbers are only as good as the data you point it at.

# COMMAND ----------

# MAGIC %md ## 0. Config (widgets)

# COMMAND ----------

# Databricks widgets — edit in the UI or here. On plain Python these dbutils calls are no-ops via the guard.
def _widget(name, default):
    try:
        dbutils.widgets.text(name, default)   # noqa: F821
        return dbutils.widgets.get(name)       # noqa: F821
    except Exception:
        return default

SOURCE_TABLE   = _widget("source_table", "")          # e.g. main.vestacy.shipment_volume_monthly ; empty -> synthetic
SKU_COL        = _widget("sku_col", "vestacy_sku")
MONTH_COL      = _widget("month_col", "calendar_month")
VOLUME_COL     = _widget("volume_col", "volume_eaches")
N_FOLDS        = int(_widget("n_folds", "4"))          # rolling-origin folds
MAX_SKUS       = int(_widget("max_skus", "200"))       # cap for the short benchmark
KRONOS_SKUS    = int(_widget("kronos_skus", "40"))     # Kronos is slow (autoregressive); subset
INTERMITTENT_ZERO_FRAC = float(_widget("intermittent_zero_frac", "0.30"))  # A3 threshold

HORIZONS = [1, 3, 6, 12, 24]
MAX_H = max(HORIZONS)
SEED = 7

import numpy as np
import pandas as pd

# COMMAND ----------

# MAGIC %md ## 1. Data — real Unity Catalog table, else a synthetic monthly SKU panel

# COMMAND ----------

def make_synthetic_panel(n_sku=200, start="2019-01-01", n_months=84, seed=SEED):
    """A believable monthly SKU panel: level + seasonality + trend + noise, ~30% intermittent SKUs."""
    rng = np.random.default_rng(seed)
    months = pd.date_range(start=start, periods=n_months, freq="MS")
    rows = []
    for i in range(n_sku):
        base = float(rng.lognormal(mean=6.0, sigma=1.0))          # wide level spread across SKUs
        trend = rng.normal(0.0, 0.004)                            # gentle per-SKU trend
        amp = rng.uniform(0.1, 0.5)                               # seasonal amplitude
        phase = rng.uniform(0, 2 * np.pi)
        intermittent = rng.random() < 0.30
        for t, m in enumerate(months):
            seasonal = 1.0 + amp * np.sin(2 * np.pi * (m.month / 12.0) + phase)
            level = base * seasonal * np.exp(trend * t)
            noise = rng.normal(1.0, 0.15)
            v = level * noise
            if intermittent and rng.random() < 0.45:             # sparse months
                v = 0.0
            rows.append((f"SKU_{i:04d}", m, max(0.0, round(v))))
    return pd.DataFrame(rows, columns=["sku", "month", "volume"])


def load_panel():
    if SOURCE_TABLE.strip():
        sdf = spark.table(SOURCE_TABLE)  # noqa: F821
        pdf = (sdf.select(SKU_COL, MONTH_COL, VOLUME_COL)
                  .toPandas()
                  .rename(columns={SKU_COL: "sku", MONTH_COL: "month", VOLUME_COL: "volume"}))
        pdf["month"] = pd.to_datetime(pdf["month"]).values.astype("datetime64[M]").astype("datetime64[ns]")
        pdf["volume"] = pd.to_numeric(pdf["volume"], errors="coerce").fillna(0.0)
        print(f"Loaded {SOURCE_TABLE}: {pdf['sku'].nunique()} SKUs, {pdf['month'].nunique()} months")
        return pdf
    print("SOURCE_TABLE empty -> synthetic panel (illustrative; not Vestacy data).")
    return make_synthetic_panel(n_sku=MAX_SKUS)


panel = load_panel()
# Keep the highest-volume SKUs for a short, representative benchmark.
top = (panel.groupby("sku")["volume"].sum().sort_values(ascending=False).head(MAX_SKUS).index)
panel = panel[panel["sku"].isin(top)].sort_values(["sku", "month"]).reset_index(drop=True)
ALL_MONTHS = np.sort(panel["month"].unique())
print(f"Benchmark panel: {panel['sku'].nunique()} SKUs x {len(ALL_MONTHS)} months")

# Intermittency class per SKU (drives A3 routing + segmentation).
zero_frac = panel.assign(is_zero=panel["volume"] <= 0).groupby("sku")["is_zero"].mean()
INTERMITTENT = set(zero_frac[zero_frac >= INTERMITTENT_ZERO_FRAC].index)
print(f"Intermittent SKUs (>= {INTERMITTENT_ZERO_FRAC:.0%} zero months): {len(INTERMITTENT)}")

# COMMAND ----------

# MAGIC %md ## 2. WMAPE + calendar rolling-origin

# COMMAND ----------

def wmape(y_true, y_pred):
    y_true = np.asarray(y_true, float); y_pred = np.asarray(y_pred, float)
    denom = np.abs(y_true).sum()
    return float(np.abs(y_true - y_pred).sum() / denom) if denom > 0 else np.nan


def rolling_origins(months, n_folds, max_h):
    """Calendar origins near the end; each needs at least one evaluable horizon (origin + h <= last)."""
    months = list(np.sort(months))
    last_idx = len(months) - 1
    # Latest origin still lets N+1 be scored; step back one month per fold.
    origins = [months[last_idx - max_h - k] for k in range(n_folds) if last_idx - max_h - k >= 12]
    return list(reversed(origins))


ORIGINS = rolling_origins(ALL_MONTHS, N_FOLDS, MAX_H)
print("Rolling-origin cutoffs:", [pd.Timestamp(o).strftime("%Y-%m") for o in ORIGINS])
if not ORIGINS:
    raise ValueError("Not enough history for the requested horizons/folds — reduce MAX_H or N_FOLDS.")

# Fast lookup: actual volume by (sku, month).
ACTUAL = panel.set_index(["sku", "month"])["volume"].to_dict()


def target_month(origin, h):
    idx = list(ALL_MONTHS).index(origin)
    j = idx + h
    return ALL_MONTHS[j] if j < len(ALL_MONTHS) else None

# COMMAND ----------

# MAGIC %md ## 3. Arms
# MAGIC Each arm returns `{(sku, horizon): yhat}` for one origin, or raises `Skip` (recorded as SKIPPED).

# COMMAND ----------

class Skip(Exception):
    pass


def train_long(origin):
    """Long panel (unique_id, ds, y) using only history <= origin."""
    tr = panel[panel["month"] <= origin]
    return tr.rename(columns={"sku": "unique_id", "month": "ds", "volume": "y"})[["unique_id", "ds", "y"]]


# --- seasonal_naive (baseline floor) ---------------------------------------
def arm_seasonal_naive(origin, skus):
    out = {}
    for sku in skus:
        hist = panel[(panel["sku"] == sku) & (panel["month"] <= origin)]
        if hist.empty:
            continue
        last_val = hist.sort_values("month")["volume"].iloc[-1]
        for h in HORIZONS:
            tgt = target_month(origin, h)
            if tgt is None:
                continue
            # last-year-same-month if it's in the training window, else last obs.
            ly = pd.Timestamp(tgt) - pd.DateOffset(months=12)
            out[(sku, h)] = float(ACTUAL.get((sku, np.datetime64(ly, "ns")), last_val)) \
                if ly.to_datetime64() <= origin else float(last_val)
    return out


# --- statsforecast: AutoETS (smooth) + Croston (intermittent) -> tests A3 ----
def arm_statsforecast(origin, skus):
    try:
        from statsforecast import StatsForecast
        from statsforecast.models import AutoETS, CrostonClassic
    except Exception:
        raise Skip("pip install statsforecast")
    tl = train_long(origin)
    tl = tl[tl["unique_id"].isin(skus)]
    smooth = [s for s in skus if s not in INTERMITTENT]
    inter = [s for s in skus if s in INTERMITTENT]
    frames = []
    if smooth:
        sf = StatsForecast(models=[AutoETS(season_length=12)], freq="MS", n_jobs=-1)
        frames.append(sf.forecast(df=tl[tl["unique_id"].isin(smooth)], h=MAX_H).rename(columns={"AutoETS": "yhat"}))
    if inter:  # A3: route intermittent SKUs out-of-band to Croston
        sf = StatsForecast(models=[CrostonClassic()], freq="MS", n_jobs=-1)
        frames.append(sf.forecast(df=tl[tl["unique_id"].isin(inter)], h=MAX_H).rename(columns={"CrostonClassic": "yhat"}))
    fc = pd.concat(frames, ignore_index=True)
    fc["ds"] = pd.to_datetime(fc["ds"])
    out = {}
    for h in HORIZONS:
        tgt = target_month(origin, h)
        if tgt is None:
            continue
        sub = fc[fc["ds"] == pd.Timestamp(tgt)]
        for uid, yh in zip(sub["unique_id"], sub["yhat"]):
            out[(uid, h)] = max(0.0, float(yh))
    return out


# --- TimesFM (zero-shot) ----------------------------------------------------
def arm_timesfm(origin, skus):
    try:
        import timesfm  # noqa
    except Exception:
        raise Skip("pip install timesfm  (and adapt init to your TimesFM version)")
    # NOTE: TimesFM's constructor differs across 1.x/2.x — adapt this block to your installed version.
    try:
        tfm = timesfm.TimesFm(  # v1.x-style; wrap so a version mismatch -> SKIPPED not crash
            context_len=min(512, len(ALL_MONTHS)), horizon_len=MAX_H,
            input_patch_len=32, output_patch_len=128, num_layers=20, model_dims=1280, backend="cpu")
        tfm.load_from_checkpoint(repo_id="google/timesfm-1.0-200m")
    except Exception as e:
        raise Skip(f"TimesFM init/checkpoint failed ({type(e).__name__}); adapt to your version")
    series, ids = [], []
    for sku in skus:
        h = panel[(panel["sku"] == sku) & (panel["month"] <= origin)].sort_values("month")["volume"].values
        if len(h) >= 12:
            series.append(np.asarray(h, float)); ids.append(sku)
    if not series:
        raise Skip("no series with >=12 months")
    point, _ = tfm.forecast(series, freq=[0] * len(series))
    out = {}
    for uid, fc in zip(ids, np.asarray(point)):
        for h in HORIZONS:
            if target_month(origin, h) is not None and h - 1 < fc.shape[0]:
                out[(uid, h)] = max(0.0, float(fc[h - 1]))
    return out


# --- Kronos (zero-shot, degenerate bar) -> tests A1 (lower bound) ------------
def arm_kronos_degenerate(origin, skus):
    try:
        import torch  # noqa
        from model import Kronos, KronosTokenizer, KronosPredictor
    except Exception:
        raise Skip("needs the Kronos repo on path + torch (git clone + %pip install einops safetensors huggingface_hub torch)")
    try:
        tok = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
        mdl = Kronos.from_pretrained("NeoQuasar/Kronos-small")
        predictor = KronosPredictor(mdl, tok, max_context=512)
    except Exception as e:
        raise Skip(f"Kronos load failed ({type(e).__name__}); check weights/network/GPU (A4)")
    out, done = {}, 0
    for sku in skus:
        if done >= KRONOS_SKUS:
            break
        hist = panel[(panel["sku"] == sku) & (panel["month"] <= origin)].sort_values("month")
        if len(hist) < 24:
            continue
        v = hist["volume"].astype(float).values
        x_df = pd.DataFrame({"open": v, "high": v, "low": v, "close": v,   # A1: degenerate bar
                             "volume": v, "amount": np.zeros_like(v)})
        x_ts = pd.Series(pd.to_datetime(hist["month"].values))
        y_ts = pd.Series(pd.date_range(pd.Timestamp(origin) + pd.DateOffset(months=1), periods=MAX_H, freq="MS"))
        try:
            pred = predictor.predict(df=x_df, x_timestamp=x_ts, y_timestamp=y_ts,
                                     pred_len=MAX_H, T=1.0, top_p=0.9, sample_count=1, verbose=False)
        except Exception:
            continue
        close = pred["close"].values
        for h in HORIZONS:
            if target_month(origin, h) is not None and h - 1 < len(close):
                out[(sku, h)] = max(0.0, float(close[h - 1]))
        done += 1
    if not out:
        raise Skip("no Kronos forecasts produced")
    return out


ARMS = {
    "seasonal_naive": arm_seasonal_naive,
    "statsforecast": arm_statsforecast,
    "timesfm": arm_timesfm,
    "kronos_degenerate": arm_kronos_degenerate,
}

# COMMAND ----------

# MAGIC %md ## 4. Rolling-origin evaluation

# COMMAND ----------

skus = sorted(panel["sku"].unique())
# accumulate abs-error and abs-actual per (arm, horizon) and per (arm, horizon, segment)
acc = {}          # (arm,h) -> [err_sum, y_sum]
acc_seg = {}      # (arm,h,seg) -> [err_sum, y_sum]
status = {}       # arm -> "OK" | "SKIPPED: <hint>"


def _add(d, key, err, y):
    s = d.setdefault(key, [0.0, 0.0]); s[0] += err; s[1] += y


for arm_name, fn in ARMS.items():
    ran_any = False
    for origin in ORIGINS:
        try:
            preds = fn(origin, skus)
            ran_any = True
        except Skip as sk:
            status[arm_name] = f"SKIPPED: {sk}"
            break
        except Exception as e:
            status[arm_name] = f"SKIPPED: {type(e).__name__}: {e}"
            break
        for (sku, h), yhat in preds.items():
            tgt = target_month(origin, h)
            key = (sku, np.datetime64(pd.Timestamp(tgt), "ns"))
            if key not in ACTUAL:
                continue
            y = float(ACTUAL[key]); err = abs(y - yhat)
            _add(acc, (arm_name, h), err, y)
            seg = "intermittent" if sku in INTERMITTENT else "smooth"
            _add(acc_seg, (arm_name, h, seg), err, y)
    if ran_any and arm_name not in status:
        status[arm_name] = "OK"

print("Arm status:")
for a, s in status.items():
    print(f"  {a:20s} {s}")

# COMMAND ----------

# MAGIC %md ## 5. Results — WMAPE by arm × horizon

# COMMAND ----------

rows = []
for (arm_name, h), (err, y) in acc.items():
    rows.append({"arm": arm_name, "horizon": f"N+{h}", "h": h,
                 "WMAPE": (err / y) if y > 0 else np.nan})
res = (pd.DataFrame(rows).pivot(index="arm", columns="h", values="WMAPE")
       if rows else pd.DataFrame())
if not res.empty:
    res = res.reindex(columns=HORIZONS)
    res.columns = [f"N+{c}" for c in res.columns]
    res["avg"] = res.mean(axis=1)
    res = res.sort_values("avg")
    print("WMAPE (lower is better):")
    display(res.style.format("{:.3f}"))  # noqa: F821
else:
    print("No results — check arm status above.")

# COMMAND ----------

# MAGIC %md ## 6. A3 — WMAPE by intermittency segment

# COMMAND ----------

seg_rows = []
for (arm_name, h, seg), (err, y) in acc_seg.items():
    seg_rows.append({"arm": arm_name, "segment": seg, "h": h, "WMAPE": (err / y) if y > 0 else np.nan})
if seg_rows:
    seg = (pd.DataFrame(seg_rows).groupby(["arm", "segment"])["WMAPE"].mean().unstack("segment"))
    display(seg.style.format("{:.3f}"))  # noqa: F821

# COMMAND ----------

# MAGIC %md ## 7. Verdict — A1..A4 tested, not asserted

# COMMAND ----------

def _avg(arm):
    vals = [v[0] / v[1] for (a, h), v in acc.items() if a == arm and v[1] > 0]
    return float(np.mean(vals)) if vals else None

sn = _avg("seasonal_naive"); sf = _avg("statsforecast")
tf = _avg("timesfm"); kr = _avg("kronos_degenerate")

verdict = {"assessment": "Kronos for Vestacy monthly volume", "horizons": HORIZONS,
           "arm_status": status, "avg_wmape": {"seasonal_naive": sn, "statsforecast": sf,
                                               "timesfm": tf, "kronos_degenerate": kr}}

def line(label, cond, detail):
    print(f"  {label}: {cond}  — {detail}")

print("A1 (degenerate-bar Kronos beats the seasonal-naive floor?)")
if kr is None:
    line("A1", "UNTESTED", f"kronos arm {status.get('kronos_degenerate','?')}")
    verdict["A1"] = "UNTESTED"
else:
    beats = kr < sn if sn is not None else False
    line("A1", "PASS" if beats else "FAIL", f"kronos={kr:.3f} vs seasonal_naive={sn:.3f}")
    verdict["A1"] = "PASS" if beats else "FAIL"

print("A2 (cross-SKU pooled fine-tune) — NOT run here (zero-shot only).")
verdict["A2"] = "NOT_RUN (zero-shot lower bound; fine-tune is the next step)"

print("A3 (intermittent routed out-of-band) — see segment table; statsforecast uses Croston on intermittent SKUs.")
verdict["A3"] = "SEE_SEGMENT_TABLE"

print("A4 (serverless can run Kronos) —", "YES" if kr is not None else f"NO/UNKNOWN ({status.get('kronos_degenerate','?')})")
verdict["A4"] = "YES" if kr is not None else "NO_OR_UNKNOWN"

# Overall recommendation, evidence-based.
ranked = sorted([(v, k) for k, v in verdict["avg_wmape"].items() if v is not None])
if ranked:
    best = ranked[0][1]
    print(f"\nBest arm by avg WMAPE: {best}")
    kronos_is_best = best == "kronos_degenerate"
    verdict["recommendation"] = (
        "Kronos competitive here — revisit assessment with these numbers." if kronos_is_best
        else f"Kronos NOT recommended; use '{best}'. Consistent with the fit assessment (NO-GO for Kronos).")
    print(verdict["recommendation"])

import json
print("\nMachine-readable verdict:\n", json.dumps(verdict, indent=2, default=str))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Notes & honest caveats
# MAGIC - **Zero-shot Kronos is the lower bound for A1.** A fair A2 test means fine-tuning Kronos on the pooled
# MAGIC   cross-section of SKUs (repo `finetune/`) on a GPU cluster, then re-running this arm. If zero-shot already
# MAGIC   loses badly to `statsforecast`/`timesfm`, A2 rarely rescues it — but it is the honest next step.
# MAGIC - **statsforecast** here = AutoETS (smooth) + CrostonClassic (intermittent). Add AutoARIMA/Theta/TSB and
# MAGIC   hierarchical reconciliation (MinT) for the real GO candidate; consider Databricks **Many Model
# MAGIC   Forecasting** to parallelize across SKUs.
# MAGIC - **TimesFM init** varies by version — adapt `arm_timesfm` to your installed TimesFM; it will report
# MAGIC   SKIPPED rather than crash if the constructor signature differs.
# MAGIC - **Fairness:** all arms use the same calendar rolling-origin cutoffs, the same SKUs, and volume-weighted
# MAGIC   WMAPE, so the comparison is apples-to-apples for whatever ran.
# MAGIC - Point this at the real Unity Catalog table via the `source_table` widget; the synthetic panel is only
# MAGIC   so the notebook runs anywhere.
