import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

export interface ShareDisclosureProps {
  className?: string;
}

export function ShareDisclosure({ className }: ShareDisclosureProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <div
        className={cn(
          "flex flex-col gap-0.5 rounded-[6px] border border-[var(--line)] bg-[var(--card)] p-2 text-[14px] leading-[18px] text-[var(--text-2)]",
          className
        )}
      >
        <p lang="ta" className="font-tamil-sm text-[var(--text-1)]">
          உங்கள் கடையின் 28 நாள் வருமானம், தெருவில் மூடிய கடைகளின் எண்ணிக்கை, மழை அளவு மட்டுமே காப்பீட்டு நிறுவனத்துக்கு அனுப்பப்படும்.
        </p>
        <div className="flex items-baseline justify-between gap-2 pt-0.5">
          <span className="font-semibold text-[var(--text-1)]">
            What we share with the insurer:
          </span>
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="shrink-0 text-[14px] leading-[18px] font-semibold text-[var(--rust)] underline underline-offset-2 cursor-pointer"
          >
            Details
          </button>
        </div>
        <p className="text-[14px] leading-[18px] text-[var(--text-2)]">
          Your shop&apos;s daily totals for 28 days, the street closure count (9 of 12), and the Open-Meteo rainfall reading, sent to the insurer queue to verify your flood-interruption claim.
        </p>
      </div>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>What We Share &amp; Why</SheetTitle>
            <SheetDescription>
              Exact data included in your income-protection evidence pack.
            </SheetDescription>
          </SheetHeader>

          <div className="mt-4 flex flex-col gap-4 overflow-y-auto text-[14px] leading-[20px] text-[var(--text-1)]">
            <div className="rounded-[4px] border border-[var(--line)] bg-[var(--card)] p-3">
              <div className="text-[12px] leading-[16px] font-semibold uppercase tracking-[0.4px] text-[var(--text-3)]">
                Sent to the Insurer Queue (Simulated Intake)
              </div>
              <ul className="mt-2 list-disc space-y-1.5 pl-5 text-[var(--text-2)]">
                <li>Shop name, owner name, category, and street name.</li>
                <li>Your 28-day median baseline and the last 7 daily payment totals (aggregated per day).</li>
                <li>Event-day payment total and drop percentage.</li>
                <li>Street closure quorum (9 of 12 shops shut on Panagal Park Road).</li>
                <li>Open-Meteo daily rainfall reading (27.7 mm) and source label.</li>
                <li>Your consent timestamp, deterministic rule version (2026.11-a), and a one-sentence summary generated from these numbers.</li>
              </ul>
            </div>

            <div className="rounded-[4px] border border-[var(--line)] bg-[var(--card)] p-3">
              <div className="text-[12px] leading-[16px] font-semibold uppercase tracking-[0.4px] text-[var(--text-3)]">
                How Voice Notes Are Processed
              </div>
              <p className="mt-1.5 text-[var(--text-2)]">
                If you reply by voice note, the audio (capped at 60 seconds and 2 MB) is sent to Sarvam AI&apos;s speech-to-text service in India to be transcribed into Tamil, and the transcript is classified into a closed cause label. Raw voice audio is never stored in the database and is never sent to the insurer.
              </p>
            </div>

            <div className="rounded-[4px] border border-[var(--line)] bg-[var(--card)] p-3">
              <div className="text-[12px] leading-[16px] font-semibold uppercase tracking-[0.4px] text-[var(--text-3)]">
                Never Sent to the Insurer
              </div>
              <p className="mt-1.5 text-[var(--text-2)]">
                Customer names, customer phone numbers, UPI IDs, individual transaction rows, and raw voice recordings are never included in the evidence pack.{" "}
                <Link
                  to="/privacy"
                  onClick={() => setOpen(false)}
                  className="font-semibold text-[var(--rust)] underline underline-offset-2"
                >
                  Read full Privacy Notice
                </Link>
              </p>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
