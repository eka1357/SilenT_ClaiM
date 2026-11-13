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
        className="flex min-h-[56px] w-full flex-col items-center justify-center rounded-[6px] border border-[var(--rust)] bg-[var(--rust)] px-4 py-3 text-[var(--paper)] transition-opacity hover:opacity-90 disabled:opacity-50 cursor-pointer"
      >
        <span lang="ta" className="font-tamil font-semibold">
          ஆம், பதிவு செய்
        </span>
        <span className="text-[12px] leading-[16px] opacity-90">
          Yes, file my claim
        </span>
      </button>

      <button
        type="button"
        disabled={disabled}
        onClick={onDecline}
        className="flex min-h-[44px] w-full items-center justify-center gap-2 rounded-[6px] border border-[var(--line)] bg-[var(--card)] px-4 py-2 text-[var(--text-1)] hover:bg-[var(--paper)] disabled:opacity-50 cursor-pointer"
      >
        <span lang="ta" className="font-tamil text-[15px] leading-[22px]">
          வேண்டாம்
        </span>
        <span className="text-[12px] leading-[16px] text-[var(--text-2)]">
          (No)
        </span>
      </button>
    </div>
  );
}

