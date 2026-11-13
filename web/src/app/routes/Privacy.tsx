import { Link } from "react-router-dom";

export function Privacy() {
  return (
    <div className="min-h-screen bg-[var(--paper)] p-6 text-[var(--text-1)]">
      <div className="mx-auto max-w-[720px] rounded-[6px] border border-[var(--line)] bg-[var(--card)] p-6">
        <div className="mb-4 flex items-center justify-between border-b border-[var(--line)] pb-3">
          <h1 className="font-heading">Privacy &amp; DPDPA Notice</h1>
          <Link
            to="/console"
            className="text-[13px] font-semibold text-[var(--rust)] underline underline-offset-2"
          >
            Back to /console
          </Link>
        </div>
        <p className="text-[15px] leading-[22px] text-[var(--text-2)]">
          Silent Claim shares only aggregated daily totals, 28-day baseline medians, street closure counts, and rainfall readings with the insurer after explicit merchant consent.
        </p>
      </div>
    </div>
  );
}

