import { useState } from "react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import type { ShopView } from "@/lib/api";
import type { AgentStepEvent } from "@/lib/stream";
import { cn } from "@/lib/utils";
import { CaseLine, type CaseStepItem } from "./CaseLine";
import { StateLabel } from "./StateLabel";

export interface RawStepRecord {
  id: string;
  event: AgentStepEvent;
  receivedAt: string;
}

export interface CaseFileProps {
  steps: RawStepRecord[];
  shops: ShopView[];
  className?: string;
}

const PLAIN_NODE_NAMES: Record<AgentStepEvent["node"], string> = {
  sense: "Check",
  confirm: "Rain",
  ask: "Ask",
  classify: "Classify",
  file: "File",
  human_review: "Review",
  close: "Close",
  batch: "Batch",
  payback: "Pay back",
};

function extractShopId(detail: string): string {
  const match = detail.match(/\bshop_\d{2}\b/);
  return match ? match[0] : "street";
}

function buildPlainTitle(
  event: AgentStepEvent,
  shopMap: Map<string, ShopView>
): string {
  const shopId = extractShopId(event.detail);
  const shop = shopMap.get(shopId);
  const ownerOrName = shop ? `${shop.owner} (${shop.name})` : shopId;

  if (event.node === "sense") {
    if (event.status === "start") {
      return `Checking 28-day baseline and daily total for ${ownerOrName}`;
    }
    const droppedMatch = event.detail.includes("dropped=True");
    return droppedMatch
      ? `Detected payment drop against 28-day baseline for ${ownerOrName}`
      : `Payments within normal range for ${ownerOrName}`;
  }

  if (event.node === "confirm") {
    if (event.status === "start") {
      return `Checking street quorum and Open-Meteo rain for ${ownerOrName}`;
    }
    if (event.detail.includes("-> file")) {
      return `Checked rain for Panagal Park Road: eligible to file for ${ownerOrName}`;
    }
    if (event.detail.includes("-> ask")) {
      return `Checked rain and street quorum: voice check required for ${ownerOrName}`;
    }
    return `Checked street quorum and rain: no claim required for ${ownerOrName}`;
  }

  if (event.node === "ask") {
    if (event.detail.includes("Consent recorded")) {
      return `Consent recorded from ${ownerOrName}`;
    }
    if (event.detail.includes("Ask declined")) {
      return `Consent declined by ${ownerOrName}`;
    }
    if (event.detail.includes("(consent)")) {
      return `Sent Tamil consent ask to ${ownerOrName}`;
    }
    if (event.detail.includes("(voice)")) {
      return `Sent Tamil voice prompt to ${ownerOrName}`;
    }
    return `Prepared Tamil prompt for ${ownerOrName}`;
  }

  if (event.node === "classify") {
    if (event.status === "start") {
      return `Transcribing and classifying Tamil voice reply from ${ownerOrName}`;
    }
    const clsMatch = event.detail.match(/classified as ([a-z_]+)/i);
    const rawLabel = clsMatch ? clsMatch[1] : event.detail;
    const readableLabel =
      rawLabel === "qr_switch"
        ? "alternate QR reported"
        : rawLabel === "leave"
          ? "closed on personal leave"
          : rawLabel === "flood_closure"
            ? "flood closure confirmed"
            : rawLabel;
    return `Classified Tamil voice reply from ${ownerOrName}: ${readableLabel}`;
  }

  if (event.node === "file") {
    if (event.status === "start") {
      return `Building evidence pack PDF for ${ownerOrName}`;
    }
    return `Filed claim and generated evidence pack PDF for ${ownerOrName}`;
  }

  if (event.node === "close") {
    return `Closed ask for ${ownerOrName}: shop closed on leave (no claim filed)`;
  }

  if (event.node === "human_review") {
    return `Queued ${ownerOrName} for human review (alternate QR reported)`;
  }

  if (event.node === "batch") {
    return `Created adjuster batch (${event.detail})`;
  }

  if (event.node === "payback") {
    if (event.status === "start") {
      return `Initiating Rs 35 plan-fee refund for ${ownerOrName}`;
    }
    return `Processed Rs 35 plan-fee refund for ${ownerOrName}`;
  }

  return event.detail;
}

