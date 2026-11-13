import { motion } from "motion/react";
import { cn } from "@/lib/utils";
import { StateLabel, type StateLabelKind } from "./StateLabel";

export type PhonePillState =
  | "Listening"
  | "Asking"
  | "Claim filed"
  | "Covered"
  | "Checking"
  | "Action needed"
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
    Listening: "live",
    Asking: "replay",
    "Claim filed": "filed",
    Covered: "live",
    Checking: "replay",
    "Action needed": "replay",
    Refunded: "filed",
  };

  return (
    <motion.div
      layout
      transition={{ duration: 0.2 }}
      aria-live="polite"
      className={cn(
        "flex items-center justify-between gap-2 rounded-[6px] border border-[var(--line)] bg-[var(--card)] px-2.5 py-1.5",
        className
      )}
    >
      <span className="font-heading text-[var(--text-1)]">{shopName}</span>
      <motion.div layout key={state}>
        <StateLabel kind={kindMap[state]} text={state} surface="paper" />
      </motion.div>
    </motion.div>
  );
}
