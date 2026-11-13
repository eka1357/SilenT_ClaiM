import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CheckGlyph } from "@/components/glyphs/CheckGlyph";
import { OpenExternalGlyph } from "@/components/glyphs/OpenExternalGlyph";
import { ReceiptGlyph } from "@/components/glyphs/ReceiptGlyph";
import { StateLabel } from "@/components/StateLabel";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  approveBatch,
  type BatchClaimItem,
  type BatchInfo,
  getCurrentBatch,
  getHealth,
  getMetrics,
  type HealthResponse,
  type RefundMetricItem,
} from "@/lib/api";
import { formatClockTimeIST, formatRupeesFromPaise } from "@/lib/format";
import { connectEventStream } from "@/lib/stream";
import { cn } from "@/lib/utils";

function computeDropPercent(baselinePaise: number, dayIncomePaise: number): string {
  if (baselinePaise <= 0) return "0%";
  const pct = Math.max(
    0,
    Math.min(100, Math.round(((baselinePaise - dayIncomePaise) / baselinePaise) * 100))
  );
  return `${pct}%`;
}

function formatQuorum(share: number): string {
  const pct = Math.round(share * 100);
  const shut = Math.round(share * 12);
  return `${shut} of 12 (${pct}%)`;
}

export function Adjuster() {
  const [batch, setBatch] = useState<BatchInfo | null>(null);
  const [claims, setClaims] = useState<BatchClaimItem[]>([]);
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null);
  const [refunds, setRefunds] = useState<RefundMetricItem[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiOffline, setApiOffline] = useState(false);
  const [approving, setApproving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const refreshAdjuster = useCallback(async () => {
    try {
      const [batchRes, metricsRes, healthRes] = await Promise.all([
        getCurrentBatch(),
        getMetrics(),
        getHealth(),
      ]);
      setBatch(batchRes.batch);
      setClaims(batchRes.claims);
      setHealth(healthRes);
      setApiOffline(false);
      if (batchRes.claims.length > 0) {
        setSelectedClaimId((prev) =>
          prev && batchRes.claims.some((c) => c.id === prev)
            ? prev
            : batchRes.claims[0].id
        );
      }
      if (metricsRes.refunds.items.length > 0) {
        setRefunds(metricsRes.refunds.items);
      }
    } catch {
      setApiOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshAdjuster();
  }, [refreshAdjuster]);

  useEffect(() => {
    const disconnect = connectEventStream({
      onClaimFiled: () => {
        void refreshAdjuster();
      },
      onBatchReady: () => {
        void refreshAdjuster();
      },
      onBatchApproved: () => {
        void refreshAdjuster();
      },
      onRefundStatus: (evt) => {
        setRefunds((prev) => {
          const item: RefundMetricItem = {
            claim_id: evt.claim_id,
            shop_id: evt.shop_id ?? "",
            refund_id: evt.refund_id,
            amount_paise: evt.amount_paise,
            status: evt.status,
            label: evt.label,
          };
          const idx = prev.findIndex((r) => r.refund_id === evt.refund_id);
          if (idx >= 0) {
            const next = [...prev];
            next[idx] = item;
            return next;
          }
          return [...prev, item];
        });
        void refreshAdjuster();
      },
    });
    return () => {
      disconnect();
    };
  }, [refreshAdjuster]);

  const handleApproveBatch = async () => {
    if (!batch || batch.status === "approved") return;
    setApproving(true);
    setErrorMsg(null);
    try {
      await approveBatch(batch.id);
      await refreshAdjuster();
      // Poll briefly while background payback task finishes all 7 refunds
      for (let i = 0; i < 6; i += 1) {
        await new Promise((r) => window.setTimeout(r, 400));
        await refreshAdjuster();
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Batch approval failed";
      setErrorMsg(msg);
    } finally {
      setApproving(false);
    }
  };

  const selectedClaim = useMemo(
    () => claims.find((c) => c.id === selectedClaimId) ?? claims[0] ?? null,
    [claims, selectedClaimId]
  );

  const claimById = useMemo(() => {
    const map = new Map<string, BatchClaimItem>();
    for (const c of claims) {
      map.set(c.id, c);
    }
    return map;
  }, [claims]);

  const canApprove = Boolean(
    batch && batch.status !== "approved" && !approving
  );
  const isApproved = batch?.status === "approved";
  const countLabel = claims.length > 0 ? claims.length : 7;
  const paytmEntry = health?.integrations?.paytm;
  const paytmMode =
    typeof paytmEntry === "string" ? paytmEntry : paytmEntry?.mode;
  const paytmDown = paytmMode === "down";

  return (
    <div className="min-h-screen bg-[var(--paper)] p-4 text-[var(--text-1)]">
      <div className="mx-auto flex max-w-[1360px] flex-col gap-3">
        {/* Header */}
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--line)] pb-2.5">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-sign text-[var(--text-1)]">ADJUSTER DESK</h1>
            <StateLabel
              kind="simulated"
              text="Simulated insurer intake"
              surface="paper"
            />
            {batch ? (
              <StateLabel
                kind={isApproved ? "filed" : "replay"}
                text={
                  isApproved
                    ? "Batch for 21 Oct: approved"
                    : "Batch for 21 Oct: ready"
                }
                surface="paper"
              />
            ) : null}
            {paytmDown ? (
              <StateLabel
                kind="error"
                text="Paytm: Down"
                surface="paper"
              />
            ) : null}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Link
              to="/console"
              className="text-[14px] leading-[20px] font-semibold text-[var(--rust)] underline underline-offset-2"
            >
              Console
            </Link>
            <Link
              to="/merchant"
              className="text-[14px] leading-[20px] font-medium text-[var(--text-2)] underline underline-offset-2"
            >
              Merchant view
            </Link>

            <Button
              type="button"
              variant="rust"
              disabled={!canApprove}
              onClick={() => void handleApproveBatch()}
            >
              <CheckGlyph className="h-4 w-4" />
              <span>
                {isApproved
                  ? `Batch approved (${countLabel})`
                  : approving
                    ? "Approving batch..."
                    : `Approve batch (${countLabel})`}
              </span>
            </Button>
          </div>
        </header>

        {apiOffline ? (
          <div
            role="alert"
            className="flex items-center justify-between rounded-[4px] border border-[var(--danger-paper)] bg-[var(--card)] px-4 py-2.5 text-[14px] leading-[20px] font-semibold text-[var(--danger-paper)]"
          >
            <span>API offline</span>
            <StateLabel kind="error" text="Down" surface="paper" />
          </div>
        ) : null}

        {errorMsg ? (
          <div
            role="alert"
            className="rounded-[4px] border border-[var(--danger-paper)] bg-[var(--card)] p-3 text-[14px] leading-[20px] text-[var(--danger-paper)]"
          >
            {errorMsg}
          </div>
        ) : null}

        {/* Batch Claims Table */}
        <section
          aria-label="Batch claims table"
          className="rounded-[6px] border border-[var(--line)] bg-[var(--card)] p-3"
        >
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-baseline gap-3">
              <h2 className="font-heading text-[var(--text-1)]">
                Filed Claims in Batch
              </h2>
              <p className="text-[14px] leading-[20px] text-[var(--text-2)]">
                Eligibility and payout caps come from fixed, tested rules (2026.11-a). No AI decides money.
              </p>
            </div>
            <span className="font-figures text-[14px] leading-[20px] text-[var(--text-2)]">
              {claims.length} {claims.length === 1 ? "claim" : "claims"}
            </span>
          </div>

          {loading && claims.length === 0 ? (
            <div
              aria-label="Loading batch table"
              className="flex flex-col gap-2"
            >
              <div className="h-[36px] w-full rounded-[4px] bg-[var(--paper-2)]" />
              <div className="h-[44px] w-full rounded-[4px] bg-[var(--paper-2)]" />
              <div className="h-[44px] w-full rounded-[4px] bg-[var(--paper-2)]" />
            </div>
          ) : claims.length === 0 ? (
            <div className="rounded-[4px] border border-[var(--line)] bg-[var(--paper)] p-6 text-center text-[14px] leading-[20px] text-[var(--text-2)]">
              Batch is not ready yet. Run the flood on{" "}
              <Link to="/console" className="font-semibold text-[var(--rust)] underline">
                /console
              </Link>{" "}
              and tap consent for Selvi on{" "}
              <Link to="/merchant" className="font-semibold text-[var(--rust)] underline">
                /merchant
              </Link>{" "}
              to complete the batch of 7 claims.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Shop</TableHead>
                  <TableHead>Owner</TableHead>
                  <TableHead>Drop %</TableHead>
                  <TableHead>Quorum</TableHead>
                  <TableHead>Rain</TableHead>
                  <TableHead>Consent Time</TableHead>
                  <TableHead>Evidence Link</TableHead>
                  <TableHead>Rules Version</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {claims.map((claim) => {
                  const isSelected = selectedClaim?.id === claim.id;
                  const dropPct = computeDropPercent(
                    claim.baseline_paise,
                    claim.day_income_paise
                  );
                  return (
                    <TableRow
                      key={claim.id}
                      onClick={() => setSelectedClaimId(claim.id)}
                      className={cn(
                        "cursor-pointer",
                        isSelected && "bg-[var(--paper)]"
                      )}
                    >
                      <TableCell className="py-1.5 font-semibold">
                        {claim.shop_name}
                      </TableCell>
                      <TableCell className="py-1.5">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span>{claim.owner}</span>
                          {claim.simulated_label ? (
                            <StateLabel
                              kind="simulated"
                              text={claim.simulated_label}
                              surface="paper"
                            />
                          ) : (
                            <StateLabel
                              kind="live"
                              text="Merchant tap"
                              surface="paper"
                            />
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="py-1.5 font-figures">
                        <span>{dropPct}</span>{" "}
                        <span className="text-[12px] leading-[16px] text-[var(--text-3)]">
                          ({formatRupeesFromPaise(claim.baseline_paise)} -&gt;{" "}
                          {formatRupeesFromPaise(claim.day_income_paise)})
                        </span>
                      </TableCell>
                      <TableCell className="py-1.5 font-figures">
                        {formatQuorum(claim.quorum_share)}
                      </TableCell>
                      <TableCell className="py-1.5 font-figures">
                        {claim.rain_mm.toFixed(1)} mm
                      </TableCell>
                      <TableCell className="py-1.5 font-figures">
                        {formatClockTimeIST(claim.consent_at)}
                      </TableCell>
                      <TableCell className="py-1.5">
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedClaimId(claim.id);
                            }}
                            className="font-semibold text-[var(--rust)] underline underline-offset-2 cursor-pointer"
                          >
                            Preview
                          </button>
                          <a
                            href={claim.evidence_url}
                            target="_blank"
                            rel="noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="inline-flex items-center gap-1 text-[var(--text-2)] underline underline-offset-2"
                          >
                            <span>PDF</span>
                            <OpenExternalGlyph className="h-3.5 w-3.5" />
                          </a>
                        </div>
                      </TableCell>
                      <TableCell className="py-1.5 font-figures">
                        {claim.rules_version}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </section>

        {/* Bottom Grid: Evidence PDF Preview Pane + Live Plan-Fee Refunds */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_360px]">
          {/* Evidence PDF Preview Pane */}
          <section
            aria-label="Evidence PDF preview"
            className="flex flex-col gap-2 rounded-[6px] border border-[var(--line)] bg-[var(--card)] p-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--line)] pb-2">
              <div className="flex flex-wrap items-baseline gap-2">
                <h2 className="font-heading text-[var(--text-1)]">
                  Evidence Pack Preview
                </h2>
                <span className="text-[14px] leading-[20px] text-[var(--text-2)]">
                  {selectedClaim
                    ? `${selectedClaim.shop_name} (${selectedClaim.owner}) · ${selectedClaim.id}`
                    : "Select a claim row above to preview its evidence PDF."}
                </span>
              </div>
              {selectedClaim ? (
                <a
                  href={selectedClaim.evidence_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 rounded-[4px] border border-[var(--line)] bg-[var(--paper)] px-2.5 py-1 text-[14px] leading-[20px] font-semibold text-[var(--rust)]"
                >
                  <span>Open PDF</span>
                  <OpenExternalGlyph className="h-4 w-4" />
                </a>
              ) : null}
            </div>

            {selectedClaim ? (
              <iframe
                title={`Evidence PDF for ${selectedClaim.shop_name}`}
                src={`${selectedClaim.evidence_url}#toolbar=0&navpanes=0&view=FitH`}
                className="h-[430px] w-full rounded-[4px] border border-[var(--line)] bg-[var(--paper)]"
              />
            ) : (
              <div className="flex h-[320px] items-center justify-center rounded-[4px] border border-[var(--line)] bg-[var(--paper)] text-[14px] leading-[20px] text-[var(--text-3)]">
                No claim selected.
              </div>
            )}
          </section>

          {/* Plan-Fee Refunds Stream */}
          <section
            aria-label="Plan-fee refunds"
            className="flex flex-col gap-2 rounded-[6px] border border-[var(--line)] bg-[var(--card)] p-3"
          >
            <div className="flex items-center justify-between border-b border-[var(--line)] pb-3">
              <div className="flex items-center gap-2">
                <ReceiptGlyph className="h-4 w-4 text-[var(--rust)]" />
                <h2 className="font-sign-sm text-[var(--text-1)]">
                  PLAN-FEE REFUNDS
                </h2>
              </div>
              <span className="font-figures text-[14px] leading-[20px] text-[var(--text-2)]">
                {refunds.length} of {countLabel}
              </span>
            </div>

            {refunds.length === 0 ? (
              <div className="rounded-[4px] border border-[var(--line)] bg-[var(--paper)] p-4 text-[14px] leading-[20px] text-[var(--text-2)]">
                Click &ldquo;Approve batch ({countLabel})&rdquo; to approve all claims and trigger ₹35 monthly plan-fee refunds.
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {refunds.map((item) => {
                  const matchedClaim = claimById.get(item.claim_id);
                  const ownerLabel = matchedClaim
                    ? `${matchedClaim.owner} (${matchedClaim.shop_name})`
                    : item.shop_id || item.claim_id;
                  const isSim = item.label.toLowerCase().includes("simulated");
                  return (
                    <div
                      key={item.refund_id}
                      className="flex flex-col gap-1.5 rounded-[4px] border border-[var(--line)] bg-[var(--paper)] p-3 font-figures text-[14px] leading-[20px]"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-[var(--text-1)]">
                          {formatRupeesFromPaise(item.amount_paise)} -&gt; {ownerLabel}
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center justify-between gap-1.5">
                        <span className="break-all text-[12px] leading-[16px] text-[var(--text-3)]">
                          {item.refund_id}
                        </span>
                        <StateLabel
                          kind={isSim ? "simulated" : "filed"}
                          text={item.label}
                          surface="paper"
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
