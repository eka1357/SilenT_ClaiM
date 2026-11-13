import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { Link } from "react-router-dom";
import { OpenExternalGlyph } from "@/components/glyphs/OpenExternalGlyph";
import { ReceiptGlyph } from "@/components/glyphs/ReceiptGlyph";
import type { MetricsResponse, ShopView } from "@/lib/api";
import { formatDurationMmSs, formatRupeesFromPaise } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ReceiptLine } from "./ReceiptLine";
import { StateLabel } from "./StateLabel";

export interface ReceiptRefundItem {
  claim_id: string;
  shop_id?: string;
  refund_id: string;
  amount_paise: number;
  status: string;
  label: string;
}

export interface ReceiptProps {
  metrics: MetricsResponse | null;
  batchId: string | null;
  batchCount: number;
  batchStatus: string | null;
  refunds: ReceiptRefundItem[];
  shops: ShopView[];
  className?: string;
}

function AnimatedRefundAmount({
  amountPaise,
  reducedMotion,
}: {
  amountPaise: number;
  reducedMotion: boolean;
}) {
  const targetRupees = Math.round(amountPaise / 100);
  const [displayRupees, setDisplayRupees] = useState<number>(
    reducedMotion ? targetRupees : 0
  );

  useEffect(() => {
    if (reducedMotion || targetRupees <= 0) {
      setDisplayRupees(targetRupees);
      return;
    }
    setDisplayRupees(0);
    const durationMs = 450;
    const startTs = performance.now();
    let rafId = 0;

    const step = (now: number) => {
      const elapsed = now - startTs;
      const progress = Math.min(1, elapsed / durationMs);
      setDisplayRupees(Math.round(progress * targetRupees));
      if (progress < 1) {
        rafId = window.requestAnimationFrame(step);
      }
    };

    rafId = window.requestAnimationFrame(step);
    return () => window.cancelAnimationFrame(rafId);
  }, [targetRupees, reducedMotion]);

  if (amountPaise % 100 !== 0) {
    return <>{formatRupeesFromPaise(amountPaise)}</>;
  }
  return <>₹{displayRupees}</>;
}

