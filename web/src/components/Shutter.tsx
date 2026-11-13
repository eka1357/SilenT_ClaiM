import { motion, useReducedMotion } from "motion/react";
import { cn } from "@/lib/utils";

export interface ShutterProps {
  isDown: boolean;
  className?: string;
}

export function Shutter({ isDown, className }: ShutterProps) {
  const reducedMotion = useReducedMotion();

  return (
    <motion.div
      initial={false}
      animate={{ height: isDown ? "54%" : "0%" }}
      transition={
        reducedMotion
          ? { duration: 0 }
          : { duration: 0.55, ease: [0.22, 1, 0.36, 1] }
      }
      aria-hidden="true"
      className={cn(
        "pointer-events-none absolute inset-x-0 top-[28px] z-10 flex flex-col justify-between overflow-hidden bg-[var(--ink)]",
        isDown ? "border-y-2 border-[var(--line-dark)]" : "border-y-0",
        className
      )}
    >
      <div className="flex h-full w-full flex-col gap-[2px] bg-[var(--ink)]">
        <div className="flex-1 border-b border-[var(--line-dark)] bg-[var(--ink-3)]" />
        <div className="flex-1 border-b border-[var(--line-dark)] bg-[var(--ink-3)]" />
        <div className="flex-1 border-b border-[var(--line-dark)] bg-[var(--ink-3)]" />
        <div className="flex-1 border-b border-[var(--line-dark)] bg-[var(--ink-3)]" />
        <div className="flex-1 border-b border-[var(--line-dark)] bg-[var(--ink-3)]" />
        <div className="flex h-[8px] shrink-0 items-center justify-center border-t border-[var(--line-dark)] bg-[var(--ink-3)]">
          <div className="h-[3px] w-8 border border-[var(--text-dark-3)] bg-[var(--ink)]" />
        </div>
      </div>
    </motion.div>
  );
}
