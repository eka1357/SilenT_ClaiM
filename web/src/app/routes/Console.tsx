import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { CaseFile, type RawStepRecord } from "@/components/CaseFile";
import { PlayGlyph } from "@/components/glyphs/PlayGlyph";
import { Receipt, type ReceiptRefundItem } from "@/components/Receipt";
import { RoadBand } from "@/components/RoadBand";
import { Shopfront } from "@/components/Shopfront";
import { StateLabel, type StateLabelKind } from "@/components/StateLabel";
import { Button } from "@/components/ui/button";
import {
  getCurrentBatch,
  getHealth,
  getMetrics,
  getStreet,
  type HealthResponse,
  type IntegrationMode,
  type IntegrationStatusItem,
  type MetricsResponse,
  resetScenario,
  runScenario,
  type ShopView,
  type StreetResponse,
} from "@/lib/api";
import { formatClockTimeIST, resolveShopStatusText } from "@/lib/format";
import { connectEventStream } from "@/lib/stream";

const INTEGRATION_LABELS: Array<{ key: string; title: string }> = [
  { key: "weather", title: "Open-Meteo" },
  { key: "sarvam", title: "Sarvam" },
  { key: "llm", title: "LLM" },
  { key: "paytm", title: "Paytm staging" },
];

function extractMode(
  entry: IntegrationStatusItem | IntegrationMode | undefined
): IntegrationMode | undefined {
  if (!entry) return undefined;
  return typeof entry === "string" ? entry : entry.mode;
}

function resolveIntegrationMode(
  integrations: Record<string, IntegrationStatusItem | IntegrationMode> | undefined,
  key: string
): IntegrationMode | undefined {
  if (!integrations) return undefined;
  if (key === "sarvam") {
    const direct = extractMode(integrations.sarvam);
    if (direct) return direct;
    const tts = extractMode(integrations.sarvam_tts);
    const stt = extractMode(integrations.sarvam_stt);
    if (tts === "down" || stt === "down") return "down";
    return tts ?? stt;
  }
  return extractMode(integrations[key]);
}

function mapModeToKind(mode: IntegrationMode | undefined): StateLabelKind {
  if (mode === "live") return "live";
  if (mode === "replay") return "replay";
  if (mode === "down") return "error";
  return "simulated";
}

function mapModeToText(
  key: string,
  mode: IntegrationMode | undefined,
  paytmMode: string
): string {
  if (mode === "down") {
    const title =
      INTEGRATION_LABELS.find((item) => item.key === key)?.title ?? key;
    return `${title}: Down`;
  }
  if (key === "paytm" && (mode === "simulated" || paytmMode === "pending")) {
    return "Paytm: Simulated (keys pending)";
  }
  const title =
    INTEGRATION_LABELS.find((item) => item.key === key)?.title ?? key;
  const suffix =
    mode === "live"
      ? "Live"
      : mode === "replay"
        ? "Replay"
        : "Simulated";
  return `${title}: ${suffix}`;
}