export function CaseFile({ steps, shops, className }: CaseFileProps) {
  const [selectedStep, setSelectedStep] = useState<CaseStepItem | null>(null);

  const shopMap = new Map<string, ShopView>();
  for (const s of shops) {
    shopMap.set(s.shop_id, s);
  }

  // Deduplicate in-place by (shopId, node): later updates overwrite "start" in place.
  const mergedByKey = new Map<string, RawStepRecord>();
  const orderedKeys: string[] = [];

  for (const rec of steps) {
    const shopId = extractShopId(rec.event.detail);
    const key = `${shopId}::${rec.event.node}`;
    if (!mergedByKey.has(key)) {
      orderedKeys.push(key);
    } else {
      const idx = orderedKeys.indexOf(key);
      if (idx >= 0) {
        orderedKeys.splice(idx, 1);
      }
      orderedKeys.push(key);
    }
    mergedByKey.set(key, rec);
  }

  const deduplicatedRecords = [...orderedKeys]
    .reverse()
    .map((k) => mergedByKey.get(k))
    .filter((item): item is RawStepRecord => item !== undefined);

  const enriched: CaseStepItem[] = deduplicatedRecords.map((rec) => {
    const shopId = extractShopId(rec.event.detail);
    const shop = shopMap.get(shopId);
    const shopLabel = shop
      ? `${shop.name} (${shop.owner})`
      : "Panagal Park Road (Batch)";
    return {
      ...rec.event,
      id: `${shopId}-${rec.event.node}`,
      shopId,
      shopLabel,
      nodeLabel: PLAIN_NODE_NAMES[rec.event.node] ?? rec.event.node,
      plainTitle: buildPlainTitle(rec.event, shopMap),
      receivedAt: rec.receivedAt,
    };
  });

  const groups: Array<{ shopId: string; shopLabel: string; items: CaseStepItem[] }> = [];
  const groupByShop = new Map<string, { shopId: string; shopLabel: string; items: CaseStepItem[] }>();

  for (const item of enriched) {
    let group = groupByShop.get(item.shopId);
    if (!group) {
      group = {
        shopId: item.shopId,
        shopLabel: item.shopLabel,
        items: [],
      };
      groupByShop.set(item.shopId, group);
      groups.push(group);
    }
    group.items.push(item);
  }

  return (
    <section
      aria-label="Case file"
      className={cn(
        "flex min-h-0 flex-1 flex-col rounded-[6px] border border-[var(--line-dark)] bg-[var(--ink-2)] p-3",
        className
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-2 border-b border-[var(--line-dark)] pb-2">
        <div className="flex items-center gap-2">
          <h2 className="font-heading text-[var(--text-dark-1)]">Case File</h2>
          <span className="font-figures text-[14px] leading-[20px] text-[var(--text-dark-3)]">
            ({enriched.length} steps)
          </span>
        </div>
        <span className="text-[14px] leading-[20px] text-[var(--text-dark-3)]">
          Newest first, grouped by shop
        </span>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        {groups.length === 0 ? (
          <div className="flex h-full items-center justify-center py-8 text-center text-[14px] leading-[20px] text-[var(--text-dark-3)]">
            Press &ldquo;Reset and run the flood&rdquo; to watch the detector and agent work across Panagal Park Road.
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {groups.map((grp) => (
              <div
                key={grp.shopId}
                className="flex flex-col gap-1.5 rounded-[4px] border border-[var(--line-dark)] bg-[var(--ink)] p-2.5"
              >
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-[12px] leading-[16px] font-semibold uppercase tracking-[0.4px] text-[var(--text-dark-2)]">
                    {grp.shopLabel}
                  </h3>
                  <span className="font-figures text-[14px] leading-[20px] text-[var(--text-dark-3)]">
                    {grp.items.length} {grp.items.length === 1 ? "step" : "steps"}
                  </span>
                </div>
                <div className="flex flex-col gap-1">
                  {grp.items.map((step) => (
                    <CaseLine
                      key={step.id}
                      step={step}
                      onOpenDetails={(item) => setSelectedStep(item)}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <Sheet
        open={selectedStep !== null}
        onOpenChange={(open) => {
          if (!open) setSelectedStep(null);
        }}
      >
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Step Details</SheetTitle>
            <SheetDescription className="text-[14px] leading-[20px]">
              Recorded agent node payload in IBM Plex Mono.
            </SheetDescription>
          </SheetHeader>

          {selectedStep ? (
            <div className="mt-4 flex flex-col gap-3 overflow-y-auto">
              <div className="flex items-center justify-between gap-2 rounded-[4px] border border-[var(--line)] bg-[var(--card)] p-3">
                <div>
                  <div className="text-[12px] leading-[16px] font-semibold uppercase text-[var(--text-2)]">
                    {selectedStep.shopLabel} · {selectedStep.nodeLabel}
                  </div>
                  <div className="mt-0.5 text-[14px] leading-[20px] font-medium text-[var(--text-1)]">
                    {selectedStep.plainTitle}
                  </div>
                </div>
                <StateLabel
                  kind={selectedStep.live ? "live" : "replay"}
                  surface="paper"
                />
              </div>

              <div className="rounded-[4px] border border-[var(--line)] bg-[var(--card)] p-3">
                <div className="mb-1.5 text-[12px] leading-[16px] font-medium uppercase tracking-[0.4px] text-[var(--text-3)]">
                  Step Event Payload (JSON)
                </div>
                <pre className="overflow-x-auto whitespace-pre-wrap break-words font-figures text-[14px] leading-[20px] text-[var(--text-1)]">
                  {JSON.stringify(
                    {
                      id: selectedStep.id,
                      step: selectedStep.nodeLabel,
                      node: selectedStep.node,
                      status: selectedStep.status,
                      shop_id: selectedStep.shopId,
                      detail: selectedStep.detail,
                      live: selectedStep.live,
                      received_at: selectedStep.receivedAt,
                    },
                    null,
                    2
                  )}
                </pre>
              </div>
            </div>
          ) : null}
        </SheetContent>
      </Sheet>
    </section>
  );
}
