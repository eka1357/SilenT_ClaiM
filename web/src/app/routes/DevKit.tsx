import { CaseFile, type RawStepRecord } from "@/components/CaseFile";
import { ConsentButton } from "@/components/ConsentButton";
import {
  AlertGlyph,
  CheckGlyph,
  ChevronGlyph,
  CloseGlyph,
  CopyGlyph,
  MicGlyph,
  OpenExternalGlyph,
  PauseGlyph,
  PlayGlyph,
  RainDropGlyph,
  ReceiptGlyph,
  ShutterGlyph,
} from "@/components/glyphs";
import { PhoneFrame } from "@/components/PhoneFrame";
import { PhoneStatusPill } from "@/components/PhoneStatusPill";
import { Receipt } from "@/components/Receipt";
import { RoadBand } from "@/components/RoadBand";
import { ShareDisclosure } from "@/components/ShareDisclosure";
import { Shopfront } from "@/components/Shopfront";
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
import { VoicePrompt } from "@/components/VoicePrompt";
import type { MetricsResponse, ShopView } from "@/lib/api";

const SAMPLE_SHOPS: ShopView[] = [
  {
    shop_id: "shop_01",
    name: "Selvi Flowers",
    owner: "Selvi",
    category: "Florist",
    lat: 13.0418,
    lon: 80.2341,
    plan_active: true,
    status: "dropped",
    baseline_paise: 320100,
    today_income_paise: 0,
    hourly: [
      { ts_hour: "2026-10-21T07:00:00+05:30", n_payments: 0, amount_paise: 0 },
      { ts_hour: "2026-10-21T08:00:00+05:30", n_payments: 0, amount_paise: 0 },
    ],
    detection: {
      id: "det_20261021_shop_01",
      day: "2026-10-21",
      baseline_paise: 320100,
      day_income_paise: 0,
      dropped: true,
      eligible: true,
      quorum_share: 0.75,
      rain_mm: 27.7,
      rain_source: "Open-Meteo",
      decision: "file",
      reason: "rain_and_quorum",
      rules_version: "2026.11-a",
    },
    ask: {
      id: "ask_20261021_shop_01",
      ask_kind: "consent",
      status: "pending",
      prompt_text_ta:
        "மழையால் உங்கள் தெருவில் 12 கடைகளில் 9 மூடியிருந்தன. உங்கள் காப்பீட்டுக் கோரிக்கையை நான் பதிவு செய்யட்டுமா?",
      has_audio: true,
      reply_type: null,
      transcript: null,
      cause_label: null,
      confidence: null,
      simulated_label: null,
      answered_at: null,
    },
    claim: null,
  },
  {
    shop_id: "shop_02",
    name: "Bala Tiffin Centre",
    owner: "Bala",
    category: "Tiffin",
    lat: 13.0419,
    lon: 80.2342,
    plan_active: true,
    status: "dropped",
    baseline_paise: 485000,
    today_income_paise: 0,
    hourly: [
      { ts_hour: "2026-10-21T07:00:00+05:30", n_payments: 0, amount_paise: 0 },
    ],
    detection: null,
    ask: {
      id: "ask_20261021_shop_02",
      ask_kind: "consent",
      status: "answered",
      prompt_text_ta:
        "மழையால் உங்கள் தெருவில் 12 கடைகளில் 9 மூடியிருந்தன. உங்கள் காப்பீட்டுக் கோரிக்கையை நான் பதிவு செய்யட்டுமா?",
      has_audio: true,
      reply_type: "tap",
      transcript: null,
      cause_label: "rain",
      confidence: 1.0,
      simulated_label: "Simulated consent",
      answered_at: "2026-10-21T22:05:00+05:30",
    },
    claim: {
      id: "clm_20261021_shop_02",
      status: "filed",
      batch_id: "bat_20261021",
      consent_at: "2026-10-21T22:05:00+05:30",
      evidence_url: "/api/evidence/clm_20261021_shop_02.pdf",
      refund: null,
    },
  },
  {
    shop_id: "shop_07",
    name: "Kani Fancy Store",
    owner: "Kani",
    category: "Fancy",
    lat: 13.0422,
    lon: 80.2345,
    plan_active: true,
    status: "dropped",
    baseline_paise: 290000,
    today_income_paise: 0,
    hourly: [
      { ts_hour: "2026-10-21T07:00:00+05:30", n_payments: 0, amount_paise: 0 },
    ],
    detection: null,
    ask: {
      id: "ask_20261021_shop_07",
      ask_kind: "voice",
      status: "answered",
      prompt_text_ta:
        "இன்று உங்கள் கடையில் Paytm பரிவர்த்தனைகள் குறைந்துள்ளன. கடை மூடப்பட்டதற்கான காரணத்தை குரல் பதிவில் சொல்லுங்கள்.",
      has_audio: true,
      reply_type: "voice",
      transcript: "நான் வெளியூர் சென்றிருந்தேன்",
      cause_label: "travel",
      confidence: 0.94,
      simulated_label: "Simulated reply",
      answered_at: "2026-10-21T22:06:00+05:30",
    },
    claim: null,
  },
  {
    shop_id: "shop_11",
    name: "Maran Medicals",
    owner: "Maran",
    category: "Medicals",
    lat: 13.0424,
    lon: 80.2348,
    plan_active: true,
    status: "trading",
    baseline_paise: 620000,
    today_income_paise: 590000,
    hourly: [
      { ts_hour: "2026-10-21T08:00:00+05:30", n_payments: 5, amount_paise: 45000 },
      { ts_hour: "2026-10-21T09:00:00+05:30", n_payments: 8, amount_paise: 78000 },
      { ts_hour: "2026-10-21T10:00:00+05:30", n_payments: 9, amount_paise: 89000 },
      { ts_hour: "2026-10-21T11:00:00+05:30", n_payments: 7, amount_paise: 64000 },
    ],
    detection: null,
    ask: null,
    claim: null,
  },
];

