import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertGlyph } from "@/components/glyphs/AlertGlyph";
import { CheckGlyph } from "@/components/glyphs/CheckGlyph";
import { RainDropGlyph } from "@/components/glyphs/RainDropGlyph";
import { ShutterGlyph } from "@/components/glyphs/ShutterGlyph";
import { ReceiptLine } from "@/components/ReceiptLine";
import { StateLabel, type StateLabelKind } from "@/components/StateLabel";
import {
  decideLabScenario,
  type LabDecideRequest,
  type LabDecideResponse,
  type LabHolidayMode,
} from "@/lib/api";

interface LabPreset {
  id: string;
  title: string;
  summary: string;
  expectedBadge: "Files the claim" | "Asks first" | "No action";
  knownLimitLabel?: string;
  params: LabDecideRequest;
}

const LAB_PRESETS: LabPreset[] = [
  {
    id: "flooded_street",
    title: "Flooded street",
    summary: "9 of 12 shops shut, 28 mm rain, 0% sales today, traded all 3 prior days.",
    expectedBadge: "Files the claim",
    params: {
      shops_closed: 9,
      rain_mm: 28,
      sales_today_pct: 0,
      days_traded_before: 3,
      regular_weekly_holiday: "none",
    },
  },
  {
    id: "lone_dry_drop",
    title: "One shop alone on a dry day",
    summary: "Only 1 shop closed, 0 mm rain, 0% sales today (for example, illness).",
    expectedBadge: "Asks first",
    params: {
      shops_closed: 1,
      rain_mm: 0,
      sales_today_pct: 0,
      days_traded_before: 3,
      regular_weekly_holiday: "none",
    },
  },
  {
    id: "leave_3_days_before",
    title: "On leave since 3 days before",
    summary: "Street floods today (9 closed, 28 mm), but shop was already shut for 3 days.",
    expectedBadge: "Asks first",
    params: {
      shops_closed: 9,
      rain_mm: 28,
      sales_today_pct: 0,
      days_traded_before: 0,
      regular_weekly_holiday: "none",
    },
  },
  {
    id: "strike_no_rain",
    title: "Street shut with no rain (strike)",
    summary: "9 of 12 shops shut together, but only 2 mm of rain fell today.",
    expectedBadge: "Asks first",
    params: {
      shops_closed: 9,
      rain_mm: 2,
      sales_today_pct: 0,
      days_traded_before: 3,
      regular_weekly_holiday: "none",
    },
  },
  {
    id: "holiday_today",
    title: "Closed today for its weekly holiday",
    summary: "Today is the shop's recurring weekly closing day across the prior 4 weeks.",
    expectedBadge: "No action",
    params: {
      shops_closed: 1,
      rain_mm: 0,
      sales_today_pct: 0,
      days_traded_before: 3,
      regular_weekly_holiday: "today",
    },
  },
  {
    id: "qr_switch_flood_day",
    title: "Moved to another QR on the flood day",
    summary: "Traded normally until yesterday, then switched QR on the exact flood morning.",
    expectedBadge: "Files the claim",
    knownLimitLabel: "Known limit: caught by consent and the adjuster",
    params: {
      shops_closed: 9,
      rain_mm: 28,
      sales_today_pct: 0,
      days_traded_before: 3,
      regular_weekly_holiday: "none",
    },
  },
  {
    id: "holiday_yesterday_flood_today",
    title: "Weekly holiday yesterday, flood today",
    summary: "Closed yesterday for its regular weekly holiday, then hit by today's flood.",
    expectedBadge: "Files the claim",
    params: {
      shops_closed: 9,
      rain_mm: 28,
      sales_today_pct: 0,
      days_traded_before: 2,
      regular_weekly_holiday: "yesterday",
    },
  },
];

const HOLIDAY_OPTIONS: { value: LabHolidayMode; label: string }[] = [
  { value: "none", label: "none" },
  { value: "yesterday", label: "yesterday" },
  { value: "today", label: "today" },
];

