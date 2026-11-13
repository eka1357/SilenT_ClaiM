import { cn } from "@/lib/utils";

export interface ReceiptLineProps {
  label: string;
  value: string | number;
  className?: string;
}

export function ReceiptLine({ label, value, className }: ReceiptLineProps) {
  return (
    <div
      className={cn(
        "flex items-baseline justify-between gap-2 font-figures text-[13px] leading-[20px] text-[var(--text-1)]",
        className
      )}
    >
      <span className="shrink-0">{label}</span>
      <span
        aria-hidden="true"
        className="min-w-[16px] flex-1 border-b border-dotted border-[var(--text-3)]/60"
      />
      <span className="shrink-0 font-semibold">{value}</span>
    </div>
  );
}

