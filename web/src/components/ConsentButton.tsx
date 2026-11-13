import { motion, useReducedMotion } from "motion/react";
import { CheckGlyph } from "@/components/glyphs/CheckGlyph";
import { cn } from "@/lib/utils";

export interface ConsentButtonProps {
  onConfirm: () => void;
  onDecline: () => void;
  disabled?: boolean;
  confirmed?: boolean;
  className?: string;
}

export function ConsentButton({
  onConfirm,
  onDecline,
  disabled = false,
  confirmed = false,
  className,
}: ConsentButtonProps) {
  const reducedMotion = useReducedMotion();

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <motion.button
        type="button"
        disabled={disabled || confirmed}
        onClick={onConfirm}
        whileTap={reducedMotion ? undefined : { scale: 0.98 }}
        transition={{ duration: reducedMotion ? 0 : 0.09 }}
        className={cn(
          "flex min-h-[56px] w-full flex-col items-center justify-center rounded-[6px] border px-4 py-2 text-[var(--ink)] transition-colors duration-150 disabled:opacity-70 cursor-pointer",
          confirmed
            ? "border-[var(--ok-paper)] bg-[var(--ok-paper)] text-[var(--paper)]"
            : "border-[var(--marigold)] bg-[var(--marigold)] text-[var(--ink)] hover:opacity-90"
        )}
      >
        {confirmed ? (
          <motion.div
            initial={reducedMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: reducedMotion ? 0 : 0.18 }}
            className="flex items-center gap-2"
          >
            <CheckGlyph className="h-5 w-5 text-[var(--paper)]" />
            <span className="font-heading text-[var(--paper)]">
              Claim filed
            </span>
          </motion.div>
        ) : (
          <>
            <span lang="ta" className="font-tamil font-semibold text-[var(--ink)]">
              ஆம், பதிவு செய்யுங்கள்
            </span>
            <span className="text-[14px] leading-[18px] font-medium text-[var(--ink)]">
              Yes, file it
            </span>
          </>
        )}
      </motion.button>

      <button
        type="button"
        disabled={disabled || confirmed}
        onClick={onDecline}
        className="flex min-h-[38px] w-full items-center justify-center gap-2 rounded-[6px] border border-[var(--line)] bg-[var(--card)] px-4 py-1.5 text-[var(--text-1)] hover:bg-[var(--paper)] disabled:opacity-50 cursor-pointer"
      >
        <span lang="ta" className="font-tamil-sm">
          வேண்டாம்
        </span>
        <span className="text-[14px] leading-[20px] text-[var(--text-2)]">
          (No)
        </span>
      </button>
    </div>
  );
}
