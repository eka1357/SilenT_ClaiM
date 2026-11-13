import { motion } from "motion/react";
import { AlertGlyph } from "@/components/glyphs/AlertGlyph";
import { CheckGlyph } from "@/components/glyphs/CheckGlyph";
import type { AgentStepEvent } from "@/lib/stream";
import { cn } from "@/lib/utils";
import { StateLabel } from "./StateLabel";

export interface CaseStepItem extends AgentStepEvent {
  id: string;
  shopId: string;
  shopLabel: string;
  nodeLabel: string;
  plainTitle: string;
  receivedAt: string;
}

export interface CaseLineProps {
  step: CaseStepItem;
  onOpenDetails: (step: CaseStepItem) => void;
  className?: string;
}

export function CaseLine({ step, onOpenDetails, className }: CaseLineProps) {
  const statusIcon =
    step.status === "error" ? (
      <AlertGlyph className="h-4 w-4 shrink-0 text-[var(--danger)]" />
    ) : step.status === "ok" ? (
      <CheckGlyph className="h-4 w-4 shrink-0 text-[var(--ok)]" />
    ) : (
      <span
        aria-label="Running"
        className="inline-block h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-[var(--marigold)] border-t-transparent"
      />
    );

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.18 }}
      className={cn(
        "flex items-center justify-between gap-3 rounded-[4px] border border-[var(--line-dark)] bg-[var(--ink-2)] px-3 py-1.5",
        className
      )}
    >
      <div className="flex min-w-0 items-center gap-2.5">
        {statusIcon}
        <span className="shrink-0 rounded-[2px] border border-[var(--line-dark)] bg-[var(--ink-3)] px-2 py-0.5 text-[12px] leading-[16px] font-medium uppercase tracking-[0.4px] text-[var(--text-dark-2)]">
          {step.nodeLabel}
        </span>
        <span className="truncate text-[14px] leading-[20px] text-[var(--text-dark-1)]">
          {step.plainTitle}
        </span>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <StateLabel kind={step.live ? "live" : "replay"} />
        <button
          type="button"
          onClick={() => onOpenDetails(step)}
          className="rounded-[2px] px-1.5 py-0.5 text-[14px] leading-[20px] font-medium text-[var(--marigold)] underline underline-offset-2 hover:opacity-85 cursor-pointer"
        >
          Details
        </button>
      </div>
    </motion.div>
  );
}
