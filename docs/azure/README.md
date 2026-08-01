# Kronos on Azure — Microsoft Fabric Real-Time Intelligence

This folder contains a **reference solution and architecture** for running the
Kronos financial foundation model as a production, streaming forecasting service
on Microsoft Azure, using **Microsoft Fabric Real-Time Intelligence (RTI/RTA)**
as the data backbone and **Azure Machine Learning** as the GPU model plane.

## Start here

- **[kronos-on-azure-fabric-rta.md](./kronos-on-azure-fabric-rta.md)** — the full
  design: architecture diagram, component design, data flow, MLOps, sizing, and
  cross-cutting concerns (security, networking, cost, DR).

## Reference implementation

Concrete, staged scaffolding lives under [`deploy/azure/`](../../deploy/azure/):

| Path | What it is |
|---|---|
| `deploy/azure/fabric/eventhouse/01_raw_and_bronze.kql` | `ticks_raw` table + ingestion mapping + retention/caching |
| `deploy/azure/fabric/eventhouse/02_ohlcv_materialized_views.kql` | `candles_1m` / `candles_5m` materialized views + model lookback functions |
| `deploy/azure/fabric/eventhouse/03_forecast_dashboard_activator.kql` | `forecasts` table + dashboard queries + Data Activator signals |
| `deploy/azure/fabric/notebooks/kronos_rt_inference.py` | Orchestrator: Eventhouse → Azure ML endpoint → Eventhouse |
| `deploy/azure/azureml/score.py` | Endpoint scoring using `KronosPredictor.predict_batch` |
| `deploy/azure/azureml/endpoint.yml`, `deployment.yml`, `environment/conda.yml` | Managed online endpoint (GPU) |
| `deploy/azure/infra/main.bicep` | Event Hubs + Key Vault + Azure ML workspace skeleton |

## The 60-second version

```
Market feeds ─▶ Event Hubs ─▶ Fabric Eventstream ─▶ Eventhouse (ticks_raw)
                                                          │  materialized views
                                                          ▼
                                                   candles_1m / candles_5m
                                                          │  latest 400 candles
                                                          ▼
                        Fabric notebook ──invoke──▶ Azure ML GPU endpoint (Kronos)
                                     ▲                    │  forecast candles
                                     └────────────────────┘
                                                          ▼
                                            Eventhouse (forecasts)
                                              │                  │
                                              ▼                  ▼
                                   Real-Time Dashboard    Data Activator (alerts)
```

Fabric owns **data, time, and action**; Azure ML owns **the model (train +
serve)**. They meet at **OneLake** (data + model artifacts) and a thin,
idempotent invocation boundary. See the full doc for details.
