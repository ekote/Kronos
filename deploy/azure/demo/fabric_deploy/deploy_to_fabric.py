"""
Deploy + run the Kronos demo in Microsoft Fabric.

What it does (the durable, scriptable part of the architecture):
  1. Authenticates with azure-identity (device-code interactively, or a service
     principal from env vars in CI — no secret needs to live in a file).
  2. Ensures a Fabric workspace, an Eventhouse, and its KQL database (creates
     them if missing; a Fabric capacity must already be assigned).
  3. Runs the offline demo to produce the pipeline result.
  4. Executes the emitted KQL against the KQL database — tables, the candles_1m
     materialized view (backfill), forecasts, signals, model_health_alerts.
  5. Runs verify queries and prints row counts + the Eventhouse query URI.

What it deliberately does NOT do (Fabric's public API for these is preview and
churns — scripting them is a maintenance liability): auto-create the Real-Time
Dashboard tiles or the Data Activator rule. It prints the ready-made KQL and a
one-time manual step for those instead.

Usage:
    pip install -r requirements-deploy.txt
    cp .env.example .env    # fill in
    python deploy_to_fabric.py --dry-run     # print the full plan, no network
    python deploy_to_fabric.py               # actually deploy

Config comes from .env (see .env.example). Auth uses DefaultAzureCredential.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

# Make the demo package importable (parent dir).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FABRIC_API = "https://api.fabric.microsoft.com/v1"
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"


# --------------------------------------------------------------------------- #
# config
# --------------------------------------------------------------------------- #
def load_env(path=".env"):
    """Tiny .env loader — no dependency. Does not override real env vars."""
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    if os.path.exists(here):
        for line in open(here):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def cfg(name, default=None, required=False):
    v = os.environ.get(name, default)
    if required and not v:
        sys.exit(f"ERROR: {name} is required (set it in .env or the environment).")
    return v


# --------------------------------------------------------------------------- #
# auth
# --------------------------------------------------------------------------- #
def get_credential():
    from azure.identity import DefaultAzureCredential, DeviceCodeCredential, ClientSecretCredential

    # Opt-in plaintext SP from .env (last resort).
    if cfg("FABRIC_SP_CLIENT_SECRET"):
        print("· auth: service principal from .env (plaintext secret)")
        return ClientSecretCredential(
            tenant_id=cfg("FABRIC_SP_TENANT_ID", required=True),
            client_id=cfg("FABRIC_SP_CLIENT_ID", required=True),
            client_secret=cfg("FABRIC_SP_CLIENT_SECRET"))
    try:
        cred = DefaultAzureCredential(exclude_interactive_browser_credential=False)
        cred.get_token(FABRIC_SCOPE)  # probe
        print("· auth: DefaultAzureCredential (env SP / Azure CLI / managed identity)")
        return cred
    except Exception:
        print("· auth: falling back to device-code login")
        return DeviceCodeCredential()


# --------------------------------------------------------------------------- #
# Fabric REST
# --------------------------------------------------------------------------- #
class Fabric:
    def __init__(self, credential):
        import requests
        self._s = requests.Session()
        self._cred = credential

    def _tok(self):
        return self._cred.get_token(FABRIC_SCOPE).token

    def _req(self, method, path, **kw):
        url = path if path.startswith("http") else f"{FABRIC_API}{path}"
        h = kw.pop("headers", {})
        h["Authorization"] = f"Bearer {self._tok()}"
        r = self._s.request(method, url, headers=h, **kw)
        return r

    def _lro(self, r):
        """Resolve a long-running-operation response to its final resource."""
        if r.status_code in (200, 201):
            return r.json() if r.text else {}
        if r.status_code == 202:
            op = r.headers.get("Location")
            for _ in range(60):
                time.sleep(int(r.headers.get("Retry-After", 3)))
                s = self._req("GET", op)
                state = (s.json() or {}).get("status", "") if s.text else ""
                if s.status_code == 200 and state.lower() in ("succeeded", ""):
                    res = self._req("GET", op + "/result")
                    return res.json() if res.text else s.json()
                if state.lower() == "failed":
                    sys.exit(f"ERROR: Fabric operation failed: {s.text}")
                r = s
        r.raise_for_status()
        return r.json() if r.text else {}

    def find_workspace(self, name, ws_id):
        if ws_id:
            return ws_id
        r = self._req("GET", "/workspaces")
        r.raise_for_status()
        for w in r.json().get("value", []):
            if w.get("displayName") == name:
                return w["id"]
        return None

    def create_workspace(self, name, capacity_id):
        if not capacity_id:
            sys.exit("ERROR: workspace not found and FABRIC_CAPACITY_ID is empty — "
                     "assign a Fabric capacity (F-SKU/Trial) or set FABRIC_WORKSPACE_ID.")
        body = {"displayName": name, "capacityId": capacity_id}
        res = self._lro(self._req("POST", "/workspaces", json=body))
        return res["id"]

    def find_item(self, ws, kind, name):
        r = self._req("GET", f"/workspaces/{ws}/items?type={kind}")
        r.raise_for_status()
        for it in r.json().get("value", []):
            if it.get("displayName") == name:
                return it
        return None

    def ensure_eventhouse(self, ws, name):
        it = self.find_item(ws, "Eventhouse", name)
        if it:
            return it["id"]
        res = self._lro(self._req("POST", f"/workspaces/{ws}/eventhouses",
                                   json={"displayName": name}))
        return res["id"]

    def get_kql_database(self, ws, eventhouse_id, name):
        r = self._req("GET", f"/workspaces/{ws}/kqlDatabases")
        r.raise_for_status()
        dbs = r.json().get("value", [])
        for db in dbs:
            props = db.get("properties", {})
            if db.get("displayName") == name or props.get("parentEventhouseItemId") == eventhouse_id:
                return db
        # Create one bound to the eventhouse if none exists yet.
        body = {"displayName": name,
                "creationPayload": {"databaseType": "ReadWrite",
                                    "parentEventhouseItemId": eventhouse_id}}
        return self._lro(self._req("POST", f"/workspaces/{ws}/kqlDatabases", json=body))


# --------------------------------------------------------------------------- #
# Kusto (KQL DB) execution
# --------------------------------------------------------------------------- #
def kusto_client(query_uri, credential):
    from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
    kcsb = KustoConnectionStringBuilder.with_azure_token_credential(query_uri, credential)
    return KustoClient(kcsb)


def run_commands(client, db, commands, dry_run):
    counts = {}
    for stage, cmd in commands:
        counts[stage] = counts.get(stage, 0) + 1
        if dry_run:
            continue
        client.execute_mgmt(db, cmd)
    return counts


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def build_result():
    from synthetic import generate_session
    from forecaster import KronosAdapter
    from pipeline import run_pipeline
    candles, meta, ticks = generate_session(
        return_ticks=True, symbol=cfg("DEMO_SYMBOL", "BTCUSDT"))
    result = run_pipeline(
        candles, meta, KronosAdapter(),
        lookback=int(cfg("DEMO_LOOKBACK", "120")),
        pred_len=int(cfg("DEMO_PRED_LEN", "30")),
        stride=int(cfg("DEMO_STRIDE", "3")))
    result["ticks"] = ticks
    return result


def main():
    ap = argparse.ArgumentParser(description="Deploy + run the Kronos demo in Microsoft Fabric.")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the full plan and every KQL command; no network calls")
    ap.add_argument("--skip-provision", action="store_true",
                    help="use an existing workspace/eventhouse/db from .env; skip creation")
    ap.add_argument("--no-ticks", action="store_true",
                    help="skip the (large) raw-tick replay; candles built from a lighter load")
    args = ap.parse_args()

    load_env()
    from kql_emit import iter_commands, verify_queries

    symbol = cfg("DEMO_SYMBOL", "BTCUSDT")
    include_ticks = not args.no_ticks and cfg("EMIT_TICKS", "true").lower() == "true"

    print("\nKronos → Microsoft Fabric — deploy + run demo")
    print("=" * 60)
    result = build_result()
    s = result["stats"]
    print(f"· demo: {s['n_candles']} candles, {s['n_forecasts']} forecasts, "
          f"{s['n_signals']} signals, detection +{s['detection_latency_min']:.0f}m")

    commands = list(iter_commands(result, include_ticks=include_ticks))
    by_stage = {}
    for stg, _ in commands:
        by_stage[stg] = by_stage.get(stg, 0) + 1
    print(f"· KQL commands to run: {len(commands)}  {by_stage}")

    if args.dry_run:
        print("\n--- DRY RUN: plan ---")
        print(f"  workspace : {cfg('FABRIC_WORKSPACE_NAME')} (id={cfg('FABRIC_WORKSPACE_ID') or 'create'})")
        print(f"  eventhouse: {cfg('EVENTHOUSE_NAME')}")
        print(f"  database  : {cfg('KQL_DATABASE_NAME')}")
        print(f"  ticks     : {'yes' if include_ticks else 'no'}")
        print("\n--- first commands ---")
        for stg, cmd in commands[:4]:
            head = cmd.splitlines()[0][:96]
            print(f"  [{stg}] {head}{' …' if len(cmd) > 96 else ''}")
        print(f"  … and {max(0, len(commands)-4)} more")
        print("\nDry run complete — no network calls made.")
        return

    # Live path.
    cred = get_credential()
    fab = Fabric(cred)

    if args.skip_provision:
        ws = cfg("FABRIC_WORKSPACE_ID", required=True)
        eh_id = None
    else:
        ws = fab.find_workspace(cfg("FABRIC_WORKSPACE_NAME"), cfg("FABRIC_WORKSPACE_ID"))
        if not ws:
            ws = fab.create_workspace(cfg("FABRIC_WORKSPACE_NAME"), cfg("FABRIC_CAPACITY_ID"))
            print(f"· created workspace {ws}")
        else:
            print(f"· using workspace {ws}")
        eh_id = fab.ensure_eventhouse(ws, cfg("EVENTHOUSE_NAME"))
        print(f"· eventhouse {eh_id}")

    db = fab.get_kql_database(ws, eh_id, cfg("KQL_DATABASE_NAME"))
    props = db.get("properties", {})
    query_uri = props.get("queryServiceUri")
    db_name = props.get("databaseName") or cfg("KQL_DATABASE_NAME")
    if not query_uri:
        sys.exit(f"ERROR: could not resolve the KQL query URI. Raw item: {db}")
    print(f"· KQL database '{db_name}' @ {query_uri}")

    client = kusto_client(query_uri, cred)
    print(f"· executing {len(commands)} commands …")
    run_commands(client, db_name, commands, dry_run=False)

    print("\n--- verify ---")
    for label, q in verify_queries(symbol):
        try:
            rows = client.execute(db_name, q).primary_results[0]
            print(f"  {label:20s} {list(rows[0].to_dict().items()) if len(rows) else '(empty)'}")
        except Exception as e:
            print(f"  {label:20s} query failed: {e}")

    print("\nDone. Next (one-time, in the Fabric portal):")
    print(f"  • Real-Time Dashboard: new tile → run DashActualVsForecast('{symbol}', 400)")
    print("  • Data Activator: new reflex on model_health_alerts → alert on new rows")
    print(f"  • Query URI for tooling: {query_uri}")


if __name__ == "__main__":
    main()
