import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";

export interface ShareDisclosureProps {
  className?: string;
}

export function ShareDisclosure({ className }: ShareDisclosureProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-2 rounded-[6px] border border-[var(--line)] bg-[var(--paper)] p-3 text-[12px] leading-[16px] text-[var(--text-2)]",
        className
      )}
    >
      <div>
        <span className="font-semibold text-[var(--text-1)]">
          Shared with the insurer:
        </span>{" "}
        today&apos;s total vs your 28-day median, street closure count (9 of 12), and Open-Meteo rainfall.
      </div>
      <div>
        <span className="font-semibold text-[var(--text-1)]">
          Never shared:
        </span>{" "}
        customer names, UPI IDs, individual transactions, or raw voice audio.{" "}
        <Link
          to="/privacy"
          className="font-medium text-[var(--rust)] underline underline-offset-2"
        >
          Privacy &amp; DPDPA notice
        </Link>
      </div>
    </div>
  );
}

