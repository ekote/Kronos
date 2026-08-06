/**
 * Open Mercato → Azure Event Hubs bridge (native subscriber).
 *
 * Open Mercato publishes domain events processed by persistent subscribers
 * (local or Redis). This is a reference subscriber that forwards commerce events
 * (order.*, sales.*, inventory.*) to Azure Event Hubs, from which Fabric
 * Eventstream / Azure Data Explorer ingest them.
 *
 * Wiring: place under `src/modules/<yourmodule>/subscribers/` and register it the
 * way your Open Mercato version registers event subscribers (the framework
 * auto-discovers module subscribers). The mapping + producer below are the parts
 * you keep; adapt only the registration signature to your version.
 *
 * Auth: DefaultAzureCredential (managed identity in Azure; az login locally) — no
 * connection string in code. Grant the identity "Azure Event Hubs Data Sender".
 *
 * deps: @azure/event-hubs @azure/identity
 */
import { EventHubProducerClient } from "@azure/event-hubs";
import { DefaultAzureCredential } from "@azure/identity";

const FQNS = process.env.EVENTHUBS_FQDN!;          // e.g. kronos-ehns.servicebus.windows.net
const HUB = process.env.EVENTHUBS_NAME ?? "market-ticks"; // reuse or use "commerce-events"

const producer = new EventHubProducerClient(FQNS, HUB, new DefaultAzureCredential());

/** Canonical payload the Azure side expects (see architecture.md §3). */
type BridgeEvent = {
  tenant_id: string;
  event: string;
  event_time: string; // ISO-8601 UTC
  order_id?: string;
  amount?: number;
  currency?: string;
  units?: number;
  channel?: string;
};

/** Map an Open Mercato domain event to the canonical bridge payload. */
function toBridgeEvent(name: string, e: any): BridgeEvent | null {
  // Only forward the events that drive demand bars; ignore the rest.
  if (!/^order\.(created|paid)$/.test(name)) return null;
  return {
    tenant_id: e.organizationId ?? e.tenantId ?? "unknown",
    event: name,
    event_time: (e.createdAt ?? new Date().toISOString()),
    order_id: e.id ?? e.orderId,
    amount: Number(e.total ?? e.amount ?? 0),
    currency: e.currency ?? "USD",
    units: Number(e.itemCount ?? e.units ?? 1),
    channel: e.channel ?? "web",
  };
}

/**
 * Subscriber entry point. Open Mercato calls your subscriber with (eventName,
 * payload); the exact signature depends on your version — adapt this wrapper,
 * keep the mapping + send.
 */
export async function handleOpenMercatoEvent(eventName: string, payload: any): Promise<void> {
  const evt = toBridgeEvent(eventName, payload);
  if (!evt) return;
  // Partition by tenant so per-merchant ordering is preserved end-to-end.
  const batch = await producer.createBatch({ partitionKey: evt.tenant_id });
  batch.tryAdd({ body: evt });
  await producer.sendBatch(batch);
}

// For a high-throughput store, buffer events and flush in batches instead of one
// send per event (createBatch loop with a timer). Kept 1:1 here for clarity.

process.on("SIGTERM", async () => { await producer.close(); process.exit(0); });
