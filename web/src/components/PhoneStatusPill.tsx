import { cn } from "@/lib/utils";
import { StateLabel, type StateLabelKind } from "./StateLabel";

export type PhonePillState =
  | "Covered"
  | "Checking"
  | "Action needed"
  | "Claim filed"
  | "Refunded";

export interface PhoneStatusPillProps {
  state: PhonePillState;
  shopName: string;
  className?: string;
}

export function PhoneStatusPill({
  state,
  shopName,
  className,
}: PhoneStatusPillProps) {
  const kindMap: Record<PhonePillState, StateLabelKind> = {
    Covered: "live",
    Checking: "replay",
    "Action needed": "replay",
    "Claim filed": "filed",
    Refunded: "filed",
  };

  return (
    <div
      aria-live="polite"
      className={cn(
        "flex items-center justify-between gap-2 rounded-[6px] border border-[var(--line)] bg-[var(--card)] px-3.5 py-2.5",
        className
      )}
    >
      <div className="flex flex-col">
        <span className="text-[11px] leading-[14px] uppercase tracking-[0.4px] text-[var(--text-3)]">
          Silent Claim Protection
        </span>
        <span className="font-heading text-[var(--text-1)]">{shopName}</span>
      </div>
      <StateLabel kind={kindMap[state]} text={state} surface="paper" />
    </div>
  );
}

