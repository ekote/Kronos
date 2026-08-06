# Open Mercato → Azure Event Hubs bridge

The one genuinely new component versus the markets solution: a small forwarder
that turns **Open Mercato domain events** into a stream on **Azure Event Hubs**,
from which Fabric Eventstream or Azure Data Explorer ingest them.

Two references — pick by how coupled you want to be:

| File | Style | When to use |
|---|---|---|
| `openmercato-eventhubs-subscriber.ts` | **Native** in-process Open Mercato event subscriber (Node/TS) | You own the Open Mercato app and want the lowest-latency, no-extra-service path. |
| `webhook_to_eventhubs.py` | **Decoupled** webhook receiver (Python; Azure Function/container) | You want isolation, a different language, or can't add in-process subscribers. |

Both emit the **same canonical payload** (tenant-scoped) that the rest of the
solution expects:

```json
{ "tenant_id": "t_123", "event": "order.paid", "event_time": "2025-03-03T14:00:05Z",
  "order_id": "o_987", "amount": 128.40, "currency": "USD", "units": 3, "channel": "web" }
```

## Auth & security

- **No secrets in code.** Both use `DefaultAzureCredential`; grant the identity the
  **Azure Event Hubs Data Sender** role. Locally, `az login` works.
- **Partition by `tenant_id`** so each merchant's events stay ordered and isolated
  end-to-end (bars and forecasts inherit the isolation).
- **PII:** order events may carry PII. Forward only what the bars need (amount,
  units, channel, ids) — not customer fields. Verify webhook signatures in prod.

## Adapting to your Open Mercato version

The event field names (`organizationId`, `total`, `itemCount`, `createdAt`) are
mapped in `toBridgeEvent` / `to_bridge_event` — adjust them to your entities. The
subscriber **registration** signature differs by Open Mercato version; keep the
mapping + producer, adapt only how the framework hands you `(eventName, payload)`.

See [`../../../docs/openmercato-azure/architecture.md`](../../../docs/openmercato-azure/architecture.md) §3.
