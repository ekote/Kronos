# Fit assessment — Kronos for Vestacy monthly volume forecasting

> **Portable evidence note.** Authored in the Kronos repo; intended to drop into
> the Vestacy client repo's evidence folder to feed the readiness verdict. It
> assesses one question: *is Kronos an appropriate forecasting method for the
> Vestacy monthly volume contract?* It does not change the data contract or the
> skill's method — it supplies evidence and a recommendation.

| | |
|---|---|
| **Subject** | Kronos foundation model ([repo](https://github.com/shiyu-coder/Kronos), [paper](https://arxiv.org/abs/2508.02739)) as a candidate method |
| **Use case** | Vestacy monthly UK shipment-volume forecasting hackathon (Azure Databricks serverless) |
| **Data contract** | target = monthly UK shipment volume (eaches); grain = `vestacy_sku × calendar month`; metric = **WMAPE**; horizons = N+1, N+3, N+6, N+12, N+24; **calendar rolling-origin** validation |
| **Assessment date** | 2026-08-04 |
| **Verdict for Kronos** | **NO-GO as primary method.** Include only as an *experimental challenger* under **READY_WITH_BOOTSTRAP_ASSUMPTIONS**, with the assumptions and falsification criteria below. |
| **Confidence tags** | [Certain] = grounded in Kronos source / the contract · [Likely] = strong inference · [Guessing] = depends on data we haven't seen |

---

## 1. Executive verdict

**Do not adopt Kronos as the Vestacy forecasting method.** [Certain] Kronos is a
foundation model for **financial candlesticks** — a decoder-only transformer over
**Binary-Spherical-Quantized OHLCV bars** (`model/kronos.py`: `KronosTokenizer`,
`Kronos`, `KronosPredictor`). The Vestacy target is a **univariate monthly count
per SKU**, in a domain (UK retail shipments) and regime (short series, long
horizons, intermittency, WMAPE) where Kronos's design provides no advantage and
several active disadvantages.

If governance requires Kronos to appear as a challenger arm, it can be included
**only** under explicit bootstrap assumptions (§4), scored against real baselines
(§5), and reported as experimental — never as the recommended model.

---

## 2. What Kronos actually is (evidence)

From the model source (not marketing):

- **Input/output = OHLCV bars.** `KronosPredictor.predict(df, x_timestamp,
  y_timestamp, pred_len, …)` expects `open, high, low, close[, volume, amount]`
  and returns forecast OHLCV. [Certain]
- **Two-stage design:** a **BSQ tokenizer** turns each continuous bar into
  hierarchical discrete tokens (`s1_bits` + `s2_bits`); an **autoregressive
  Transformer** predicts next tokens; results are decoded back to bars. [Certain]
- **Preprocessing** z-score-normalizes per window and clips (`clip=5`); dynamics
  are effectively **log-return-like**. [Certain]
- **Context length** 512 (base/small) / 2048 (mini); **probabilistic sampling**
  via temperature / top-p / `sample_count`. [Certain]
- **Pretraining domain:** price/volume K-lines from 45+ exchanges. [Certain]

These are the properties that make it strong on liquid, higher-frequency price
series — and ill-suited to the Vestacy contract.

---

## 3. Fit analysis against the Vestacy contract

| Contract dimension | Kronos design | Assessment |
|---|---|---|
| Target = univariate **monthly volume (eaches)** | multivariate **OHLCV** bars | **Mismatch [Certain].** No O/H/L/C exist. Encoding `open=high=low=close=volume` is a *degenerate* bar that discards the model's core inductive bias (intrabar shape, price↔volume coupling). |
| Grain = `sku × month`; **~24–60 points/SKU** | 512–2048-length dense context | **Mismatch [Certain].** The context capability never engages; a per-SKU monthly series is data-starved for a ~100M-param transformer. |
| Horizons **N+1 … N+24 months** | short-horizon roll-outs on dense series | **Weak [Likely].** 24-step monthly roll-out from a data-poor origin is where statistical + purpose-built demand models dominate. |
| SKU monthly demand is often **intermittent / lumpy** (zeros) | continuous, log-return-style; z-score + clip | **Mismatch [Certain].** No intermittent-demand handling (no Croston/TSB analog); zeros break the log-return framing; normalization/tokenization assume continuity. |
| Metric = **WMAPE**, calendar rolling-origin | nucleus-sampled candle distribution, averaged | **Weak [Likely].** Favors calibrated point forecasts + hierarchical reconciliation, not sampled candles. |
| Domain = **UK retail** (promotions, seasonality, calendar) | exchange microstructure | **Mismatch [Certain].** Financial pretraining gives **no transferable priors**; utility would depend entirely on fine-tuning — on data too thin per SKU. |
| Platform = **Databricks serverless** | PyTorch **GPU** (train), GPU/CPU (infer) | **Friction [Likely].** Serverless compute is CPU-first; competitive Kronos needs GPU fine-tuning that serverless may not provide. |

**Net:** five mismatches (four [Certain]), two weaknesses, one platform friction.
No dimension favors Kronos.

---

## 4. Conditional inclusion path (if Kronos must be a challenger)

This is the **only** defensible way to include Kronos, and it is
**READY_WITH_BOOTSTRAP_ASSUMPTIONS**, not GO. Each assumption is explicit and
falsifiable; if any fails, Kronos is NO-GO.

| # | Bootstrap assumption | How to falsify | If falsified |
|---|---|---|---|
| A1 | Degenerate-bar encoding (`open=high=low=close=volume`, `amount=0`) preserves enough signal | Compare fine-tuned Kronos WMAPE vs seasonal-naïve at N+1/3/6 | Drop Kronos |
| A2 | **Cross-SKU pooled** fine-tune (all SKUs, month-index time features) overcomes per-SKU data scarcity | Rolling-origin WMAPE vs classical baselines, per horizon | Drop Kronos |
| A3 | Intermittency is handled **out-of-band** (route sparse SKUs to Croston/TSB; Kronos only on high-volume non-intermittent SKUs) | Segment WMAPE by intermittency class | Restrict scope or drop |
| A4 | Databricks serverless can run the required **GPU fine-tune** (or an offline GPU job feeds a registered model) | Confirm GPU availability / MLflow-registered artifact | Move off serverless or drop |

**Reporting rule:** any Kronos result ships labeled *experimental, bootstrap
assumptions A1–A4*, with the WMAPE table beside the baselines — never as the
headline.

---

## 5. Recommended methods instead (what should carry the verdict)

[Likely] These are the methods that actually win monthly SKU-level WMAPE and are
native to Databricks serverless:

- **Classical / ML (primary GO candidates):** ETS, ARIMA, Theta, seasonal-naïve
  via **Nixtla `statsforecast`**; **`mlforecast` / LightGBM** with lag + calendar +
  promo features; **Croston / TSB** for intermittent SKUs; **hierarchical
  reconciliation (MinT)** across `sku → category → total`.
- **Foundation-model arm (GO candidate, if one is wanted):** **TimesFM** (Google,
  TS-native, ~100B time-points), **Chronos-Bolt** (Amazon), **Moirai**
  (Salesforce) — general-purpose, zero-shot univariate, matched to monthly data.
- **Platform accelerator:** Databricks' first-party **Many Model Forecasting
  (MMF)** already integrates 40+ of these (statsforecast, neuralforecast, sktime,
  Chronos, Moirai, Moment, TimesFM) and auto-selects per series. **Kronos is not
  in MMF** — a useful signal about domain fit.

---

## 6. Readiness verdict mapping

| Method arm | Verdict | Rationale |
|---|---|---|
| Classical + GBM ensemble (`statsforecast`/`mlforecast`, Croston/TSB, MinT) | **GO candidate** | Purpose-built for monthly SKU volume + WMAPE; strong under data scarcity. |
| General TS foundation model (TimesFM / Chronos / Moirai) | **GO candidate** | Zero-shot univariate; correct data shape; Databricks-native via MMF. |
| **Kronos** | **NO-GO (primary); experimental-only** | Wrong data shape/domain/regime; usable only under bootstrap assumptions A1–A4. |

---

## 7. Evidence gaps (what would change this)

- [Guessing] **SKU volume distribution & history length** — if a meaningful share
  of SKUs are high-volume, non-intermittent, with 5+ years of monthly history, the
  *general* FM arm (TimesFM/Chronos) strengthens. Kronos still does not, for the
  domain/shape reasons in §3.
- [Guessing] **Serverless GPU reality** — confirm whether the hackathon
  environment can fine-tune/serve a PyTorch GPU model at all (A4).
- Intermittency rate by SKU segment (drives A3 and Croston/TSB scope).

---

## 8. References

- Kronos — model & code: <https://github.com/shiyu-coder/Kronos> · paper:
  <https://arxiv.org/abs/2508.02739>
- Databricks Many Model Forecasting:
  <https://github.com/databricks-industry-solutions/many-model-forecasting>
- Databricks — time-series forecasting with generative AI:
  <https://www.databricks.com/blog/introduction-time-series-forecasting-generative-ai>
- Nixtla statsforecast / mlforecast: <https://github.com/Nixtla/statsforecast> ·
  <https://github.com/Nixtla/mlforecast>
- TimesFM: <https://github.com/google-research/timesfm> · Chronos:
  <https://github.com/amazon-science/chronos-forecasting> · Moirai (uni2ts):
  <https://github.com/SalesforceAIResearch/uni2ts>

---

*Prepared as an independent fit assessment. Kronos's appropriate home is
high-frequency financial / price-volume forecasting; this note recommends against
repurposing it for monthly retail-demand forecasting.*