export function Receipt({
  metrics,
  batchId,
  batchCount,
  batchStatus,
  refunds,
  shops,
  className,
}: ReceiptProps) {
  const reducedMotion = Boolean(useReducedMotion());
  const shopMap = new Map<string, ShopView>();
  for (const s of shops) {
    shopMap.set(s.shop_id, s);
  }

  const formsFilled = metrics?.forms_filled ?? 0;
  const merchantTaps = metrics?.merchant_taps ?? 0;
  const timeToFile = formatDurationMmSs(
    metrics?.max_time_to_file_seconds ?? metrics?.avg_time_to_file_seconds ?? 0
  );
  const evalMetrics = metrics?.eval;
  const claimsRightText = evalMetrics
    ? `${evalMetrics.claims_right} of ${evalMetrics.claims_filed}`
    : "17 of 18";
  const closuresMissedText = evalMetrics
    ? `${evalMetrics.closures_missed} of ${evalMetrics.total_closures}`
    : "1 of 18";

  const activeClaimsCount =
    batchCount > 0 ? batchCount : (metrics?.claims_filed_in_run ?? 0);

  return (
    <aside
      aria-label="Run receipt"
      className={cn(
        "flex h-full flex-col justify-between rounded-[6px] border border-[var(--line)] bg-[var(--paper)] text-[var(--text-1)]",
        className
      )}
    >
      <div className="flex min-h-0 flex-1 flex-col p-3.5">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--line)] pb-2">
          <div className="flex items-center gap-2">
            <ReceiptGlyph className="h-4 w-4 text-[var(--rust)]" />
            <h2 className="font-sign-sm text-[var(--text-1)]">RUN RECEIPT</h2>
          </div>
          <StateLabel
            kind="simulated"
            text={evalMetrics?.label ?? "Simulated eval"}
            surface="paper"
          />
        </div>

        {/* Dotted-leader metric rows */}
        <div className="mt-2 flex flex-col gap-1 border-b border-[var(--line)] pb-2">
          <ReceiptLine label="Forms filled" value={formsFilled} />
          <ReceiptLine label="Taps" value={merchantTaps} />
          <ReceiptLine label="Time to file" value={timeToFile} />
          <ReceiptLine label="Claims right (eval)" value={claimsRightText} />
          <ReceiptLine
            label="Closures missed (eval)"
            value={closuresMissedText}
          />
        </div>

        {/* Batch link section */}
        <div className="mt-2 border-b border-[var(--line)] pb-2">
          <div className="mb-1 text-[12px] leading-[16px] font-semibold uppercase tracking-[0.4px] text-[var(--text-3)]">
            Adjuster Batch
          </div>
          {batchId || batchCount > 0 ? (
            <Link
              to="/adjuster"
              className="flex items-center justify-between gap-2 rounded-[4px] border border-[var(--line)] bg-[var(--card)] px-2.5 py-1.5 font-figures text-[14px] leading-[20px] text-[var(--text-1)] hover:border-[var(--rust)]"
            >
              <span>
                {batchStatus === "approved"
                  ? "Batch for 21 Oct: approved"
                  : `Batch for 21 Oct: ready (${batchCount})`}
              </span>
              <OpenExternalGlyph className="h-4 w-4 shrink-0 text-[var(--rust)]" />
            </Link>
          ) : activeClaimsCount > 0 ? (
            <div className="flex flex-col gap-1 rounded-[4px] border border-[var(--line)] bg-[var(--card)] p-2 font-figures text-[14px] leading-[20px] text-[var(--text-2)]">
              <div>
                {activeClaimsCount} of 7 claims filed (awaiting Selvi&apos;s tap)
              </div>
              <div className="flex items-center gap-3">
                <Link
                  to="/merchant"
                  className="inline-flex items-center gap-1 font-semibold text-[var(--rust)] underline underline-offset-2"
                >
                  <span>Open merchant view</span>
                  <OpenExternalGlyph className="h-3.5 w-3.5" />
                </Link>
                <Link
                  to="/adjuster"
                  className="inline-flex items-center gap-1 text-[var(--text-2)] underline underline-offset-2"
                >
                  <span>Adjuster view</span>
                </Link>
              </div>
            </div>
          ) : (
            <div className="rounded-[4px] border border-[var(--line)] bg-[var(--card)] px-2.5 py-1.5 font-figures text-[14px] leading-[20px] text-[var(--text-3)]">
              No batch ready yet. Run the scenario to generate claims.
            </div>
          )}
        </div>

        {/* Plan-fee refund lines */}
        <div className="mt-2 flex min-h-0 flex-1 flex-col">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-[12px] leading-[16px] font-semibold uppercase tracking-[0.4px] text-[var(--text-3)]">
              Plan-Fee Refunds
            </span>
            <span className="font-figures text-[14px] leading-[20px] text-[var(--text-3)]">
              {refunds.length} processed
            </span>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto pr-0.5">
            {refunds.length === 0 ? (
              <div className="rounded-[4px] border border-[var(--line)] bg-[var(--card)] px-3 py-2 font-figures text-[14px] leading-[20px] text-[var(--text-3)]">
                Approve the batch on /adjuster to trigger Rs 35 plan-fee refunds.
              </div>
            ) : (
              <div className="flex flex-col gap-1">
                {refunds.map((item) => {
                  const shop = item.shop_id ? shopMap.get(item.shop_id) : undefined;
                  const ownerLabel = shop
                    ? shop.owner
                    : (item.shop_id ?? item.claim_id);
                  const isSimulated = item.label.toLowerCase().includes("simulated");
                  return (
                    <motion.div
                      key={item.refund_id}
                      initial={reducedMotion ? false : { opacity: 0, y: -8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={
                        reducedMotion ? { duration: 0 } : { duration: 0.2 }
                      }
                      className="flex flex-col gap-0.5 rounded-[4px] border border-[var(--line)] bg-[var(--card)] px-2 py-1 font-figures text-[14px] leading-[18px] text-[var(--text-1)]"
                    >
                      <div className="flex items-center justify-between gap-1.5">
                        <span className="font-semibold">
                          <AnimatedRefundAmount
                            amountPaise={item.amount_paise}
                            reducedMotion={reducedMotion}
                          />{" "}
                          plan fee -&gt; {ownerLabel}
                        </span>
                        <StateLabel
                          kind={
                            isSimulated
                              ? "simulated"
                              : item.status === "failed"
                                ? "error"
                                : "filed"
                          }
                          text={item.label}
                          surface="paper"
                        />
                      </div>
                      <div className="text-[12px] leading-[16px] text-[var(--text-3)]">
                        {item.refund_id}
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Torn-edge SVG rule at bottom */}
      <div className="w-full overflow-hidden">
        <svg
          viewBox="0 0 360 12"
          preserveAspectRatio="none"
          aria-hidden="true"
          className="block h-3 w-full text-[var(--ink)]"
        >
          <path
            d="M0,12 L0,2 L12,10 L24,2 L36,10 L48,2 L60,10 L72,2 L84,10 L96,2 L108,10 L120,2 L132,10 L144,2 L156,10 L168,2 L180,10 L192,2 L204,10 L216,2 L228,10 L240,2 L252,10 L264,2 L276,10 L288,2 L300,10 L312,2 L324,10 L336,2 L348,10 L360,2 L360,12 Z"
            fill="currentColor"
          />
        </svg>
      </div>
    </aside>
  );
}
