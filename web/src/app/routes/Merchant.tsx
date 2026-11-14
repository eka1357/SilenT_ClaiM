import { useCallback, useEffect, useRef, useState } from "react";
import { useReducedMotion } from "motion/react";
import { Link } from "react-router-dom";
import { ConsentButton } from "@/components/ConsentButton";
import { CheckGlyph } from "@/components/glyphs/CheckGlyph";
import { MicGlyph } from "@/components/glyphs/MicGlyph";
import { OpenExternalGlyph } from "@/components/glyphs/OpenExternalGlyph";
import { ReceiptGlyph } from "@/components/glyphs/ReceiptGlyph";
import { PhoneFrame } from "@/components/PhoneFrame";
import { PhoneStatusPill, type PhonePillState } from "@/components/PhoneStatusPill";
import { ReceiptLine } from "@/components/ReceiptLine";
import { ShareDisclosure } from "@/components/ShareDisclosure";
import { StateLabel } from "@/components/StateLabel";
import { VoicePrompt } from "@/components/VoicePrompt";
import {
  getHealth,
  getStreet,
  type HealthResponse,
  type ShopView,
  submitConsent,
  submitVoice,
} from "@/lib/api";
import { formatRupeesFromPaise } from "@/lib/format";
import { connectEventStream } from "@/lib/stream";

const SELVI_SHOP_ID = "shop_01";

function formatTrackerTime(
  isoString?: string | null,
  fallback = "Pending"
): string {
  if (!isoString) return fallback;
  const parsed = new Date(isoString);
  if (Number.isNaN(parsed.getTime())) return fallback;
  const formatted = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(parsed);
  return `${formatted} IST`;
}

function classifyRefundStatus(
  status?: string | null
): "succeeded" | "pending" | "failed" | "none" {
  if (!status) return "none";
  const norm = status.trim();
  const upper = norm.toUpperCase();
  if (upper === "TXN_SUCCESS" || upper === "SUCCESS" || upper === "SIMULATED") {
    return "succeeded";
  }
  if (
    norm === "Pending at Paytm" ||
    upper === "PENDING" ||
    upper === "TXN_PENDING" ||
    upper === "INITIATED" ||
    upper === "PROCESSING"
  ) {
    return "pending";
  }
  return "failed";
}

