import { Link } from "react-router-dom";
import { StateLabel } from "@/components/StateLabel";

export function Privacy() {
  return (
    <div className="min-h-screen bg-[var(--paper)] p-6 text-[var(--text-1)]">
      <div className="mx-auto flex max-w-[720px] flex-col gap-5 rounded-[6px] border border-[var(--line)] bg-[var(--card)] p-6">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--line)] pb-4">
          <div className="flex items-center gap-3">
            <h1 className="font-sign text-[var(--text-1)]">PRIVACY NOTICE</h1>
            <StateLabel kind="simulated" text="Synthetic demo data" surface="paper" />
          </div>
          <div className="flex items-center gap-4 text-[14px] leading-[20px]">
            <Link
              to="/console"
              className="font-semibold text-[var(--rust)] underline underline-offset-2"
            >
              Console
            </Link>
            <Link
              to="/merchant"
              className="font-medium text-[var(--text-2)] underline underline-offset-2"
            >
              Merchant view
            </Link>
          </div>
        </header>

        <section className="flex flex-col gap-2">
          <h2 className="font-heading text-[var(--text-1)]">
            1. Synthetic Demo Data
          </h2>
          <p className="text-[15px] leading-[22px] text-[var(--text-2)]">
            All 12 shops on Panagal Park Road and their hourly payment histories are synthetic, simulated records generated from{" "}
            <code className="font-figures text-[14px]">data/shops.csv</code> and{" "}
            <code className="font-figures text-[14px]">data/street.csv</code>. No real merchant or customer data is stored or processed in this application.
          </p>
        </section>

        <section className="flex flex-col gap-2">
          <h2 className="font-heading text-[var(--text-1)]">
            2. Explicit Merchant Consent
          </h2>
          <p className="text-[15px] leading-[22px] text-[var(--text-2)]">
            When the deterministic detector (<code className="font-figures text-[14px]">rules.py</code>) flags a street flood event, the agent pauses and asks the merchant in Tamil whether to file their claim. A claim is filed only after the merchant taps consent (<code className="font-figures text-[14px]">POST /api/asks/&#123;id&#125;/consent</code>) or submits a voice reply classified as a flood closure.
          </p>
        </section>

        <section className="flex flex-col gap-2">
          <h2 className="font-heading text-[var(--text-1)]">
            3. What Is Sent to the Insurer Queue
          </h2>
          <p className="text-[15px] leading-[22px] text-[var(--text-2)]">
            When a claim is filed, the generated PDF evidence pack and adjuster batch include:
          </p>
          <ul className="list-disc space-y-1.5 pl-5 text-[14px] leading-[20px] text-[var(--text-2)]">
            <li>Shop name, owner name, shop category, and street name.</li>
            <li>The shop&apos;s 28-day median baseline and the last 7 daily payment totals (aggregated payment count and rupee total per day).</li>
            <li>The event-day payment total and drop percentage.</li>
            <li>The street closure quorum (for example, 9 of 12 shops shut on Panagal Park Road).</li>
            <li>Daily rainfall in millimetres from Open-Meteo and its source label.</li>
            <li>The merchant&apos;s consent timestamp in <code className="font-figures text-[14px]">Asia/Kolkata</code>, the deterministic rule version (<code className="font-figures text-[14px]">2026.11-a</code>), and a short summary sentence written by the configured LLM from those numbers (the LLM sets no eligibility or payout amount).</li>
          </ul>
        </section>

        <section className="flex flex-col gap-2">
          <h2 className="font-heading text-[var(--text-1)]">
            4. How Tamil Voice Notes Are Processed
          </h2>
          <p className="text-[15px] leading-[22px] text-[var(--text-2)]">
            When a merchant replies by voice note (<code className="font-figures text-[14px]">POST /api/asks/&#123;id&#125;/voice</code>, restricted to audio uploads up to 60 seconds and 2 MB):
          </p>
          <ul className="list-disc space-y-1.5 pl-5 text-[14px] leading-[20px] text-[var(--text-2)]">
            <li>
              The audio is sent to Sarvam AI&apos;s speech-to-text service (<code className="font-figures text-[14px]">saaras:v3</code>) to be transcribed into Tamil text.
            </li>
            <li>
              The Tamil transcript is sent to the configured LLM (<code className="font-figures text-[14px]">temperature=0</code>, <code className="font-figures text-[14px]">max_tokens=32</code>) to classify the reply into one of four fixed labels (<code className="font-figures text-[14px]">flood_closure</code>, <code className="font-figures text-[14px]">leave</code>, <code className="font-figures text-[14px]">qr_switch</code>, or <code className="font-figures text-[14px]">other</code>).
            </li>
            <li>
              Raw voice audio is held only in server memory during transcription, is removed immediately afterwards, is never written to the database, and is never sent to the insurer. The Tamil transcript and classified label are recorded on the ask record.
            </li>
          </ul>
        </section>

        <section className="flex flex-col gap-2">
          <h2 className="font-heading text-[var(--text-1)]">
            5. What Is Never Collected or Sent to the Insurer
          </h2>
          <ul className="list-disc space-y-1.5 pl-5 text-[14px] leading-[20px] text-[var(--text-2)]">
            <li>Customer names, phone numbers, UPI IDs, or individual customer transactions (only hourly shop totals exist in <code className="font-figures text-[14px]">payments_hourly</code>).</li>
            <li>Raw voice recordings (never stored on disk for merchant uploads and never sent to the insurer).</li>
            <li>Paytm merchant keys, checksums, and signatures (redacted by <code className="font-figures text-[14px]">redact_paytm_payload</code> before any log or database write).</li>
            <li>No user accounts, passwords, cookies, or browser storage tokens are used.</li>
          </ul>
        </section>
      </div>
    </div>
  );
}