function decisionStateKind(
  decision: LabDecideResponse["decision"]
): StateLabelKind {
  if (decision === "file") return "filed";
  if (decision === "ask") return "replay";
  return "simulated";
}

export function Lab() {
  const [activePresetId, setActivePresetId] = useState<string>("flooded_street");
  const [params, setParams] = useState<LabDecideRequest>(LAB_PRESETS[0].params);
  const [result, setResult] = useState<LabDecideResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const evaluateScenario = useCallback(async (nextParams: LabDecideRequest) => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await decideLabScenario(nextParams);
      setResult(res);
    } catch (err) {
      setErrorMsg(
        err instanceof Error ? err.message : "Could not evaluate scenario"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void evaluateScenario(params);
  }, [evaluateScenario, params]);

  const handleSelectPreset = (preset: LabPreset) => {
    setActivePresetId(preset.id);
    setParams({ ...preset.params });
  };

  const handleParamChange = <K extends keyof LabDecideRequest>(
    key: K,
    value: LabDecideRequest[K]
  ) => {
    setActivePresetId("custom");
    setParams((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const activePreset = LAB_PRESETS.find((p) => p.id === activePresetId) ?? null;

  return (
    <div className="min-h-screen bg-[var(--paper)] text-[var(--text-1)]">
      <div className="mx-auto flex max-w-[1400px] flex-col gap-3 px-4 py-3 md:px-6 md:py-3">
        {/* Header */}
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--line)] pb-2.5">
          <div className="flex flex-col gap-0.5">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="font-label text-[var(--rust)]">
                SILENT CLAIM / TRY TO FOOL IT
              </span>
              <StateLabel
                kind="simulated"
                text="Simulated scenarios, same rules as production (2026.11-a)"
                surface="paper"
              />
            </div>
            <h1 className="font-sign text-[var(--text-1)]">
              Try to fool the detector
            </h1>
            <p className="text-[14px] leading-[20px] text-[var(--text-2)]">
              Every change runs the same fixed rules the product uses. No AI decides eligibility or money.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Link
              to="/console"
              className="rounded-[4px] border border-[var(--line)] bg-[var(--card)] px-3 py-1.5 text-[14px] leading-[20px] font-medium text-[var(--text-1)] hover:border-[var(--rust)]"
            >
              Console
            </Link>
            <Link
              to="/merchant"
              className="rounded-[4px] border border-[var(--line)] bg-[var(--card)] px-3 py-1.5 text-[14px] leading-[20px] font-medium text-[var(--text-1)] hover:border-[var(--rust)]"
            >
              Merchant Phone
            </Link>
            <Link
              to="/adjuster"
              className="rounded-[4px] border border-[var(--line)] bg-[var(--card)] px-3 py-1.5 text-[14px] leading-[20px] font-medium text-[var(--text-1)] hover:border-[var(--rust)]"
            >
              Adjuster Desk
            </Link>
          </div>
        </header>

        {errorMsg ? (
          <div
            role="alert"
            className="rounded-[4px] border border-[var(--bad-paper)] bg-[var(--card)] px-3 py-2 text-[14px] leading-[20px] text-[var(--bad-paper)]"
          >
            {errorMsg}
          </div>
        ) : null}

        {/* Main 12-column grid */}
        <div className="grid grid-cols-1 gap-3.5 lg:grid-cols-12">
          {/* Left column: Sliders + Live decision card (5 cols) */}
          <section
            aria-label="Scenario controls and live decision"
            className="flex flex-col gap-3 lg:col-span-5"
          >
            {/* Controls card */}
            <div className="flex flex-col gap-2.5 rounded-[6px] border border-[var(--line)] bg-[var(--card)] p-3.5">
              <div className="flex items-center justify-between border-b border-[var(--line)] pb-2">
                <h2 className="font-heading text-[var(--text-1)]">
                  Street and shop inputs
                </h2>
                <span className="font-mono-num text-[12px] leading-[16px] text-[var(--text-3)]">
                  12-shop street
                </span>
              </div>

              {/* Slider 1: Shops closed */}
              <div className="flex flex-col gap-1">
                <div className="flex items-center justify-between">
                  <label
                    htmlFor="slider-shops-closed"
                    className="flex items-center gap-1.5 text-[14px] leading-[20px] font-medium text-[var(--text-1)]"
                  >
                    <ShutterGlyph className="h-4 w-4 text-[var(--rust)]" />
                    <span>Shops closed on the street</span>
                  </label>
                  <span className="font-mono-num text-[14px] leading-[20px] font-semibold text-[var(--text-1)]">
                    {params.shops_closed} of 12 ({Math.round((params.shops_closed / 12) * 100)}%)
                  </span>
                </div>
                <input
                  id="slider-shops-closed"
                  type="range"
                  min={0}
                  max={12}
                  step={1}
                  value={params.shops_closed}
                  onChange={(e) =>
                    handleParamChange("shops_closed", Number(e.target.value))
                  }
                  className="w-full accent-[var(--rust)] cursor-pointer"
                />
                <div className="flex justify-between font-mono-num text-[12px] leading-[16px] text-[var(--text-3)]">
                  <span>0 closed</span>
                  <span>{result?.gates.quorum_gate_label ?? ""}</span>
                  <span>12 closed</span>
                </div>
              </div>

              {/* Slider 2: Rain mm */}
              <div className="flex flex-col gap-1">
                <div className="flex items-center justify-between">
                  <label
                    htmlFor="slider-rain-mm"
                    className="flex items-center gap-1.5 text-[14px] leading-[20px] font-medium text-[var(--text-1)]"
                  >
                    <RainDropGlyph className="h-4 w-4 text-[var(--rain)]" />
                    <span>Rainfall today</span>
                  </label>
                  <span className="font-mono-num text-[14px] leading-[20px] font-semibold text-[var(--text-1)]">
                    {params.rain_mm} mm
                  </span>
                </div>
                <input
                  id="slider-rain-mm"
                  type="range"
                  min={0}
                  max={60}
                  step={1}
                  value={params.rain_mm}
                  onChange={(e) =>
                    handleParamChange("rain_mm", Number(e.target.value))
                  }
                  className="w-full accent-[var(--rust)] cursor-pointer"
                />
                <div className="flex justify-between font-mono-num text-[12px] leading-[16px] text-[var(--text-3)]">
                  <span>0 mm</span>
                  <span>{result?.gates.rain_gate_label ?? ""}</span>
                  <span>60 mm</span>
                </div>
              </div>

              {/* Slider 3: Sales today % */}
              <div className="flex flex-col gap-1">
                <div className="flex items-center justify-between">
                  <label
                    htmlFor="slider-sales-pct"
                    className="text-[14px] leading-[20px] font-medium text-[var(--text-1)]"
                  >
                    Shop&apos;s sales today (% of usual ₹3,200)
                  </label>
                  <span className="font-mono-num text-[14px] leading-[20px] font-semibold text-[var(--text-1)]">
                    {params.sales_today_pct}%
                  </span>
                </div>
                <input
                  id="slider-sales-pct"
                  type="range"
                  min={0}
                  max={150}
                  step={5}
                  value={params.sales_today_pct}
                  onChange={(e) =>
                    handleParamChange("sales_today_pct", Number(e.target.value))
                  }
                  className="w-full accent-[var(--rust)] cursor-pointer"
                />
                <div className="flex justify-between font-mono-num text-[12px] leading-[16px] text-[var(--text-3)]">
                  <span>0% (shut)</span>
                  <span>{result?.gates.drop_gate_label ?? ""}</span>
                  <span>150%</span>
                </div>
              </div>

              {/* Slider 4: Days traded before */}
              <div className="flex flex-col gap-1">
                <div className="flex items-center justify-between">
                  <label
                    htmlFor="slider-days-before"
                    className="text-[14px] leading-[20px] font-medium text-[var(--text-1)]"
                  >
                    Days traded in the 3 days before
                  </label>
                  <span className="font-mono-num text-[14px] leading-[20px] font-semibold text-[var(--text-1)]">
                    {params.days_traded_before} of 3 days
                  </span>
                </div>
                <input
                  id="slider-days-before"
                  type="range"
                  min={0}
                  max={3}
                  step={1}
                  value={params.days_traded_before}
                  onChange={(e) =>
                    handleParamChange(
                      "days_traded_before",
                      Number(e.target.value)
                    )
                  }
                  className="w-full accent-[var(--rust)] cursor-pointer"
                />
                <div className="flex justify-between font-mono-num text-[12px] leading-[16px] text-[var(--text-3)]">
                  <span>0 days</span>
                  <span>{result?.gates.eligibility_gate_label ?? ""}</span>
                  <span>3 days</span>
                </div>
              </div>

              {/* Control 5: Regular weekly holiday: none / yesterday / today */}
              <div className="flex flex-col gap-1.5 border-t border-[var(--line)] pt-2.5">
                <span
                  id="holiday-control-label"
                  className="text-[14px] leading-[20px] font-medium text-[var(--text-1)]"
                >
                  Regular weekly holiday: none / yesterday / today
                </span>
                <div
                  role="group"
                  aria-labelledby="holiday-control-label"
                  className="grid grid-cols-3 gap-2"
                >
                  {HOLIDAY_OPTIONS.map((opt) => {
                    const selected =
                      params.regular_weekly_holiday === opt.value;
                    return (
                      <button
                        key={opt.value}
                        type="button"
                        aria-pressed={selected}
                        onClick={() =>
                          handleParamChange("regular_weekly_holiday", opt.value)
                        }
                        className={`rounded-[4px] border px-2.5 py-1.5 text-[14px] leading-[20px] font-semibold capitalize cursor-pointer ${
                          selected
                            ? "border-[var(--rust)] bg-[var(--rust)] text-[var(--paper)]"
                            : "border-[var(--line)] bg-[var(--paper)] text-[var(--text-1)] hover:border-[var(--rust)]"
                        }`}
                      >
                        {opt.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Live decision card */}
            <div
              data-testid="lab-decision-card"
              className="flex flex-col gap-2 rounded-[6px] border-2 border-[var(--text-1)] bg-[var(--card)] p-3.5"
            >
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--line)] pb-2.5">
                <div className="flex items-center gap-2">
                  {result?.decision === "file" ? (
                    <span className="flex h-6 w-6 items-center justify-center rounded-[4px] bg-[var(--ok-paper)] text-[var(--paper)]">
                      <CheckGlyph className="h-4 w-4" />
                    </span>
                  ) : (
                    <span className="flex h-6 w-6 items-center justify-center rounded-[4px] bg-[var(--warn-paper)] text-[var(--paper)]">
                      <AlertGlyph className="h-4 w-4" />
                    </span>
                  )}
                  <h2
                    data-testid="lab-decision-label"
                    className="font-sign-sm text-[var(--text-1)]"
                  >
                    {result ? result.decision_label : "Evaluating..."}
                  </h2>
                </div>
                {result ? (
                  <StateLabel
                    kind={decisionStateKind(result.decision)}
                    text={`decide() -> ${result.decision}`}
                    surface="paper"
                  />
                ) : null}
              </div>

              {activePreset?.knownLimitLabel ? (
                <div className="rounded-[4px] border border-[var(--warn-paper)] bg-[var(--paper)] px-2.5 py-1.5 text-[14px] leading-[20px] font-semibold text-[var(--warn-paper)]">
                  {activePreset.knownLimitLabel}
                </div>
              ) : null}

              <div className="flex flex-col gap-1">
                <span className="font-label text-[var(--text-3)]">
                  WHY THIS DECISION
                </span>
                <p
                  data-testid="lab-decision-explanation"
                  className="text-[14px] leading-[20px] text-[var(--text-1)]"
                >
                  {result ? result.explanation : "Running detector rules..."}
                </p>
              </div>

              <div className="flex flex-col gap-1 border-t border-[var(--line)] pt-2">
                <span className="font-label text-[var(--text-3)]">
                  WHAT HAPPENS NEXT
                </span>
                <p
                  data-testid="lab-decision-next-step"
                  className="text-[14px] leading-[20px] font-medium text-[var(--rust)]"
                >
                  {result ? result.next_step : "..."}
                </p>
              </div>

              {result ? (
                <div className="flex flex-col gap-1 border-t border-[var(--line)] pt-2">
                  <ReceiptLine label="Reason code" value={result.reason} />
                  <ReceiptLine
                    label={result.gates.quorum_receipt_label}
                    value={`${Math.round(result.quorum_share * 100)}% (${
                      result.quorum_met ? "met" : "not met"
                    })`}
                  />
                  <ReceiptLine
                    label={result.gates.rain_receipt_label}
                    value={`${result.rain_mm} mm (${
                      result.rain_gate_met ? "met" : "not met"
                    })`}
                  />
                  <ReceiptLine
                    label="Rules version"
                    value={result.rules_version}
                  />
                </div>
              ) : null}
              {loading ? (
                <span className="font-mono-num text-[12px] leading-[16px] text-[var(--text-3)]">
                  Updating...
                </span>
              ) : null}
            </div>
          </section>

          {/* Right column: Seven preset cards in a 2-column grid (7 cols) */}
          <section
            aria-label="Preset scenarios"
            className="flex flex-col gap-2.5 lg:col-span-7"
          >
            <div className="flex items-center justify-between">
              <h2 className="font-heading text-[var(--text-1)]">
                Seven edge-case presets
              </h2>
              <span className="text-[14px] leading-[20px] text-[var(--text-2)]">
                Click any card to load its sliders
              </span>
            </div>

            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
              {LAB_PRESETS.map((preset) => {
                const isSelected = activePresetId === preset.id;
                const badgeKind: StateLabelKind =
                  preset.expectedBadge === "Files the claim"
                    ? "filed"
                    : preset.expectedBadge === "Asks first"
                      ? "replay"
                      : "simulated";
                return (
                  <button
                    key={preset.id}
                    type="button"
                    data-testid={`preset-${preset.id}`}
                    onClick={() => handleSelectPreset(preset)}
                    className={`flex flex-col justify-between gap-1.5 rounded-[6px] border p-3 text-left cursor-pointer ${
                      isSelected
                        ? "border-2 border-[var(--rust)] bg-[var(--card)]"
                        : "border-[var(--line)] bg-[var(--card)] hover:border-[var(--text-2)]"
                    }`}
                  >
                    <div className="flex flex-col gap-1.5">
                      <div className="flex flex-wrap items-start justify-between gap-1.5">
                        <span className="text-[15px] leading-[20px] font-semibold text-[var(--text-1)]">
                          {preset.title}
                        </span>
                        <StateLabel
                          kind={badgeKind}
                          text={preset.expectedBadge}
                          surface="paper"
                        />
                      </div>
                      <p className="text-[14px] leading-[20px] text-[var(--text-2)]">
                        {preset.summary}
                      </p>
                      {preset.knownLimitLabel ? (
                        <span className="inline-block rounded-[4px] border border-[var(--warn-paper)] bg-[var(--paper)] px-2 py-0.5 text-[12px] leading-[16px] font-semibold text-[var(--warn-paper)]">
                          {preset.knownLimitLabel}
                        </span>
                      ) : null}
                    </div>

                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-[var(--line)] pt-2 font-mono-num text-[12px] leading-[16px] text-[var(--text-3)]">
                      <span>{preset.params.shops_closed}/12 shut</span>
                      <span>{preset.params.rain_mm} mm</span>
                      <span>{preset.params.sales_today_pct}% sales</span>
                      <span>{preset.params.days_traded_before}/3 prior</span>
                      <span>holiday: {preset.params.regular_weekly_holiday}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

