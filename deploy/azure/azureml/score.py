"""
Azure ML managed online endpoint scoring script for Kronos.

Loads the Kronos tokenizer + model once in init() and serves multi-symbol
forecasts via KronosPredictor.predict_batch(). Designed to be invoked by the
Fabric orchestrator (see deploy/azure/fabric/notebooks/kronos_rt_inference.py).

Request body (JSON):
{
  "pred_len": 120,
  "sampling": {"T": 1.0, "top_p": 0.9, "top_k": 0, "sample_count": 1},
  "series": [
    {
      "symbol": "BTCUSDT",
      "timestamps": ["2025-01-01T00:00:00Z", ...],   # lookback timestamps
      "ohlcv": [[open, high, low, close, volume, amount], ...],  # same length
      "future_timestamps": ["...", ...]              # length == pred_len
    },
    ...
  ]
}

Response (JSON): {"model_version": "...", "results": [{"symbol": ..., "forecast": [...]}]}
"""
import os
import json
import logging

import numpy as np
import pandas as pd

from model import Kronos, KronosTokenizer, KronosPredictor

logger = logging.getLogger("kronos-score")

# Environment-configurable model selection (defaults to the base model).
TOKENIZER_ID = os.getenv("KRONOS_TOKENIZER_ID", "NeoQuasar/Kronos-Tokenizer-base")
MODEL_ID = os.getenv("KRONOS_MODEL_ID", "NeoQuasar/Kronos-base")
MAX_CONTEXT = int(os.getenv("KRONOS_MAX_CONTEXT", "512"))
MODEL_VERSION = os.getenv("KRONOS_MODEL_VERSION", MODEL_ID)

_predictor: KronosPredictor = None
_OHLCV_COLS = ["open", "high", "low", "close", "volume", "amount"]


def init():
    """Load model + tokenizer once per worker."""
    global _predictor
    import torch

    # AZUREML_MODEL_DIR is set when the model is mounted from the registry;
    # fall back to the HF hub id for local / bootstrap runs.
    model_dir = os.getenv("AZUREML_MODEL_DIR")
    tok_src = os.path.join(model_dir, "tokenizer") if model_dir else TOKENIZER_ID
    mdl_src = os.path.join(model_dir, "predictor") if model_dir else MODEL_ID
    if model_dir and not os.path.isdir(tok_src):
        tok_src, mdl_src = TOKENIZER_ID, MODEL_ID  # registry holds only metadata

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    logger.info("Loading Kronos tokenizer=%s model=%s on %s", tok_src, mdl_src, device)

    tokenizer = KronosTokenizer.from_pretrained(tok_src)
    model = Kronos.from_pretrained(mdl_src)
    _predictor = KronosPredictor(model, tokenizer, device=device, max_context=MAX_CONTEXT)
    logger.info("Kronos predictor ready (device=%s, max_context=%d)", device, MAX_CONTEXT)


def run(raw_data):
    """Score a batch of symbols in a single GPU pass."""
    payload = json.loads(raw_data) if isinstance(raw_data, (str, bytes)) else raw_data
    pred_len = int(payload["pred_len"])
    s = payload.get("sampling", {})
    T = float(s.get("T", 1.0))
    top_p = float(s.get("top_p", 0.9))
    top_k = int(s.get("top_k", 0))
    sample_count = int(s.get("sample_count", 1))

    series = payload["series"]
    df_list, x_ts_list, y_ts_list, symbols = [], [], [], []
    for item in series:
        df = pd.DataFrame(item["ohlcv"], columns=_OHLCV_COLS)
        df_list.append(df)
        x_ts_list.append(pd.Series(pd.to_datetime(item["timestamps"])))
        y_ts_list.append(pd.Series(pd.to_datetime(item["future_timestamps"])))
        symbols.append(item["symbol"])

    # predict_batch requires equal lookback + pred_len across the batch; the
    # orchestrator enforces this by construction (fixed lookback / horizon).
    preds = _predictor.predict_batch(
        df_list=df_list,
        x_timestamp_list=x_ts_list,
        y_timestamp_list=y_ts_list,
        pred_len=pred_len,
        T=T,
        top_k=top_k,
        top_p=top_p,
        sample_count=sample_count,
        verbose=False,
    )

    results = []
    for symbol, y_ts, pred_df in zip(symbols, y_ts_list, preds):
        forecast = []
        for step, (ts, row) in enumerate(zip(y_ts, pred_df.itertuples(index=False)), start=1):
            forecast.append({
                "target_time": pd.Timestamp(ts).isoformat(),
                "horizon_step": step,
                "open": float(row.open), "high": float(row.high),
                "low": float(row.low), "close": float(row.close),
                "volume": float(getattr(row, "volume", 0.0)),
                "amount": float(getattr(row, "amount", 0.0)),
            })
        results.append({"symbol": symbol, "forecast": forecast})

    return {
        "model_version": MODEL_VERSION,
        "sampling": {"T": T, "top_p": top_p, "top_k": top_k, "sample_count": sample_count},
        "results": results,
    }
