import { cn } from "@/lib/utils";

export type StateLabelKind = "live" | "replay" | "simulated" | "filed" | "error";

export interface StateLabelProps {
  kind: StateLabelKind;
  text?: string;
  surface?: "dark" | "paper";
  className?: string;
}

const DEFAULT_TEXT: Record<StateLabelKind, string> = {
  live: "Live",
  replay: "Replay",
  simulated: "Simulated",
  filed: "Filed",
  error: "Error",
};

export function StateLabel({
  kind,
  text,
  surface = "dark",
  className,
}: StateLabelProps) {
  const labelText = text ?? DEFAULT_TEXT[kind];

  const colorClasses: Record<StateLabelKind, { dot: string; text: string; border: string }> =
    surface === "paper"
      ? {
          live: {
            dot: "bg-[var(--live-paper)]",
            text: "text-[var(--live-paper)]",
            border: "border-[var(--live-paper)]/40 bg-[var(--card)]",
          },
          replay: {
            dot: "bg-[var(--rust)]",
            text: "text-[var(--rust)]",
            border: "border-[var(--rust)]/40 bg-[var(--card)]",
          },
          simulated: {
            dot: "bg-[var(--text-3)]",
            text: "text-[var(--text-2)]",
            border: "border-[var(--line)] bg-[var(--card)]",
          },
          filed: {
            dot: "bg-[var(--ok-paper)]",
            text: "text-[var(--ok-paper)]",
            border: "border-[var(--ok-paper)]/40 bg-[var(--card)]",
          },
          error: {
            dot: "bg-[var(--danger-paper)]",
            text: "text-[var(--danger-paper)]",
            border: "border-[var(--danger-paper)]/40 bg-[var(--card)]",
          },
        }
      : {
          live: {
            dot: "bg-[var(--live)]",
            text: "text-[var(--live)]",
            border: "border-[var(--live)]/40 bg-[var(--ink-2)]",
          },
          replay: {
            dot: "bg-[var(--marigold)]",
            text: "text-[var(--marigold)]",
            border: "border-[var(--marigold)]/40 bg-[var(--ink-2)]",
          },
          simulated: {
            dot: "bg-[var(--text-dark-3)]",
            text: "text-[var(--text-dark-2)]",
            border: "border-[var(--line-dark)] bg-[var(--ink-2)]",
          },
          filed: {
            dot: "bg-[var(--ok)]",
            text: "text-[var(--ok)]",
            border: "border-[var(--ok)]/40 bg-[var(--ink-2)]",
          },
          error: {
            dot: "bg-[var(--danger)]",
            text: "text-[var(--danger)]",
            border: "border-[var(--danger)]/40 bg-[var(--ink-2)]",
          },
        };

  const styles = colorClasses[kind];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-[2px] border px-1.5 py-0.5 text-[11px] leading-[14px] font-medium uppercase tracking-[0.4px] whitespace-nowrap",
        styles.border,
        styles.text,
        className
      )}
    >
      <span className={cn("h-1.5 w-1.5 shrink-0", styles.dot)} aria-hidden="true" />
      <span>{labelText}</span>
    </span>
  );
}