const SAMPLE_STEPS: RawStepRecord[] = [
  {
    id: "kit-step-1",
    receivedAt: "2026-10-21T22:00:01+05:30",
    event: {
      node: "sense",
      status: "ok",
      detail: "shop_01 income=0p baseline=320100p dropped=True",
      live: true,
    },
  },
  {
    id: "kit-step-2",
    receivedAt: "2026-10-21T22:00:02+05:30",
    event: {
      node: "confirm",
      status: "ok",
      detail: "shop_01 -> file (rain_and_quorum), quorum=9/12, rain=27.7mm",
      live: false,
    },
  },
  {
    id: "kit-step-3",
    receivedAt: "2026-10-21T22:00:03+05:30",
    event: {
      node: "ask",
      status: "ok",
      detail: "Ask ask_20261021_shop_01 (consent) sent to shop_01",
      live: false,
    },
  },
];

const SAMPLE_METRICS: MetricsResponse = {
  forms_filled: 0,
  taps: 7,
  merchant_taps: 1,
  adjuster_taps: 1,
  claims_filed_in_run: 7,
  avg_time_to_file_seconds: 14,
  max_time_to_file_seconds: 14,
  time_to_file_by_claim: [],
  refunds: {
    count: 1,
    total_amount_paise: 3500,
    payback_enabled: true,
    items: [
      {
        claim_id: "clm_20261021_shop_01",
        shop_id: "shop_01",
        refund_id: "SC-clm_20261021_shop_01",
        amount_paise: 3500,
        status: "simulated",
        label: "Simulated: keys pending",
      },
    ],
  },
  eval: {
    label: "Simulated eval",
    rules_version: "2026.11-a",
    split: "held_out",
    total_cases: 60,
    claims_filed: 18,
    claims_right: 18,
    wrong_claims: 0,
    wrong_claim_share: 0,
    false_positive_rate: 0,
    closures_missed: 0,
    total_closures: 18,
    missed_claim_rate: 0,
  },
  integrations: {
    open_meteo: "replay",
    sarvam: "replay",
    llm: "replay",
    paytm: "simulated",
  },
};

