# References

Everything cited by this folder — the **original Kronos resources** first, then the
recommended alternative methods and the Databricks/platform docs.

## Kronos — original resources (the model under assessment)

| Resource | Link |
|---|---|
| **Source code (official repo)** | <https://github.com/shiyu-coder/Kronos> |
| **Paper** — *Kronos: A Foundation Model for the Language of Financial Markets* | <https://arxiv.org/abs/2508.02739> |
| **License** | MIT — © 2025 ShiYu (`LICENSE` in the repo) |
| **Pretrained models (Hugging Face org)** | <https://huggingface.co/NeoQuasar> |
| ↳ Kronos-mini (4.1M, ctx 2048) | <https://huggingface.co/NeoQuasar/Kronos-mini> |
| ↳ Kronos-small (24.7M, ctx 512) | <https://huggingface.co/NeoQuasar/Kronos-small> |
| ↳ Kronos-base (102.3M, ctx 512) | <https://huggingface.co/NeoQuasar/Kronos-base> |
| ↳ Tokenizer-base (BSQ) | <https://huggingface.co/NeoQuasar/Kronos-Tokenizer-base> |
| ↳ Tokenizer-2k | <https://huggingface.co/NeoQuasar/Kronos-Tokenizer-2k> |

**Key API used by the benchmark** (all in the repo's `model/kronos.py`):
- `KronosTokenizer.from_pretrained(...)` — BSQ tokenizer (hierarchical `s1`/`s2` bits).
- `Kronos.from_pretrained(...)` — the autoregressive Transformer.
- `KronosPredictor(model, tokenizer, device=..., max_context=...)` →
  `.predict(df, x_timestamp, y_timestamp, pred_len, T, top_k, top_p, sample_count)` —
  takes an OHLCV `df` (`open, high, low, close[, volume, amount]`), returns forecast
  OHLCV. The benchmark feeds a **degenerate bar** (`open=high=low=close=volume`) and
  reads back `close` as the volume forecast (assumption **A1**).

**Fine-tuning (for a fair A2)** — the repo's `finetune/` pipeline:
- `finetune/qlib_data_preprocess.py` — data prep.
- `finetune/train_tokenizer.py` — stage-1 tokenizer fine-tune (`torchrun`, multi-GPU).
- `finetune/train_predictor.py` — stage-2 predictor fine-tune.
- `finetune/qlib_test.py` — backtest/eval.

**Runtime deps** (from the repo's `requirements.txt`): `torch>=2.0`, `numpy`,
`pandas`, `einops`, `huggingface_hub`, `safetensors`, `tqdm`.

> Kronos's intended domain is **high-frequency financial / price-volume** series.
> This folder assesses re-purposing it for **monthly retail SKU volume** — a
> different problem class (see `kronos-fit-assessment.md`).

## Recommended alternative methods (the GO candidates)

| Tool | Link | Role here |
|---|---|---|
| Nixtla **statsforecast** | <https://github.com/Nixtla/statsforecast> | AutoETS / AutoARIMA / Theta / SeasonalNaive; **Croston/TSB** for intermittent demand. |
| Nixtla **mlforecast** | <https://github.com/Nixtla/mlforecast> | LightGBM + lag/calendar features. |
| **TimesFM** (Google) | <https://github.com/google-research/timesfm> | General-purpose TS foundation model (the fair FM comparison). |
| **Chronos** (Amazon) | <https://github.com/amazon-science/chronos-forecasting> | Alt TS foundation model. |
| **Moirai** / uni2ts (Salesforce) | <https://github.com/SalesforceAIResearch/uni2ts> | Alt TS foundation model. |
| Hierarchical reconciliation (**HierarchicalForecast**) | <https://github.com/Nixtla/hierarchicalforecast> | MinT across `sku → category → total`. |

## Databricks / platform

| Resource | Link |
|---|---|
| **Many Model Forecasting (MMF)** — Databricks industry solution | <https://github.com/databricks-industry-solutions/many-model-forecasting> |
| Time-series forecasting with generative AI (Databricks blog) | <https://www.databricks.com/blog/introduction-time-series-forecasting-generative-ai> |
| Unity Catalog | <https://learn.microsoft.com/azure/databricks/data-governance/unity-catalog/> |
| Notebook-scoped `%pip` libraries | <https://learn.microsoft.com/azure/databricks/libraries/notebooks-python-libraries> |
| Databricks widgets | <https://learn.microsoft.com/azure/databricks/notebooks/widgets> |

## Metric

- **WMAPE** (weighted mean absolute percentage error) = `Σ|yₜ − ŷₜ| / Σ|yₜ|` over the
  scored `(sku, month)` pairs, per horizon — the contract metric.
