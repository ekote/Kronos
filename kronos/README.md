# `kronos/` — Kronos as a volume-forecasting method: assessment + benchmark

This folder evaluates the **Kronos** foundation model
([repo](https://github.com/shiyu-coder/Kronos) ·
[paper](https://arxiv.org/abs/2508.02739)) as a candidate for the hackathon's
volume-forecasting contract, and backs the verdict with a reproducible benchmark.

It slots into the client contract this repo owns — target = **monthly UK shipment
volume (eaches)**, grain = **`vestacy_sku × calendar month`**, metric = **WMAPE**,
horizons **N+1, N+3, N+6, N+12, N+24**, **calendar rolling-origin** validation —
and defers the forecasting *method* to the `com-skill-volume-forecasting-prototype`
skill. Here we simply ask whether Kronos should be one of those methods.

## TL;DR verdict

**Kronos is NO-GO as the primary method** — it's a financial-candlestick model, and
monthly retail SKU volume is the wrong data shape, domain, and regime for it. It
can appear only as an **experimental challenger under READY_WITH_BOOTSTRAP_
ASSUMPTIONS** (A1–A4 in the assessment). The benchmark tests those assumptions with
numbers instead of argument.

## Contents

| File | What it is |
|---|---|
| [`RUNBOOK.md`](./RUNBOOK.md) | **End-to-end**: how to run on Databricks, how to plug your Unity Catalog data, how to read A1–A4, the optional fine-tune, and troubleshooting. |
| [`kronos-fit-assessment.md`](./kronos-fit-assessment.md) | The evidence note: why Kronos mismatches the contract, the A1–A4 bootstrap assumptions with falsification criteria, and the recommended methods instead. |
| [`vestacy_kronos_wmape_benchmark.py`](./vestacy_kronos_wmape_benchmark.py) | Databricks notebook: benchmarks a **degenerate-bar Kronos** arm vs **seasonal-naive**, **statsforecast** (AutoETS + Croston), and **TimesFM** on WMAPE with calendar rolling-origin; emits a machine-readable A1–A4 verdict. |
| [`REFERENCES.md`](./REFERENCES.md) | **All original Kronos resources** (repo, paper, HF models, license, API, fine-tune pipeline) + the alternative methods + Databricks docs. |

## Quickstart

1. Import `vestacy_kronos_wmape_benchmark.py` into Databricks (source-format; Repos or
   Workspace → Import).
2. `%pip install statsforecast timesfm` (add torch + the Kronos repo for the Kronos
   arm); missing libs report `SKIPPED`, not a crash.
3. Set the **`source_table`** widget to your Unity Catalog table (or leave empty for a
   synthetic panel), map `sku_col` / `month_col` / `volume_col`, **Run all**.
4. Read the WMAPE table, the A3 segment table, and the A1–A4 verdict JSON.

**Full details — env, data schema, interpreting output, fine-tune for A2,
troubleshooting — are in [`RUNBOOK.md`](./RUNBOOK.md).**

> The Kronos arm is **zero-shot** (the A1 lower bound); a fair A2 needs a GPU
> fine-tune (Kronos repo `finetune/`). The notebook was authored to run on Databricks
> but **not executed by its author** — numbers are only as good as the table you point
> it at.

## What "good" looks like here

If zero-shot degenerate-bar Kronos loses to `statsforecast`/`timesfm` (the expected
outcome), **A1 = FAIL** and Kronos stays NO-GO on evidence. If it wins, the notebook
says "revisit the assessment" — the verdict follows the data, not the prior.