export function DevKit() {
  return (
    <div className="min-h-screen bg-[var(--ink)] p-6 text-[var(--text-dark-1)]">
      <div className="mx-auto flex max-w-[1400px] flex-col gap-8">
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-[var(--line-dark)] pb-4">
          <div>
            <h1 className="font-sign">SILENT CLAIM / DEV KIT</h1>
            <p className="text-[var(--text-dark-2)]">
              Chennai street-sign typography, dark wet-asphalt console tokens, and warm paper receipts.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <StateLabel kind="live" />
            <StateLabel kind="replay" />
            <StateLabel kind="simulated" />
            <StateLabel kind="filed" />
            <StateLabel kind="error" />
          </div>
        </header>

        {/* Glyphs & Buttons */}
        <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="rounded-[6px] border border-[var(--line-dark)] bg-[var(--ink-2)] p-4">
            <h2 className="font-heading mb-3">12 Custom 20x20 SVG Glyphs</h2>
            <div className="grid grid-cols-4 gap-3 sm:grid-cols-6">
              {[
                { name: "play", el: <PlayGlyph /> },
                { name: "pause", el: <PauseGlyph /> },
                { name: "mic", el: <MicGlyph /> },
                { name: "check", el: <CheckGlyph /> },
                { name: "alert", el: <AlertGlyph /> },
                { name: "copy", el: <CopyGlyph /> },
                { name: "open-external", el: <OpenExternalGlyph /> },
                { name: "chevron", el: <ChevronGlyph /> },
                { name: "close", el: <CloseGlyph /> },
                { name: "rain-drop", el: <RainDropGlyph /> },
                { name: "shutter", el: <ShutterGlyph /> },
                { name: "receipt", el: <ReceiptGlyph /> },
              ].map((g) => (
                <div
                  key={g.name}
                  className="flex flex-col items-center gap-1.5 rounded-[4px] border border-[var(--line-dark)] bg-[var(--ink)] p-2.5"
                >
                  <span className="text-[var(--marigold)]">{g.el}</span>
                  <span className="font-figures-sm text-[var(--text-dark-2)]">
                    {g.name}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[6px] border border-[var(--line-dark)] bg-[var(--ink-2)] p-4">
            <h2 className="font-heading mb-3">Restyled Primitives &amp; Typography</h2>
            <div className="flex flex-wrap gap-2 pb-4">
              <Button>Marigold Primary</Button>
              <Button variant="rust">Rust Paper Action</Button>
              <Button variant="outline">Dark Outline</Button>
              <Button variant="ghost">Ghost</Button>
            </div>
            <div className="flex flex-col gap-1 border-t border-[var(--line-dark)] pt-3">
              <span className="font-sign-sm">PANAGAL PARK ROAD (Sign)</span>
              <span className="font-heading">Section Heading (18px / 24px)</span>
              <span className="font-body">Body copy in Anek Tamil (15px / 22px)</span>
              <span lang="ta" className="font-tamil text-[var(--marigold)]">
                மழையால் உங்கள் தெருவில் 12 கடைகளில் 9 மூடியிருந்தன. (Tamil 17px / 27px)
              </span>
              <span className="font-figures text-[var(--live)]">
                ₹3,201 · 27.7 mm · 00:14 · SC-01 (IBM Plex Mono tabular-nums)
              </span>
            </div>
          </div>
        </section>

        {/* Street tiles & RoadBand */}
        <section className="flex flex-col gap-3 rounded-[6px] border border-[var(--line-dark)] bg-[var(--ink-2)] p-4">
          <h2 className="font-heading">Shopfront Tiles, Shutter &amp; RoadBand</h2>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {SAMPLE_SHOPS.map((shop) => (
              <Shopfront key={shop.shop_id} shop={shop} />
            ))}
          </div>
          <RoadBand
            streetName="Panagal Park Road"
            dayIso="2026-10-21"
            rainMm={27.7}
            rainSource="Open-Meteo"
            rainLive={false}
            shuttersDown={9}
            totalShops={12}
          />
        </section>

        {/* Case File, Receipt & PhoneFrame */}
        <section className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          <CaseFile steps={SAMPLE_STEPS} shops={SAMPLE_SHOPS} />

          <Receipt
            metrics={SAMPLE_METRICS}
            batchId="bat_20261021"
            batchCount={7}
            batchStatus="pending"
            refunds={SAMPLE_METRICS.refunds.items}
            shops={SAMPLE_SHOPS}
          />

          <PhoneFrame className="min-h-[560px]">
            <div className="flex flex-col gap-4">
              <PhoneStatusPill state="Action needed" shopName="Selvi Flowers" />
              <VoicePrompt
                promptTextTa="மழையால் உங்கள் தெருவில் 12 கடைகளில் 9 மூடியிருந்தன. உங்கள் காப்பீட்டுக் கோரிக்கையை நான் பதிவு செய்யட்டுமா?"
                live={false}
              />
              <ConsentButton
                onConfirm={() => undefined}
                onDecline={() => undefined}
              />
              <ShareDisclosure />
            </div>
          </PhoneFrame>
        </section>

        {/* Paper Table Preview */}
        <section className="rounded-[6px] border border-[var(--line)] bg-[var(--paper)] p-4 text-[var(--text-1)]">
          <h2 className="font-heading mb-3">Restyled Paper Table</h2>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Shop</TableHead>
                <TableHead>Baseline</TableHead>
                <TableHead>Today</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell className="font-medium">Selvi Flowers</TableCell>
                <TableCell className="font-figures">₹3,201</TableCell>
                <TableCell className="font-figures">₹0</TableCell>
                <TableCell>
                  <StateLabel kind="filed" surface="paper" />
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </section>
      </div>
    </div>
  );
}

