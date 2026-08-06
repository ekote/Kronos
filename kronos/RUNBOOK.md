# Runbook — end-to-end: run the Kronos volume-forecasting benchmark

Everything needed to run [`vestacy_kronos_wmape_benchmark.py`](./vestacy_kronos_wmape_benchmark.py)
on Databricks, plug in your own data, read the result, and (optionally) go further
with a Kronos fine-tune. For *why* this benchmark exists and what verdict it feeds,
see [`kronos-fit-assessment.md`](./kronos-fit-assessment.md).

---

## 0. Prerequisites

| Need | Detail |
|---|---|
| Databricks workspace | Azure Databricks; **serverless** or a normal cluster (DBR 14.x+/ML runtime is easiest). |
| Data access | Read on the Unity Catalog table holding monthly SKU volume, **or** nothing (a synthetic panel runs out of the box). |
| Compute for the Kronos arm | **GPU** strongly recommended (Kronos is a PyTorch transformer). Serverless is CPU-first — if no GPU, the Kronos arm reports `SKIPPED` (that itself is the answer to assumption **A4**). |
| Internet / model access | For `timesfm` and `kronos_degenerate`, the runtime downloads checkpoints from Hugging Face. In a locked-down workspace, pre-stage the weights. |

---

## 1. Import the notebook

- **Workspace → Import → File** (or **Repos**), choose
  `vestacy_kronos_wmape_benchmark.py`. It's Databricks *source format* (starts with
  `# Databricks notebook source`), so it imports as a runnable notebook with cells.

## 2. Install libraries (per arm)

The notebook already imports lazily and marks a missing arm `SKIPPED`. To run all
four arms, add a first `%pip` cell (or use cluster libraries):

```python
%pip install statsforecast timesfm
# Kronos arm also needs torch + the Kronos package on the path:
%pip install torch einops safetensors huggingface_hub
# then make Kronos importable, e.g.:
#   %pip install git+https://github.com/shiyu-coder/Kronos.git
#   (or %sh git clone https://github.com/shiyu-coder/Kronos && add it to sys.path)
```

`dbutils.library.restartPython()` after installing. On serverless, prefer notebook-
scoped `%pip`.

## 3. Plug in your data (the important part)

The benchmark reads a **long monthly panel**: one row per `SKU × month` with a
numeric volume. Wire it up with the notebook **widgets** (top of the notebook, cell
"0. Config"):

| Widget | Set to | Notes |
|---|---|---|
| `source_table` | `catalog.schema.table` (e.g. `main.vestacy.shipment_volume_monthly`) | **Leave empty to run the synthetic panel first** and confirm the pipeline. |
| `sku_col` | your SKU column (default `vestacy_sku`) | the series id (grain). |
| `month_col` | your month column (default `calendar_month`) | a date/timestamp; coerced to **month start (`MS`)**. |
| `volume_col` | your volume column (default `volume_eaches`) | numeric; nulls → 0. |
| `n_folds` | rolling-origin folds (default 4) | more folds = more robust, slower. |
| `max_skus` | cap for a short run (default 200) | top-N by total volume. |
| `kronos_skus` | SKUs scored by Kronos (default 40) | Kronos is slow (autoregressive). |
| `intermittent_zero_frac` | zero-month fraction to call a SKU "intermittent" (default 0.30) | drives the **A3** Croston routing + segment table. |

**Data contract expectations**
- **Grain / frequency:** exactly one value per `SKU × calendar month`; monthly (`MS`).
  If your table is daily/weekly, pre-aggregate to month before pointing at it, or add
  a `GROUP BY sku, date_trunc('month', ...)` view and use that as `source_table`.
- **Units:** volume in **eaches** (the contract target). Any additive count works;
  WMAPE is scale-free per horizon.
- **Zeros / intermittency:** keep real zeros (don't drop months) — they define the
  intermittent segment and are handled by Croston in the `statsforecast` arm.
- **History length:** each series needs ≥ ~24 months for the seasonal models and the
  Kronos lookback to engage; shorter series still score under seasonal-naive.
- **No leakage:** the notebook only ever trains on months `<=` the rolling origin; do
  not pre-compute features that peek past it.

Minimal shape the notebook expects after mapping:

```
sku (string) | month (date, month-start) | volume (float, >= 0)
```

## 4. Run it

**Run all.** You'll get, in order:
1. **Arm status** — `OK` or `SKIPPED: <install hint>` per arm.
2. **WMAPE by arm × horizon** (N+1…N+24) + an `avg` column, sorted best-first.
3. **A3 segment table** — WMAPE split by `smooth` vs `intermittent` SKUs.
4. **Verdict** — human-readable A1–A4 lines **plus a machine-readable JSON** you can
   copy into the hackathon evidence / readiness verdict.

## 5. Read the result (A1–A4)

| Assumption | Where to read it |
|---|---|
| **A1** — degenerate-bar Kronos beats the seasonal-naive floor? | Verdict cell: `PASS`/`FAIL`/`UNTESTED` from `kronos_degenerate` vs `seasonal_naive` avg WMAPE. |
| **A2** — cross-SKU pooled fine-tune helps? | **NOT run here** (zero-shot lower bound). See §6. |
| **A3** — intermittent SKUs routed out-of-band? | Segment table: compare `statsforecast` on `intermittent` vs the others. |
| **A4** — serverless can run Kronos at all? | If the Kronos arm ran → `YES`; if `SKIPPED` (no GPU / no weights) → that's the finding. |

Expected outcome (state it either way so the result isn't spun): zero-shot
degenerate-bar Kronos most likely **loses** to `statsforecast`/`timesfm` → **A1 =
FAIL**, Kronos stays NO-GO on evidence. If it wins, the verdict cell says "revisit
the assessment."

## 6. Optional — a fair A2 (fine-tune Kronos), if you want to push it

Zero-shot is the floor. To give Kronos its best shot:
1. Export the pooled monthly bars (all SKUs, degenerate OHLCV) to Delta.
2. Fine-tune with the **Kronos repo's `finetune/`** pipeline
   (`train_tokenizer.py` → `train_predictor.py`) on a **GPU** cluster/job; track with
   MLflow.
3. Point the notebook's Kronos arm at the fine-tuned checkpoint (swap the
   `from_pretrained(...)` ids in `arm_kronos_degenerate`) and re-run.

If zero-shot already loses badly, A2 rarely reverses it — but this is the honest
next step rather than an assumption.

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| `statsforecast` arm `SKIPPED` | `%pip install statsforecast`, restart Python. |
| `timesfm` arm `SKIPPED` | `%pip install timesfm`; TimesFM's constructor differs by version — adapt `arm_timesfm` init to your installed version (it fails soft to SKIPPED). |
| Kronos arm `SKIPPED: … GPU (A4)` | Use a GPU cluster; pre-stage HF weights if the workspace blocks egress. On serverless-CPU this SKIP is a legitimate A4 result. |
| "Not enough history for horizons/folds" | Lower `n_folds` or drop N+24; you need ≥ `max_h + folds + 12` months. |
| Very slow | Lower `max_skus` / `kronos_skus`, or `n_folds`; parallelize across SKUs with Spark / Databricks MMF for production. |

## 8. Cost / time

Seasonal-naive + `statsforecast` are seconds–minutes on a small cluster. `timesfm`
zero-shot is minutes (checkpoint download dominates the first run). The Kronos arm is
the slow one (per-SKU autoregressive decode) — keep `kronos_skus` small for a
hackathon pass.

---

References for every tool named here (Kronos, statsforecast, TimesFM, Databricks) are
in [`REFERENCES.md`](./REFERENCES.md).
