# References & further reading

Public, authoritative sources for every building block in this solution. Each
row maps a concept **as used here** to its official documentation (Microsoft
Learn) or upstream project (GitHub / Hugging Face / arXiv).

> Links verified against live Microsoft Learn results. Microsoft Learn URLs
> auto-redirect to your locale and occasionally reorganize — if one moves, search
> the exact page title on <https://learn.microsoft.com>.

---

## Kronos — the model

| Concept | Where it's used here | Reference |
|---|---|---|
| Kronos foundation model (source + docs) | The forecasting model in `model/` | GitHub: <https://github.com/shiyu-coder/Kronos> |
| Kronos paper (method, training, results) | Background for the model plane | arXiv 2508.02739: <https://arxiv.org/abs/2508.02739> |
| Pre-trained weights | Loaded by `score.py` / `KronosPredictor` | Hugging Face: <https://huggingface.co/NeoQuasar> |
| ↳ Kronos-base / small / mini | Model-family table | <https://huggingface.co/NeoQuasar/Kronos-base> · <https://huggingface.co/NeoQuasar/Kronos-small> · <https://huggingface.co/NeoQuasar/Kronos-mini> |
| ↳ Tokenizers (base / 2k) | Stage-1 tokenizer | <https://huggingface.co/NeoQuasar/Kronos-Tokenizer-base> · <https://huggingface.co/NeoQuasar/Kronos-Tokenizer-2k> |
| Qlib (fine-tune data example) | `finetune/` pipeline | GitHub: <https://github.com/microsoft/qlib> |

## Microsoft Fabric — Real-Time Intelligence (the data plane)

| Concept | Where it's used here | Reference |
|---|---|---|
| Real-Time Intelligence overview | The whole Fabric side | <https://learn.microsoft.com/fabric/real-time-intelligence/overview> |
| RTI documentation (root) | — | <https://learn.microsoft.com/fabric/real-time-intelligence/> |
| Eventstream (ingest/route/transform) | Stage 1 ingestion | <https://learn.microsoft.com/fabric/real-time-intelligence/event-streams/overview> |
| Eventhouse (KQL database) | `ticks_raw`, `forecasts`, `signals`, `model_health_alerts` | <https://learn.microsoft.com/fabric/real-time-intelligence/eventhouse> |
| Materialized views | `candles_1m` / `candles_5m` OHLCV | <https://learn.microsoft.com/fabric/real-time-intelligence/materialized-view> |
| Get data from Azure Event Hubs | Feed → Eventhouse | <https://learn.microsoft.com/fabric/real-time-intelligence/get-data-event-hub> |
| Query with KQL (tutorial) | Lookback + dashboard queries | <https://learn.microsoft.com/fabric/real-time-intelligence/tutorial-5-query-data> |
| Kusto Query Language (KQL) reference | All `.kql` scripts | <https://learn.microsoft.com/kusto/query/> |
| Real-Time Dashboard | Actual-vs-forecast visuals | <https://learn.microsoft.com/fabric/real-time-intelligence/tutorial-6-create-dashboard> |
| Data Activator (Activator) | Signals + model-health alerts | <https://learn.microsoft.com/fabric/real-time-intelligence/data-activator/> |
| Medallion in RTI (bronze/silver/gold) | Raw ticks → candles → forecasts | <https://learn.microsoft.com/fabric/real-time-intelligence/architecture-medallion> |
| OneLake (unified data lake) | Shared data + model substrate | <https://learn.microsoft.com/fabric/onelake/onelake-overview> |
| OneLake ↔ Azure ML integration | Training data / model artifacts | <https://learn.microsoft.com/fabric/onelake/onelake-azure-machine-learning> |
| Fabric REST APIs | `deploy_to_fabric.py` provisioning | <https://learn.microsoft.com/rest/api/fabric/articles/using-fabric-apis> |
| Fabric Git integration / CI-CD | Deploying Fabric items | <https://learn.microsoft.com/fabric/cicd/git-integration/intro-to-git-integration> |

## Azure — the model & platform plane

| Concept | Where it's used here | Reference |
|---|---|---|
| Azure ML online endpoints (concept) | Serving Kronos (GPU) | <https://learn.microsoft.com/azure/machine-learning/concept-endpoints-online?view=azureml-api-2> |
| Deploy to online endpoints (how-to) | `endpoint.yml` / `deployment.yml` | <https://learn.microsoft.com/azure/machine-learning/how-to-deploy-online-endpoints?view=azureml-api-2> |
| Identity-based auth for Azure ML | Managed identity between planes | <https://learn.microsoft.com/azure/machine-learning/how-to-identity-based-service-authentication?view=azureml-api-2> |
| MLflow in Azure ML | Fine-tune tracking / registry | <https://learn.microsoft.com/azure/machine-learning/concept-mlflow?view=azureml-api-2> |
| Azure Event Hubs | Market-feed ingestion | <https://learn.microsoft.com/azure/event-hubs/> |
| Azure Key Vault | Secrets for the deployer/orchestrator | <https://learn.microsoft.com/azure/key-vault/> |
| Azure Monitor | Endpoint/pipeline observability | <https://learn.microsoft.com/azure/azure-monitor/fundamentals/overview> |
| Bicep (IaC) | `infra/main.bicep` | <https://learn.microsoft.com/azure/azure-resource-manager/bicep/overview> |

## Tooling used by the deployer

| Concept | Where it's used here | Reference |
|---|---|---|
| `azure-identity` (DefaultAzureCredential) | Auth in `deploy_to_fabric.py` | GitHub: <https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/identity/azure-identity> |
| `azure-kusto-python` (Kusto SDK) | Running KQL against the Eventhouse | GitHub: <https://github.com/Azure/azure-kusto-python> |

---

*This solution is a reference architecture using open-source Kronos on supported
Azure & Fabric services. It is not a Microsoft product and is not financial
advice — see the customer primer and seller guide for framing.*