function buildSilentWavBlob(): Blob {
  const sampleRate = 16000;
  const numSamples = sampleRate;
  const buffer = new ArrayBuffer(44 + numSamples * 2);
  const view = new DataView(buffer);

  function writeAscii(offset: number, str: string) {
    for (let i = 0; i < str.length; i += 1) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  }

  writeAscii(0, "RIFF");
  view.setUint32(4, 36 + numSamples * 2, true);
  writeAscii(8, "WAVE");
  writeAscii(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeAscii(36, "data");
  view.setUint32(40, numSamples * 2, true);

  return new Blob([buffer], { type: "audio/wav" });
}

export function Merchant() {
  const reducedMotion = useReducedMotion();
  const [selvi, setSelvi] = useState<ShopView | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiOffline, setApiOffline] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [confirmingCheck, setConfirmingCheck] = useState(false);
  const [recording, setRecording] = useState(false);
  const [declined, setDeclined] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);

  const refreshSelvi = useCallback(async () => {
    try {
      const [streetRes, healthRes] = await Promise.all([
        getStreet("panagal_park_road", "2026-10-21"),
        getHealth(),
      ]);
      const found =
        streetRes.shops.find((s) => s.shop_id === SELVI_SHOP_ID) ?? null;
      setSelvi(found);
      setHealth(healthRes);
      setApiOffline(false);
      if (found?.ask?.status === "declined") {
        setDeclined(true);
      } else if (found?.ask?.status === "pending") {
        setDeclined(false);
      }
    } catch {
      setApiOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshSelvi();
  }, [refreshSelvi]);

  useEffect(() => {
    const disconnect = connectEventStream({
      onDetectorDecision: (evt) => {
        if (evt.shop_id === SELVI_SHOP_ID) {
          void refreshSelvi();
        }
      },
      onAskSent: (evt) => {
        if (evt.shop_id === SELVI_SHOP_ID) {
          void refreshSelvi();
        }
      },
      onAskAnswered: () => {
        void refreshSelvi();
      },
      onClaimFiled: (evt) => {
        if (evt.shop_id === SELVI_SHOP_ID) {
          void refreshSelvi();
        }
      },
      onBatchReady: () => {
        void refreshSelvi();
      },
      onBatchApproved: () => {
        void refreshSelvi();
      },
      onRefundStatus: () => {
        void refreshSelvi();
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
  }, [refreshSelvi]);

  const handleConsent = async (consent: boolean) => {
    const askId = selvi?.ask?.id;
    if (!askId) return;
    setSubmitting(true);
    setErrorMsg(null);
    if (consent && !reducedMotion) {
      setConfirmingCheck(true);
    }
    try {
      await submitConsent(askId, consent);
      if (consent && !reducedMotion) {
        await new Promise((resolve) => window.setTimeout(resolve, 420));
      }
      if (!consent) {
        setDeclined(true);
      }
      await refreshSelvi();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to submit consent";
      setErrorMsg(msg);
    } finally {
      setConfirmingCheck(false);
      setSubmitting(false);
    }
  };

  const handleVoiceToggle = async () => {
    const askId = selvi?.ask?.id;
    if (!askId) return;

    if (recording && mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      setRecording(false);
      return;
    }

    setErrorMsg(null);
    if (
      typeof navigator !== "undefined" &&
      navigator.mediaDevices &&
      typeof navigator.mediaDevices.getUserMedia === "function" &&
      typeof window.MediaRecorder !== "undefined"
    ) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        chunksRef.current = [];
        const recorder = new MediaRecorder(stream);
        mediaRecorderRef.current = recorder;

        recorder.ondataavailable = (evt) => {
          if (evt.data.size > 0) {
            chunksRef.current.push(evt.data);
          }
        };

        recorder.onstop = () => {
          for (const track of stream.getTracks()) {
            track.stop();
          }
          const mimeType = recorder.mimeType || "audio/webm";
          const ext = mimeType.includes("ogg")
            ? "reply.ogg"
            : mimeType.includes("mp4")
              ? "reply.m4a"
              : "reply.webm";
          const blob =
            chunksRef.current.length > 0
              ? new Blob(chunksRef.current, { type: mimeType })
              : buildSilentWavBlob();
          setSubmitting(true);
          void submitVoice(askId, blob, ext)
            .then(() => refreshSelvi())
            .catch((err: unknown) => {
              const msg =
                err instanceof Error ? err.message : "Voice upload failed";
              setErrorMsg(msg);
            })
            .finally(() => setSubmitting(false));
        };

        recorder.start();
        setRecording(true);
        return;
      } catch {
        // Fallback when microphone permission is unavailable in headless/demo browser
      }
    }

    setSubmitting(true);
    try {
      const wavBlob = buildSilentWavBlob();
      await submitVoice(askId, wavBlob, "reply.wav");
      await refreshSelvi();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Voice upload failed";
      setErrorMsg(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const hasClaim = Boolean(selvi?.claim) && !confirmingCheck;
  const hasRefund = Boolean(selvi?.claim?.refund);
  const hasPendingAsk =
    (!selvi?.claim || confirmingCheck) &&
    !declined &&
    Boolean(selvi?.ask && (selvi.ask.status === "pending" || confirmingCheck));

  const pillState: PhonePillState =
    hasClaim || confirmingCheck
      ? "Claim filed"
      : hasPendingAsk
        ? "Asking"
        : "Listening";

  const sarvamEntry =
    health?.integrations?.sarvam ?? health?.integrations?.sarvam_tts;
  const sarvamMode =
    typeof sarvamEntry === "string" ? sarvamEntry : sarvamEntry?.mode;
  const sarvamLive = sarvamMode === "live";
  const sarvamDown = sarvamMode === "down";

  const baselineRupees = formatRupeesFromPaise(selvi?.baseline_paise ?? 320100);
  const todayRupees = formatRupeesFromPaise(selvi?.today_income_paise ?? 0);

  return (
    <div className="min-h-screen bg-[var(--ink)] px-4 py-1 text-[var(--text-dark-1)] max-[480px]:p-0">
      <div className="mx-auto mb-1 flex max-w-[390px] items-center justify-between max-[480px]:hidden">
        <Link
          to="/console"
          className="text-[14px] leading-[20px] font-medium text-[var(--marigold)] underline underline-offset-2"
        >
          Console
        </Link>
        <Link
          to="/adjuster"
          className="text-[14px] leading-[20px] font-medium text-[var(--text-dark-2)] underline underline-offset-2"
        >
          Adjuster desk
        </Link>
      </div>

      <PhoneFrame>
        <div className="flex flex-1 flex-col justify-between gap-2">
          <div className="flex flex-col gap-1.5">
            {apiOffline ? (
              <div
                role="alert"
                className="flex items-center justify-between rounded-[4px] border border-[var(--danger-paper)] bg-[var(--card)] px-3 py-1.5 text-[14px] leading-[20px] font-semibold text-[var(--danger-paper)]"
              >
                <span>API offline</span>
                <StateLabel kind="error" text="Down" surface="paper" />
              </div>
            ) : null}

            {sarvamDown ? (
              <div className="flex items-center justify-between rounded-[4px] border border-[var(--danger-paper)] bg-[var(--card)] px-3 py-1.5 text-[14px] leading-[20px] text-[var(--danger-paper)]">
                <span>Sarvam speech service</span>
                <StateLabel kind="error" text="Down" surface="paper" />
              </div>
            ) : null}

            <PhoneStatusPill
              state={pillState}
              shopName={`${selvi?.name ?? "Flower stall"} · ${selvi?.owner ?? "Selvi"}`}
            />

            {errorMsg ? (
              <div
                role="alert"
                className="rounded-[4px] border border-[var(--danger-paper)] bg-[var(--card)] p-2.5 text-[14px] leading-[20px] text-[var(--danger-paper)]"
              >
                {errorMsg}
              </div>
            ) : null}

            {loading && !selvi ? (
              <div
                aria-label="Loading merchant screen"
                className="flex flex-col gap-2"
              >
                <div className="h-[140px] w-full rounded-[6px] border border-[var(--line)] bg-[var(--paper-2)]" />
                <div className="h-[88px] w-full rounded-[6px] border border-[var(--line)] bg-[var(--paper-2)]" />
                <div className="h-[56px] w-full rounded-[6px] border border-[var(--line)] bg-[var(--paper-2)]" />
              </div>
            ) : null}

            {/* Screen 1: Listening */}
            {!loading && !hasPendingAsk && !hasClaim ? (
              <div className="flex flex-col gap-3 rounded-[6px] border border-[var(--line)] bg-[var(--card)] p-3.5">
                <div className="flex items-center justify-between border-b border-[var(--line)] pb-2">
                  <span className="text-[12px] leading-[16px] font-semibold uppercase tracking-[0.4px] text-[var(--text-3)]">
                    Panagal Park Road · 21 Oct 2026
                  </span>
                  <StateLabel kind="simulated" text="Simulated" surface="paper" />
                </div>

                <div className="flex flex-col gap-2 py-1">
                  <ReceiptLine label="Usual daily total" value={baselineRupees} />
                  <ReceiptLine label="Today so far" value={`${todayRupees} today`} />
                  <ReceiptLine label="Monthly cover fee" value="₹35" />
                </div>

                <p className="border-t border-[var(--line)] pt-2.5 text-[14px] leading-[20px] text-[var(--text-2)]">
                  {declined
                    ? "You chose not to file a claim for today."
                    : "When your Soundbox goes silent and most of Panagal Park Road shuts in heavy rain, Silent Claim asks one question in Tamil and files your claim on one tap."}
                </p>
              </div>
            ) : null}

            {/* Screen 2: Ask */}
            {hasPendingAsk && selvi?.ask ? (
              <>
                <VoicePrompt
                  promptTextTa={selvi.ask.prompt_text_ta}
                  promptEn="Nine of twelve shops on your street were shut by the rain. Shall I file your insurance claim?"
                  audioUrl={
                    selvi.ask.has_audio
                      ? `/api/asks/${encodeURIComponent(selvi.ask.id)}/audio`
                      : null
                  }
                  live={sarvamLive}
                />

                <ShareDisclosure />

                <ConsentButton
                  disabled={submitting}
                  confirmed={confirmingCheck}
                  onConfirm={() => void handleConsent(true)}
                  onDecline={() => void handleConsent(false)}
                />

                <div className="flex items-center justify-between rounded-[6px] border border-[var(--line)] bg-[var(--card)] px-3 py-1.5">
                  <span className="text-[14px] leading-[20px] text-[var(--text-2)]">
                    Need to explain in your own words?
                  </span>
                  <button
                    type="button"
                    disabled={submitting}
                    onClick={() => void handleVoiceToggle()}
                    className="inline-flex items-center gap-1.5 rounded-[4px] border border-[var(--line)] bg-[var(--paper)] px-2.5 py-1 text-[14px] leading-[20px] font-medium text-[var(--text-1)] hover:border-[var(--rust)] disabled:opacity-50 cursor-pointer"
                  >
                    <MicGlyph className="h-4 w-4 text-[var(--rust)]" />
                    <span>
                      {recording ? "Stop & send" : "Reply by voice"}
                    </span>
                  </button>
                </div>
              </>
            ) : null}

            {/* Screen 3 & 4: Filed + Money back */}
            {hasClaim && selvi?.claim ? (
              <div className="flex flex-col gap-3">
                <div className="flex flex-col gap-2.5 rounded-[6px] border border-[var(--ok-paper)]/40 bg-[var(--card)] p-3.5">
                  <div className="flex items-center justify-between border-b border-[var(--line)] pb-2.5">
                    <div className="flex items-center gap-2">
                      <span className="flex h-6 w-6 items-center justify-center rounded-[4px] bg-[var(--ok-paper)] text-[var(--paper)]">
                        <CheckGlyph className="h-4 w-4" />
                      </span>
                      <h2 className="font-heading text-[var(--text-1)]">
                        Claim filed
                      </h2>
                    </div>
                    <StateLabel kind="filed" text="Filed" surface="paper" />
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <ReceiptLine label="Forms filled" value={0} />
                    <ReceiptLine label="Usual daily total" value={baselineRupees} />
                    <ReceiptLine label="Event-day total" value="₹0 today" />
                    <ReceiptLine label="Street closures" value="9 of 12" />
                    <ReceiptLine label="Rainfall" value="27.7 mm" />
                  </div>

                  <div className="flex items-center justify-between border-t border-[var(--line)] pt-2.5">
                    <span className="text-[14px] leading-[20px] text-[var(--text-2)]">
                      Evidence pack ready
                    </span>
                    <a
                      href={selvi.claim.evidence_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 text-[14px] leading-[20px] font-semibold text-[var(--rust)] underline underline-offset-2"
                    >
                      <span>Evidence PDF</span>
                      <OpenExternalGlyph className="h-4 w-4" />
                    </a>
                  </div>
                </div>

                {/* Vertical claim tracker */}
                {(() => {
                  const refundState = classifyRefundStatus(
                    selvi.claim.refund?.status
                  );
                  const refundSucceeded = refundState === "succeeded";
                  const isApproved =
                    selvi.claim.status === "approved" ||
                    selvi.claim.status === "paid_sim" ||
                    Boolean(selvi.claim.approved_at) ||
                    hasRefund;
                  const refundTimeText = refundSucceeded
                    ? formatTrackerTime(
                        selvi.claim.refund?.created_at ??
                          selvi.claim.approved_at,
                        "Refunded"
                      )
                    : refundState === "pending"
                      ? "Pending at Paytm"
                      : refundState === "failed"
                        ? "Refund failed"
                        : "Queued on approval";
                  const steps = [
                    {
                      key: "asked",
                      title: "Asked",
                      done: true,
                      time: formatTrackerTime(
                        selvi.ask?.created_at ?? selvi.ask?.answered_at,
                        "22:01:00 IST"
                      ),
                      simulated: false,
                    },
                    {
                      key: "filed",
                      title: "Filed",
                      done: true,
                      time: formatTrackerTime(
                        selvi.claim.consent_at ?? selvi.claim.created_at,
                        "22:02:00 IST"
                      ),
                      simulated: false,
                    },
                    {
                      key: "approved",
                      title: "Approved by adjuster",
                      done: isApproved,
                      time: isApproved
                        ? formatTrackerTime(
                            selvi.claim.approved_at ??
                              selvi.claim.refund?.created_at,
                            "Approved"
                          )
                        : "Awaiting batch review",
                      simulated: false,
                    },
                    {
                      key: "refund",
                      title: "₹35 back",
                      done: refundSucceeded,
                      time: refundTimeText,
                      simulated: false,
                    },
                    {
                      key: "insurer_payout",
                      title: "Claim payout by insurer",
                      done: isApproved,
                      time: isApproved
                        ? formatTrackerTime(
                            selvi.claim.approved_at ??
                              selvi.claim.refund?.created_at,
                            "Queued"
                          )
                        : "After batch approval",
                      simulated: true,
                    },
                  ];
                  return (
                    <div
                      aria-label="Claim progress tracker"
                      className="flex flex-col gap-2 rounded-[6px] border border-[var(--line)] bg-[var(--card)] p-3.5"
                    >
                      <span className="font-label text-[var(--text-3)]">
                        CLAIM TRACKER
                      </span>
                      <ol className="flex flex-col">
                        {steps.map((step, idx) => {
                          const isLast = idx === steps.length - 1;
                          return (
                            <li
                              key={step.key}
                              className="relative flex items-start gap-2.5 pb-2.5 last:pb-0"
                            >
                              {!isLast ? (
                                <span
                                  aria-hidden="true"
                                  className={`absolute left-[9px] top-[20px] bottom-0 w-[2px] ${
                                    step.done
                                      ? "bg-[var(--ok-paper)]"
                                      : "bg-[var(--line)]"
                                  }`}
                                />
                              ) : null}
                              <span
                                aria-hidden="true"
                                className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${
                                  step.done
                                    ? "border-[var(--ok-paper)] bg-[var(--ok-paper)] text-[var(--paper)]"
                                    : "border-[var(--line)] bg-[var(--paper)] text-[var(--text-3)]"
                                }`}
                              >
                                {step.done ? (
                                  <CheckGlyph className="h-3 w-3" />
                                ) : (
                                  <span className="h-1.5 w-1.5 rounded-full bg-[var(--text-3)]" />
                                )}
                              </span>
                              <div className="flex min-w-0 flex-1 flex-wrap items-center justify-between gap-1">
                                <div className="flex flex-wrap items-center gap-1.5">
                                  <span
                                    className={`text-[14px] leading-[20px] ${
                                      step.done
                                        ? "font-semibold text-[var(--text-1)]"
                                        : "font-medium text-[var(--text-3)]"
                                    }`}
                                  >
                                    {step.title}
                                  </span>
                                  {step.simulated ? (
                                    <StateLabel
                                      kind="simulated"
                                      text="Simulated"
                                      surface="paper"
                                    />
                                  ) : null}
                                </div>
                                <span className="font-mono-num text-[12px] leading-[16px] text-[var(--text-2)]">
                                  {step.time}
                                </span>
                              </div>
                            </li>
                          );
                        })}
                      </ol>
                    </div>
                  );
                })()}

                {/* Screen 4: Money back receipt */}
                {hasRefund && selvi.claim.refund ? (
                  (() => {
                    const refundState = classifyRefundStatus(
                      selvi.claim.refund.status
                    );
                    const headingText =
                      refundState === "succeeded"
                        ? "₹35 returned"
                        : refundState === "pending"
                          ? "₹35 refund pending"
                          : "₹35 refund failed";
                    const labelKind =
                      refundState === "failed"
                        ? "error"
                        : selvi.claim.refund.label
                              .toLowerCase()
                              .includes("simulated")
                          ? "simulated"
                          : refundState === "pending"
                            ? "replay"
                            : "live";
                    return (
                      <div className="flex flex-col gap-2.5 rounded-[6px] border border-[var(--line)] bg-[var(--card)] p-3.5">
                        <div className="flex items-center justify-between border-b border-[var(--line)] pb-2">
                          <div className="flex items-center gap-2">
                            <ReceiptGlyph className="h-4 w-4 text-[var(--rust)]" />
                            <span className="font-sign-sm text-[var(--text-1)]">
                              {headingText}
                            </span>
                          </div>
                          <StateLabel
                            kind={labelKind}
                            text={selvi.claim.refund.label}
                            surface="paper"
                          />
                        </div>

                        <div className="flex flex-col gap-1.5">
                          <ReceiptLine
                            label="Plan fee refunded"
                            value={formatRupeesFromPaise(
                              selvi.claim.refund.amount_paise
                            )}
                          />
                          <ReceiptLine
                            label="Refund ID"
                            value={selvi.claim.refund.refund_id}
                          />
                          <ReceiptLine
                            label="Status"
                            value={selvi.claim.refund.status}
                          />
                        </div>
                      </div>
                    );
                  })()
                ) : (
                  <div className="rounded-[6px] border border-[var(--line)] bg-[var(--card)] p-3 text-[14px] leading-[20px] text-[var(--text-2)]">
                    Your evidence pack is in the adjuster batch. As soon as the adjuster approves the batch, this month&apos;s ₹35 plan fee is refunded automatically.
                  </div>
                )}
              </div>
            ) : null}
          </div>

          <footer className="flex items-center justify-between border-t border-[var(--line)] pt-1.5 text-[14px] leading-[20px] text-[var(--text-3)]">
            <span>Rules 2026.11-a</span>
            <Link
              to="/privacy"
              className="font-medium text-[var(--rust)] underline underline-offset-2"
            >
              Privacy Notice
            </Link>
          </footer>
        </div>
      </PhoneFrame>
    </div>
  );
}
