import type { IntegrationMode } from "./api";

export interface ClockTickEvent {
  ts: string;
}

export interface ShopStatusEvent {
  shop_id: string;
  status: "trading" | "quiet" | "dropped";
}

export interface DetectorDecisionEvent {
  shop_id: string;
  decision: "file" | "ask" | "none";
  reason: string;
  quorum_share: number;
  rain_mm: number;
  live: boolean;
  replay: boolean;
}

export interface AgentStepEvent {
  node:
    | "sense"
    | "confirm"
    | "ask"
    | "classify"
    | "file"
    | "close"
    | "human_review"
    | "payback"
    | "batch";
  status: "start" | "ok" | "error";
  detail: string;
  live: boolean;
}

export interface AskSentEvent {
  ask_id: string;
  shop_id: string;
  kind: "consent" | "voice";
  text_ta: string;
  audio_url: string | null;
  live: boolean;
}

export interface AskAnsweredEvent {
  ask_id: string;
  shop_id: string;
  reply_type: string;
  label: string;
  simulated: boolean;
  simulated_label?: string | null;
}

export interface ClaimFiledEvent {
  claim_id: string;
  shop_id: string;
  evidence_url: string;
}

export interface BatchReadyEvent {
  batch_id: string;
  n: number;
  count?: number;
}

export interface BatchApprovedEvent {
  batch_id: string;
  by: string;
  payback_enabled: boolean;
}

export interface RefundStatusEvent {
  claim_id: string;
  shop_id?: string;
  refund_id: string;
  status: "initiated" | "success" | "pending" | "failed" | "skipped";
  amount_paise: number;
  label: string;
}

export interface IntegrationHealthEvent {
  name: string;
  mode: IntegrationMode;
}

export interface StreamHandlers {
  onClockTick?: (data: ClockTickEvent, eventId: number) => void;
  onShopStatus?: (data: ShopStatusEvent, eventId: number) => void;
  onDetectorDecision?: (data: DetectorDecisionEvent, eventId: number) => void;
  onAgentStep?: (data: AgentStepEvent, eventId: number) => void;
  onAskSent?: (data: AskSentEvent, eventId: number) => void;
  onAskAnswered?: (data: AskAnsweredEvent, eventId: number) => void;
  onClaimFiled?: (data: ClaimFiledEvent, eventId: number) => void;
  onBatchReady?: (data: BatchReadyEvent, eventId: number) => void;
  onBatchApproved?: (data: BatchApprovedEvent, eventId: number) => void;
  onRefundStatus?: (data: RefundStatusEvent, eventId: number) => void;
  onIntegrationHealth?: (data: IntegrationHealthEvent, eventId: number) => void;
  onOpen?: () => void;
  onError?: () => void;
}

export function connectEventStream(handlers: StreamHandlers): () => void {
  let lastEventId: number | null = null;
  let source: EventSource | null = null;
  let closed = false;
  let reconnectTimer: number | null = null;

  function parseId(evt: MessageEvent<string>): number {
    const num = Number.parseInt(evt.lastEventId, 10);
    if (!Number.isNaN(num)) {
      lastEventId = num;
      return num;
    }
    return lastEventId ?? 0;
  }

  function bindEvent<T>(
    es: EventSource,
    eventName: string,
    cb?: (data: T, eventId: number) => void
  ): void {
    if (!cb) return;
    es.addEventListener(eventName, (rawEvt: Event) => {
      const msgEvt = rawEvt as MessageEvent<string>;
      const id = parseId(msgEvt);
      try {
        const parsed = JSON.parse(msgEvt.data) as T;
        cb(parsed, id);
      } catch {
        // Ignore malformed event frame
      }
    });
  }

  function open(): void {
    if (closed) return;
    const query = lastEventId !== null ? `?since_id=${lastEventId}` : "";
    const es = new EventSource(`/api/stream${query}`);
    source = es;

    es.onopen = () => {
      handlers.onOpen?.();
    };

    es.onerror = () => {
      handlers.onError?.();
      es.close();
      if (!closed && reconnectTimer === null) {
        reconnectTimer = window.setTimeout(() => {
          reconnectTimer = null;
          open();
        }, 1500);
      }
    };

    bindEvent(es, "clock.tick", handlers.onClockTick);
    bindEvent(es, "shop.status", handlers.onShopStatus);
    bindEvent(es, "detector.decision", handlers.onDetectorDecision);
    bindEvent(es, "agent.step", handlers.onAgentStep);
    bindEvent(es, "ask.sent", handlers.onAskSent);
    bindEvent(es, "ask.answered", handlers.onAskAnswered);
    bindEvent(es, "claim.filed", handlers.onClaimFiled);
    bindEvent(es, "batch.ready", handlers.onBatchReady);
    bindEvent(es, "batch.approved", handlers.onBatchApproved);
    bindEvent(es, "refund.status", handlers.onRefundStatus);
    bindEvent(es, "integration.health", handlers.onIntegrationHealth);
  }

  open();

  return () => {
    closed = true;
    if (reconnectTimer !== null) {
      window.clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    source?.close();
  };
}