function synthesizeStepsFromShops(
  shops: ShopView[],
  demoOffline: boolean
): RawStepRecord[] {
  const records: RawStepRecord[] = [];
  const nowIso = new Date().toISOString();
  for (const s of shops) {
    if (!s.detection) continue;
    records.push({
      id: `syn-sense-${s.shop_id}`,
      receivedAt: nowIso,
      event: {
        node: "sense",
        status: "ok",
        detail: `${s.shop_id} income=${s.detection.day_income_paise}p baseline=${s.detection.baseline_paise}p dropped=${s.detection.dropped ? "True" : "False"}`,
        live: true,
      },
    });
    records.push({
      id: `syn-confirm-${s.shop_id}`,
      receivedAt: nowIso,
      event: {
        node: "confirm",
        status: "ok",
        detail: `${s.shop_id} -> ${s.detection.decision} (${s.detection.reason}), rain=${s.detection.rain_mm.toFixed(1)}mm`,
        live: !demoOffline,
      },
    });
    if (s.ask) {
      records.push({
        id: `syn-ask-${s.shop_id}`,
        receivedAt: s.ask.answered_at ?? nowIso,
        event: {
          node: "ask",
          status: "ok",
          detail: `Ask ${s.ask.id} (${s.ask.ask_kind}) sent to ${s.shop_id}`,
          live: !demoOffline,
        },
      });
      if (s.ask.ask_kind === "consent" && s.ask.status === "answered") {
        records.push({
          id: `syn-consent-${s.shop_id}`,
          receivedAt: s.ask.answered_at ?? nowIso,
          event: {
            node: "ask",
            status: "ok",
            detail: `Consent recorded for ${s.shop_id}`,
            live: !demoOffline,
          },
        });
      }
      if (s.ask.ask_kind === "voice" && s.ask.status !== "pending") {
        records.push({
          id: `syn-classify-${s.shop_id}`,
          receivedAt: s.ask.answered_at ?? nowIso,
          event: {
            node: "classify",
            status: "ok",
            detail: `${s.shop_id} classified as ${s.ask.cause_label ?? "other"}`,
            live: !demoOffline,
          },
        });
        if (s.ask.cause_label === "leave" || s.ask.status === "closed") {
          records.push({
            id: `syn-close-${s.shop_id}`,
            receivedAt: s.ask.answered_at ?? nowIso,
            event: {
              node: "close",
              status: "ok",
              detail: `Closed ask for ${s.shop_id} (leave)`,
              live: !demoOffline,
            },
          });
        } else if (
          s.ask.cause_label === "qr_switch" ||
          s.ask.status === "human_review"
        ) {
          records.push({
            id: `syn-review-${s.shop_id}`,
            receivedAt: s.ask.answered_at ?? nowIso,
            event: {
              node: "human_review",
              status: "ok",
              detail: `Queued ${s.shop_id} for human review (qr_switch)`,
              live: !demoOffline,
            },
          });
        }
      }
    }
    if (s.claim) {
      records.push({
        id: `syn-file-${s.shop_id}`,
        receivedAt: s.claim.consent_at ?? nowIso,
        event: {
          node: "file",
          status: "ok",
          detail: `Filed ${s.claim.id} for ${s.shop_id}`,
          live: !demoOffline,
        },
      });
      if (s.claim.refund) {
        records.push({
          id: `syn-payback-${s.shop_id}`,
          receivedAt: nowIso,
          event: {
            node: "payback",
            status: "ok",
            detail: `Refund ${s.claim.refund.refund_id} for ${s.shop_id}`,
            live: !demoOffline,
          },
        });
      }
    }
  }
  return records;
}

