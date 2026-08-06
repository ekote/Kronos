"""
Open Mercato → Azure Event Hubs bridge (decoupled webhook).

An alternative to the in-process Node subscriber: a tiny HTTP service that
receives Open Mercato webhooks (or outbox deliveries) and forwards the canonical
event to Azure Event Hubs. Language-agnostic and isolated from the app — good as
an Azure Function or a small container.

Run (local):
    pip install flask azure-eventhub azure-identity
    EVENTHUBS_FQDN=<ns>.servicebus.windows.net EVENTHUBS_NAME=commerce-events \
        python webhook_to_eventhubs.py
Point an Open Mercato webhook for order.created / order.paid at POST /om/events.

Auth: DefaultAzureCredential (managed identity in Azure). Grant the identity
"Azure Event Hubs Data Sender". Verify the webhook signature in production.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from flask import Flask, request, jsonify
from azure.identity import DefaultAzureCredential
from azure.eventhub import EventHubProducerClient, EventData

FQDN = os.environ["EVENTHUBS_FQDN"]
HUB = os.environ.get("EVENTHUBS_NAME", "commerce-events")

app = Flask(__name__)
_producer = EventHubProducerClient(
    fully_qualified_namespace=FQDN, eventhub_name=HUB, credential=DefaultAzureCredential())

_FORWARD = {"order.created", "order.paid"}


def to_bridge_event(name: str, e: dict) -> dict | None:
    """Map an Open Mercato domain event to the canonical bridge payload."""
    if name not in _FORWARD:
        return None
    return {
        "tenant_id": e.get("organizationId") or e.get("tenantId") or "unknown",
        "event": name,
        "event_time": e.get("createdAt") or datetime.now(timezone.utc).isoformat(),
        "order_id": e.get("id") or e.get("orderId"),
        "amount": float(e.get("total", e.get("amount", 0)) or 0),
        "currency": e.get("currency", "USD"),
        "units": int(e.get("itemCount", e.get("units", 1)) or 1),
        "channel": e.get("channel", "web"),
    }


@app.post("/om/events")
def receive():
    body = request.get_json(force=True, silent=True) or {}
    name = body.get("event") or body.get("type") or ""
    payload = body.get("data") or body.get("payload") or body
    evt = to_bridge_event(name, payload)
    if evt is None:
        return jsonify({"status": "ignored", "event": name}), 202

    # Partition by tenant to preserve per-merchant ordering downstream.
    batch = _producer.create_batch(partition_key=evt["tenant_id"])
    batch.add(EventData(json.dumps(evt)))
    _producer.send_batch(batch)
    return jsonify({"status": "forwarded", "event": name}), 200


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
