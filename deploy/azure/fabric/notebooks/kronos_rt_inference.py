"""
Fabric notebook / Spark Job — Kronos real-time inference orchestrator.

Runs on a schedule (e.g. every 1 minute) or on a closed-candle trigger. It:
  1. Reads the latest `LOOKBACK` closed candles per symbol from the Eventhouse
     (KQL function KronosLookbackUniverse).
  2. Builds a predict_batch payload and calls the Azure ML online endpoint.
  3. Writes forecasts back into the Eventhouse `forecasts` table.

Auth uses the Fabric workspace managed identity; the endpoint key is read from
Key Vault. Replace the placeholders marked TODO for your environment.

This file is written as a plain .py so it lives in git; paste cells into a Fabric
notebook or register it as a Spark Job Definition.
"""
import json
import uuid
import datetime as dt

import requests
import pandas as pd

# Fabric provides these helpers in the notebook runtime.
# from notebookutils import mssparkutils  # noqa
# from sempy import fabric               # for KQL query helpers, if preferred

# ---- Configuration ----------------------------------------------------------
KQL_CLUSTER = "https://<eventhouse>.kusto.fabric.microsoft.com"   # TODO
KQL_DATABASE = "kronos_rt"                                        # TODO
AML_ENDPOINT_URI = "https://kronos-forecast.<region>.inference.ml.azure.com/score"  # TODO
KEYVAULT_URI = "https://<vault>.vault.azure.net/"                 # TODO
KEYVAULT_SECRET = "kronos-endpoint-key"                          # TODO

LOOKBACK = 400
PRED_LEN = 120
BAR = "1m"
SAMPLING = {"T": 1.0, "top_p": 0.9, "top_k": 0, "sample_count": 1}


# ---- Helpers ----------------------------------------------------------------
def kql_query(query: str) -> pd.DataFrame:
    """Execute a KQL query against the Eventhouse and return a DataFrame.

    In Fabric use the Kusto Python SDK with AAD device/managed-identity auth:
        from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
        from azure.kusto.data.helpers import dataframe_from_result_table
    """
    from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
    from azure.kusto.data.helpers import dataframe_from_result_table

    kcsb = KustoConnectionStringBuilder.with_aad_managed_service_identity_authentication(KQL_CLUSTER)
    client = KustoClient(kcsb)
    resp = client.execute(KQL_DATABASE, query)
    return dataframe_from_result_table(resp.primary_results[0])


def kql_ingest(df: pd.DataFrame, table: str, mapping: str) -> None:
    """Inline-ingest a small DataFrame into an Eventhouse table via `.ingest inline`.

    For higher volumes, queue ingestion via the Kusto ingest client instead.
    """
    from azure.kusto.data import KustoClient, KustoConnectionStringBuilder

    kcsb = KustoConnectionStringBuilder.with_aad_managed_service_identity_authentication(KQL_CLUSTER)
    client = KustoClient(kcsb)
    rows = "\n".join(df.to_csv(index=False, header=False).splitlines())
    cmd = f".ingest inline into table {table} with (format='csv', ingestionMappingReference='{mapping}') <|\n{rows}"
    client.execute_mgmt(KQL_DATABASE, cmd)


def get_endpoint_key() -> str:
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    cred = DefaultAzureCredential()
    return SecretClient(vault_url=KEYVAULT_URI, credential=cred).get_secret(KEYVAULT_SECRET).value


def future_timestamps(last_ts: pd.Timestamp, step: pd.Timedelta, n: int) -> list[str]:
    return [(last_ts + step * i).isoformat() for i in range(1, n + 1)]


# ---- Main orchestration -----------------------------------------------------
def main():
    run_id = str(uuid.uuid4())
    run_time = dt.datetime.utcnow()

    # 1. Pull the universe lookback window in a single KQL call.
    lookback = kql_query(f"KronosLookbackUniverse({LOOKBACK})")
    if lookback.empty:
        print("No candles available yet; skipping run.")
        return

    step = pd.Timedelta(BAR)
    series = []
    for symbol, g in lookback.groupby("symbol"):
        g = g.sort_values("event_time")
        if len(g) < LOOKBACK:
            continue  # not enough history yet for this symbol
        last_ts = pd.Timestamp(g["event_time"].iloc[-1])
        series.append({
            "symbol": symbol,
            "timestamps": [pd.Timestamp(t).isoformat() for t in g["event_time"]],
            "ohlcv": g[["open", "high", "low", "close", "volume", "amount"]].values.tolist(),
            "future_timestamps": future_timestamps(last_ts, step, PRED_LEN),
        })

    if not series:
        print("No symbol has a full lookback window; skipping run.")
        return

    # 2. Call the Azure ML endpoint (batch all symbols in one request).
    body = {"pred_len": PRED_LEN, "sampling": SAMPLING, "series": series}
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {get_endpoint_key()}"}
    resp = requests.post(AML_ENDPOINT_URI, headers=headers, data=json.dumps(body), timeout=120)
    resp.raise_for_status()
    out = resp.json()
    model_version = out.get("model_version", "unknown")

    # 3. Flatten forecasts and write back to the Eventhouse.
    records = []
    for item in out["results"]:
        for f in item["forecast"]:
            records.append({
                "symbol": item["symbol"],
                "run_id": run_id,
                "run_time": run_time.isoformat(),
                "target_time": f["target_time"],
                "open": f["open"], "high": f["high"], "low": f["low"], "close": f["close"],
                "volume": f["volume"], "amount": f["amount"],
                "horizon_step": f["horizon_step"],
                "model_version": model_version,
                "sampling": json.dumps(SAMPLING),
            })

    forecasts_df = pd.DataFrame(records)
    kql_ingest(forecasts_df, table="forecasts", mapping="forecasts_map")
    print(f"Wrote {len(forecasts_df)} forecast rows for {len(series)} symbols (run_id={run_id}).")


if __name__ == "__main__":
    main()
