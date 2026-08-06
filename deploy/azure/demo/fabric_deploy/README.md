# Deploy + run the demo in Microsoft Fabric

One command provisions an Eventhouse and replays the whole Kronos demo into it:

```bash
pip install -r requirements-deploy.txt
cp .env.example .env            # fill in (non-secret values only)
python deploy_to_fabric.py --dry-run    # print the plan + KQL, no network
python deploy_to_fabric.py              # actually deploy
```

## What it does — and deliberately doesn't

**Does** (the durable, scriptable part):
1. Auth via `DefaultAzureCredential` (device-code interactively, or a service
   principal from env vars in CI).
2. Ensure a Fabric **workspace → Eventhouse → KQL database** (create if missing).
3. Run the offline demo, then execute the emitted KQL against the KQL database:
   tables, the `candles_1m` materialized view (backfill), `forecasts`,
   `signals`, `model_health_alerts`.
4. Run verify queries; print row counts and the Eventhouse query URI.

**Does not**: auto-create the Real-Time Dashboard tiles or the Data Activator
rule. Fabric's public REST for those is preview-grade and changes often —
scripting them is a maintenance liability, so the script prints the ready-made
KQL and a one-time manual step instead. If you want those automated anyway, say
so and it can be added (accepting the churn).

## Prerequisites (the script can't create these)

- A **Fabric capacity** (F-SKU or Trial) — set `FABRIC_CAPACITY_ID` to create a
  new workspace, or point `FABRIC_WORKSPACE_ID` at an existing one that already
  has capacity.
- An identity with **workspace Admin/Member** rights and, for the KQL load,
  **Database Admin** on the KQL database.
- Fabric REST APIs must be enabled for your tenant/principal.

If any are missing the script fails fast with a specific message.

## Configuration options (pick what fits)

| Option | Config lives in | Secret handling | Best for |
|---|---|---|---|
| **`.env` + `DefaultAzureCredential`** (default here) | `.env` (gitignored) | none in file — interactive/device-code or env-var SP | laptops, first run |
| **Env vars only** | shell / CI secret store | `AZURE_*` injected at runtime | CI/CD pipelines |
| **`.env` with plaintext SP secret** | `.env` | secret in file (opt-in, insecure) | quick throwaway only |
| **Terraform / `azd` / Fabric deployment pipelines** | IaC repo | provider-managed | teams standardizing infra |

Recommendation: **`.env` for non-secret IDs, `DefaultAzureCredential` for auth.**
Never commit a client secret. For repeatable team infra, graduate to Terraform
(the Fabric/AzAPI providers) or Fabric Git-integration deployment pipelines —
this script is for a fast, reproducible single-tenant demo, not fleet infra.

## `.env` keys

See [`.env.example`](./.env.example). Summary:

- `FABRIC_WORKSPACE_NAME` / `FABRIC_WORKSPACE_ID` / `FABRIC_CAPACITY_ID`
- `EVENTHOUSE_NAME` / `KQL_DATABASE_NAME`
- `DEMO_SYMBOL`, `DEMO_LOOKBACK`, `DEMO_PRED_LEN`, `DEMO_STRIDE`, `EMIT_TICKS`
- Auth: leave SP fields blank for interactive login (recommended)

## Flags

- `--dry-run` — print the plan and command breakdown; **no network calls** (works
  with zero cloud deps installed).
- `--skip-provision` — reuse an existing workspace/eventhouse/db from `.env`.
- `--no-ticks` — skip the large raw-tick replay; candles build from a lighter load.

## After it runs

The script prints the query URI and the two manual steps:

- **Real-Time Dashboard** — new tile → `DashActualVsForecast('BTCUSDT', 400)`
  (defined in [`../../fabric/eventhouse/03_forecast_dashboard_activator.kql`](../../fabric/eventhouse/03_forecast_dashboard_activator.kql)).
- **Data Activator** — new reflex on `model_health_alerts` → alert on new rows.

## Note on real Kronos vs the baseline

This deploys the **demo**, which uses the baseline forecaster — no GPU, no Azure
ML. Standing up the real Kronos model is a separate concern (Azure ML online
endpoint; see [`../../azureml/`](../../azureml/)); the Fabric side here is
identical either way, since both write the same `forecasts` schema.
