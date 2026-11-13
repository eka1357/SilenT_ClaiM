import { cn } from "@/lib/utils";

export interface ConsentButtonProps {
  onConfirm: () => void;
  onDecline: () => void;
  disabled?: boolean;
  className?: string;
}

export function ConsentButton({
  onConfirm,
  onDecline,
  disabled = false,
  className,
}: ConsentButtonProps) {
  return (
    <div className={cn("flex flex-col gap-2.5", className)}>
      <button
        type="button"
        disabled={disabled}
        onClick={onConfirm}
        className="flex min-h-[56px] w-full flex-col items-center justify-center rounded-[6px] border border-[var(--marigold)] bg-[var(--marigold)] px-4 py-3 text-[var(--ink)] transition-opacity hover:opacity-90 disabled:opacity-50 cursor-pointer"
      >
        <span lang="ta" className="font-tamil font-semibold text-[var(--ink)]">
          ஆம், பதிவு செய்யுங்கள்
        </span>
        <span className="text-[14px] leading-[20px] font-medium text-[var(--ink)]">
          Yes, file it
        </span>
      </button>

      <button
        type="button"
        disabled={disabled}
        onClick={onDecline}
        className="flex min-h-[44px] w-full items-center justify-center gap-2 rounded-[6px] border border-[var(--line)] bg-[var(--card)] px-4 py-2 text-[var(--text-1)] hover:bg-[var(--paper)] disabled:opacity-50 cursor-pointer"
      >
        <span lang="ta" className="font-tamil text-[17px] leading-[24px]">
          வேண்டாம்
        </span>
        <span className="text-[14px] leading-[20px] text-[var(--text-2)]">
          (No)
        </span>
      </button>
    </div>
  );
}
