# Seller guide — Open Mercato × Kronos × Azure

*A field companion to `openmercato-deck.pdf` for Microsoft sellers / CSAs /
partners positioning the commerce variant. Use the deck to present; use this to
qualify, handle objections, and land consumption.*

> **What this is:** a **reference architecture and accelerator** that turns an
> open-source **Open Mercato** commerce event stream into **real-time demand
> forecasts + a model-health guardrail** using the open-source **Kronos** model on
> **Azure** (Fabric RTI or Azure-only). **Not** a Microsoft or Open Mercato
> product; **not** a sales-prediction guarantee. Position it as a repeatable
> *pattern* that drives Azure/Fabric consumption.

---

## The one-line pitch

**"Turn your storefront's live order stream into real-time demand forecasts you
can act on — with a built-in alarm for stockouts, outages, and fraud waves."**

Lead with the **real-time loop + guardrail**, not "we predict your sales." The
guardrail (auto-detecting when demand forecasts break) is the credible, ops-facing
hook. Demand accuracy is the demo; **trustworthy real-time operations** is the sale.

---

## Who to sell to (ideal customer profile)

Any customer with a **high-volume commerce/order stream and a need to act on it
now** — especially those running or evaluating Open Mercato (or any event-emitting
commerce/ERP).

| Strong fit | The signal that opens the door |
|---|---|
| Online retail / marketplaces / D2C at scale | "Our demand & ops signals are batch/end-of-day." |
| Businesses on Open Mercato or a headless commerce/ERP | "We already emit order/inventory events." |
| High-velocity events: flash sales, drops, peak seasons | "Peak events catch us unprepared; we react late." |
| Ops teams burned by stockouts / checkout outages / fraud | "We find out about incidents too slowly." |

**Disqualifiers / slow down:** customers expecting a guaranteed sales-forecasting
oracle (reset expectations — it's real-time ops + safety), or with no real-time
event source and no appetite to build one.

---

## The value, in the customer's words

1. **From end-of-day to real-time.** Demand forecasts on every minute of orders.
2. **Act, don't just chart.** Signals pre-warn ops to scale/pre-stock; alerts can
   trigger workflows **back in Open Mercato**.
3. **A safety net for AI in production.** The guardrail flags stockouts, checkout
   outages, and fraud waves automatically (~minutes). *This lands with ops/risk.*

---

## What lights up in Azure & Fabric (the consumption story)

One solution, **multiple meters** — and it works two ways:

| Component | Fabric option | Azure-only option | Consumption driver |
|---|---|---|---|
| Event bridge | Container / Function | Azure Function | small, always-on |
| Ingestion | Azure Event Hubs | Azure Event Hubs | events/sec, throughput units |
| Real-time store + bars + dashboards + alerts | **Fabric capacity (CUs)** | **Azure Data Explorer** cluster | tenants, query volume, users |
| Model serving | Azure ML online endpoint (GPU) | same | GPU instance hours |
| Fine-tuning | Azure ML GPU clusters | same | training job hours |
| Storage | OneLake | ADLS / storage | data volume |

**Talk track:** land it as **Fabric adoption** (Eventhouse + Real-Time Dashboard +
Data Activator) *or*, for non-Fabric shops, as **core Azure** (ADX + Functions) —
either way it's an **Azure ML attach** for serving and fine-tuning. Same KQL
either way, so the POC isn't wasted if they switch. Good for **Fabric adoption +
MACC/ACR** motions.

---

## Discovery questions

- How fresh are your demand/ops signals today — real-time or end-of-day?
- When a stockout, checkout outage, or fraud spike happens, **how fast do you find
  out**?
- Do you already emit order/inventory events (Open Mercato or otherwise)? Where do
  they land?
- Are you on Fabric, or would core Azure (ADX) fit your stack better?
- Do you have history to **fine-tune** a demand model on? Where would training run?
- Who owns ops/on-call and (for order PII) data protection?

---

## Objection handling

| Objection | Response |
|---|---|
| *"Can it predict my sales exactly?"* | No — and anyone promising that is overselling. It's real-time demand forecasting **plus** a guardrail that flags when it's wrong. The safety net is the differentiator. |
| *"Kronos is a stock-market model — why my store?"* | It's a time-series foundation model; your orders become OHLC "sales bars" (same shape). Zero-shot is a baseline; **fine-tune on your data** for accuracy. |
| *"We already have demand forecasting."* | Bring it — the value is the **managed real-time loop + guardrail**, not the model. Kronos is swappable. |
| *"We're not on Fabric."* | Fine — the Azure-only path (ADX + Functions) runs the **same KQL**. No Fabric required. |
| *"Why not build it ourselves?"* | This *is* the blueprint; the bridge + KQL + endpoint remove the plumbing. Weeks, not quarters. |

---

## Demo & assets to use

- **`openmercato-deck.pdf`** — the 8-slide story (open with this).
- **Live demo** — `run_openmercato_demo.py`: the full loop, the flash sale, the
  checkout outage caught in ~5 min.
- **KQL round-trip** — replays into **Fabric Eventhouse or Azure Data Explorer**;
  proves it's real, and portable.
- **Event bridge** (`bridge/`) — the concrete path to their real Open Mercato data.
- **`openmercato-deck-eli5.md`** — the no-jargon version for execs/stakeholders.

**Suggested flow:** deck → live demo → "stand it up in *your* Azure/Fabric" (KQL
replay) → wire the bridge to their Open Mercato → scope a fine-tune (Azure ML).

---

## Landmines — don't do this

- ❌ Don't promise sales-prediction accuracy or "we forecast your revenue." Frame
  as real-time ops + safety.
- ❌ Don't present it as a Microsoft or Open Mercato product, or imply support.
- ❌ Don't ignore **PII** — order events carry it; keep bars aggregated and loop in
  data protection.
- ❌ Don't quote the demo's numbers as live-store performance — fixed-seed
  synthetic, illustrative only.

---

## Next steps / call to action

1. **Qualify** (real-time gap? event source? Fabric vs ADX? data to fine-tune on?).
2. **Show** the deck + live demo.
3. **Prove** with a KQL replay into their Fabric Eventhouse or ADX.
4. **Connect** the Open Mercato event bridge to their real stream.
5. **Expand** into a fine-tune (Azure ML GPU) and more tenants/SKUs (capacity growth).

---

**Learn more:** [Open Mercato](https://github.com/open-mercato/open-mercato),
[Kronos](https://github.com/shiyu-coder/Kronos), design in
[`../architecture.md`](../architecture.md), and references in
[`../../azure/references.md`](../../azure/references.md).
