import { Link } from "react-router-dom";
import { StateLabel } from "@/components/StateLabel";

export function Adjuster() {
  return (
    <div className="min-h-screen bg-[var(--paper)] p-6 text-[var(--text-1)]">
      <div className="mx-auto max-w-[1040px]">
        <header className="flex items-center justify-between border-b border-[var(--line)] pb-4">
          <div className="flex items-center gap-3">
            <h1 className="font-sign text-[var(--text-1)]">ADJUSTER DESK</h1>
            <StateLabel kind="simulated" text="Simulated insurer intake" surface="paper" />
          </div>
          <Link
            to="/console"
            className="text-[13px] font-semibold text-[var(--rust)] underline underline-offset-2"
          >
            Back to /console
          </Link>
        </header>
      </div>
    </div>
  );
}