export function Console() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [streetData, setStreetData] = useState<StreetResponse | null>(null);
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [batchCount, setBatchCount] = useState<number>(0);
  const [batchStatus, setBatchStatus] = useState<string | null>(null);
  const [steps, setSteps] = useState<RawStepRecord[]>([]);
  const [refunds, setRefunds] = useState<ReceiptRefundItem[]>([]);
  const [clockTs, setClockTs] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiOffline, setApiOffline] = useState(false);
  const [isTriggering, setIsTriggering] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const activeDayRef = useRef<string>("2026-10-21");

  const refreshSnapshots = useCallback(async (dayOverride?: string) => {
    try {
      const targetDay = dayOverride ?? activeDayRef.current;
      const [streetRes, metricsRes, batchRes, healthRes] = await Promise.all([
        getStreet("panagal_park_road", targetDay),
        getMetrics(),
        getCurrentBatch(),
        getHealth(),
      ]);
      setStreetData(streetRes);
      setMetrics(metricsRes);
      setHealth(healthRes);
      setApiOffline(false);
      setErrorBanner(null);

      if (streetRes.clock.current_hour) {
        setClockTs(streetRes.clock.current_hour);
      }
      if (streetRes.clock.active_day) {
        activeDayRef.current = streetRes.clock.active_day;
      }

      if (batchRes.batch) {
        setBatchId(batchRes.batch.id);
        setBatchCount(batchRes.batch.claims_count);
        setBatchStatus(batchRes.batch.status);
      } else {
        setBatchId(null);
        setBatchCount(0);
        setBatchStatus(null);
      }

      if (metricsRes.refunds.items.length > 0) {
        setRefunds(metricsRes.refunds.items);
      }
    } catch (err) {
      setApiOffline(true);
      const msg = err instanceof Error ? err.message : "Failed to load console state";
      setErrorBanner(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshSnapshots("2026-10-21");
  }, [refreshSnapshots]);

  const isRunningClock = Boolean(streetData?.clock.running);

  useEffect(() => {
    if (!isRunningClock && !isTriggering) {
      const timer = window.setTimeout(() => {
        void refreshSnapshots("2026-10-21");
      }, 400);
      return () => window.clearTimeout(timer);
    }
    const interval = window.setInterval(() => {
      void refreshSnapshots("2026-10-21");
    }, 1000);
    return () => {
      window.clearInterval(interval);
    };
  }, [isRunningClock, isTriggering, refreshSnapshots]);

  useEffect(() => {
    const disconnect = connectEventStream({
      onClockTick: (evt) => {
        setClockTs(evt.ts);
        void getStreet("panagal_park_road", activeDayRef.current)
          .then((res) => setStreetData(res))
          .catch(() => undefined);
      },
      onShopStatus: (evt) => {
        setStreetData((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            shops: prev.shops.map((s) =>
              s.shop_id === evt.shop_id ? { ...s, status: evt.status } : s
            ),
          };
        });
      },
      onDetectorDecision: () => {
        void refreshSnapshots();
      },
      onAgentStep: (evt, eventId) => {
        setSteps((prev) => [
          ...prev,
          {
            id: `sse-${eventId}-${prev.length}`,
            event: evt,
            receivedAt: new Date().toISOString(),
          },
        ]);
      },
      onAskSent: () => {
        void refreshSnapshots();
      },
      onAskAnswered: () => {
        void refreshSnapshots();
      },
      onClaimFiled: () => {
        void refreshSnapshots();
      },
      onBatchReady: (evt) => {
        setBatchId(evt.batch_id);
        setBatchCount(evt.count);
        setBatchStatus("pending");
        void refreshSnapshots();
      },
      onBatchApproved: (evt) => {
        setBatchId(evt.batch_id);
        setBatchStatus("approved");
        void refreshSnapshots();
      },
      onRefundStatus: (evt) => {
        setRefunds((prev) => {
          const existingIdx = prev.findIndex((r) => r.refund_id === evt.refund_id);
          const item: ReceiptRefundItem = {
            claim_id: evt.claim_id,
            shop_id: evt.shop_id,
            refund_id: evt.refund_id,
            amount_paise: evt.amount_paise,
            status: evt.status,
            label: evt.label,
          };
          if (existingIdx >= 0) {
            const copy = [...prev];
            copy[existingIdx] = item;
            return copy;
          }
          return [...prev, item];
        });
        void refreshSnapshots();
      },
      onIntegrationHealth: (evt) => {
        setHealth((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            integrations: {
              ...prev.integrations,
              [evt.name]: evt.mode,
            },
          };
        });
      },
    });

    return () => {
      disconnect();
    };
  }, [refreshSnapshots]);

  const handleResetAndRun = async () => {
    setIsTriggering(true);
    setErrorBanner(null);
    try {
      await resetScenario();
      setSteps([]);
      setRefunds([]);
      setBatchId(null);
      setBatchCount(0);
      setBatchStatus(null);
      setClockTs(null);
      activeDayRef.current = "2026-10-21";
      await runScenario("2026-10-21", 60);
      await refreshSnapshots("2026-10-21");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to start flood scenario";
      setErrorBanner(msg);
    } finally {
      setIsTriggering(false);
    }
  };

  const shops = useMemo(() => streetData?.shops ?? [], [streetData]);
  const topRowShops = useMemo(() => shops.slice(0, 6), [shops]);
  const bottomRowShops = useMemo(() => shops.slice(6, 12), [shops]);

  const displayedSteps = useMemo(() => {
    const synthesized = synthesizeStepsFromShops(
      shops,
      health?.demo_offline ?? true
    );
    if (steps.length >= synthesized.length && steps.length > 0) {
      return steps;
    }
    return synthesized.length > 0 ? synthesized : steps;
  }, [steps, shops, health?.demo_offline]);

  const shuttersDownCount = useMemo(() => {
    if (shops.length === 0) return 0;
    const detectedDrops = shops.filter((s) => s.detection?.dropped).length;
    if (detectedDrops > 0) return detectedDrops;
    return shops.filter((s) => resolveShopStatusText(s) !== "Trading").length;
  }, [shops]);

  const firstDetection = useMemo(
    () => shops.find((s) => s.detection !== null)?.detection ?? null,
    [shops]
  );

  const rainLive = resolveIntegrationMode(health?.integrations, "weather") === "live";

  return (
    <div className="flex min-h-screen w-full flex-col bg-[var(--ink)] text-[var(--text-dark-1)] xl:h-screen xl:overflow-hidden">
      {/* Top Bar (72 px) */}
      <header className="flex min-h-[72px] shrink-0 flex-wrap items-center justify-between gap-4 border-b border-[var(--line-dark)] bg-[var(--ink-2)] px-6 py-2">
        <div className="flex items-center gap-4">
          <h1 className="font-sign text-[var(--text-dark-1)]">SILENT CLAIM</h1>
          <div
            aria-label="Scenario clock"
            className="rounded-[4px] border border-[var(--line-dark)] bg-[var(--ink)] px-3 py-1 font-figures text-[var(--marigold)]"
          >
            {formatClockTimeIST(clockTs)}
          </div>
          <span className="font-figures text-[14px] leading-[20px] text-[var(--text-dark-2)]">
            Rules 2026.11-a
          </span>
          <Link
            to="/lab"
            className="rounded-[4px] border border-[var(--marigold)] bg-[var(--ink)] px-3 py-1 text-[14px] leading-[20px] font-semibold text-[var(--marigold)] hover:bg-[var(--ink-3)]"
          >
            Try to fool it
          </Link>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div
            aria-label="Integration statuses"
            className="flex flex-wrap items-center gap-2"
          >
            {INTEGRATION_LABELS.map(({ key }) => {
              const mode = resolveIntegrationMode(health?.integrations, key);
              const paytmMode = health?.paytm_mode ?? "pending";
              return (
                <StateLabel
                  key={key}
                  kind={mapModeToKind(mode)}
                  text={mapModeToText(key, mode, paytmMode)}
                />
              );
            })}
          </div>

          <Button
            type="button"
            disabled={isTriggering}
            onClick={() => void handleResetAndRun()}
          >
            <PlayGlyph className="h-4 w-4" />
            <span>
              {isTriggering ? "Starting flood run..." : "Reset and run the flood"}
            </span>
          </Button>
        </div>
      </header>

      {apiOffline || errorBanner ? (
        <div
          role="alert"
          className="flex items-center justify-between border-b border-[var(--danger)]/40 bg-[var(--ink-2)] px-6 py-2 text-[14px] leading-[20px] text-[var(--danger)]"
        >
          <span className="font-semibold">
            {apiOffline ? `API offline${errorBanner ? `: ${errorBanner}` : ""}` : errorBanner}
          </span>
          <StateLabel kind="error" text="Down" />
        </div>
      ) : null}

      {/* Main Two-Column Body (1fr 360px at >=1280px) */}
      <main className="mx-auto grid min-h-0 w-full max-w-[1440px] flex-1 grid-cols-1 gap-4 p-4 xl:grid-cols-[1fr_360px]">
        {/* Left Column: Street + Case File */}
        <div className="flex min-h-0 flex-col gap-3">
          {/* Street Section */}
          <section
            aria-label="Panagal Park Road street view"
            className="flex shrink-0 flex-col gap-2 rounded-[6px] border border-[var(--line-dark)] bg-[var(--ink-2)] p-3"
          >
            {/* Top row: Shops 1-6 */}
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
              {loading && topRowShops.length === 0
                ? Array.from({ length: 6 }).map((_, idx) => (
                    <div
                      key={`skel-top-${idx}`}
                      className="h-[126px] w-full rounded-[6px] border border-[var(--line-dark)] bg-[var(--ink-3)]"
                    />
                  ))
                : topRowShops.map((shop) => (
                    <Shopfront key={shop.shop_id} shop={shop} />
                  ))}
            </div>

            {/* RoadBand */}
            <RoadBand
              streetName={streetData?.street.name ?? "Panagal Park Road"}
              dayIso={streetData?.clock.active_day ?? "2026-10-21"}
              rainMm={firstDetection?.rain_mm ?? 27.7}
              rainSource={firstDetection?.rain_source ?? "Open-Meteo"}
              rainLive={Boolean(rainLive)}
              shuttersDown={shuttersDownCount}
              totalShops={shops.length || 12}
              isReplaying={isRunningClock}
            />

            {/* Bottom row: Shops 7-12 */}
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
              {loading && bottomRowShops.length === 0
                ? Array.from({ length: 6 }).map((_, idx) => (
                    <div
                      key={`skel-bot-${idx}`}
                      className="h-[126px] w-full rounded-[6px] border border-[var(--line-dark)] bg-[var(--ink-3)]"
                    />
                  ))
                : bottomRowShops.map((shop) => (
                    <Shopfront key={shop.shop_id} shop={shop} />
                  ))}
            </div>
          </section>

          {/* Case File Section */}
          <CaseFile steps={displayedSteps} shops={shops} />
        </div>

        {/* Right Column: Paper Receipt */}
        <div className="h-full min-h-0">
          <Receipt
            metrics={metrics}
            batchId={batchId}
            batchCount={batchCount}
            batchStatus={batchStatus}
            refunds={refunds}
            shops={shops}
          />
        </div>
      </main>
    </div>
  );
}

