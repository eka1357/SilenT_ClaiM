import { motion } from "motion/react";
import { cn } from "@/lib/utils";

export interface ShutterProps {
  isDown: boolean;
  className?: string;
}

export function Shutter({ isDown, className }: ShutterProps) {
  return (
    <motion.div
      initial={false}
      animate={{ height: isDown ? "56%" : "0%" }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      aria-hidden="true"
      className={cn(
        "pointer-events-none absolute inset-x-0 top-0 z-10 overflow-hidden border-b border-[var(--line-dark)] bg-[var(--ink-3)]",
        !isDown && "border-b-0",
        className
      )}
    >
      <svg
        viewBox="0 0 160 68"
        preserveAspectRatio="none"
        className="h-full w-full text-[var(--line-dark)]"
      >
        <line x1="0" y1="11" x2="160" y2="11" stroke="currentColor" strokeWidth="1.5" />
        <line x1="0" y1="22" x2="160" y2="22" stroke="currentColor" strokeWidth="1.5" />
        <line x1="0" y1="33" x2="160" y2="33" stroke="currentColor" strokeWidth="1.5" />
        <line x1="0" y1="44" x2="160" y2="44" stroke="currentColor" strokeWidth="1.5" />
        <line x1="0" y1="55" x2="160" y2="55" stroke="currentColor" strokeWidth="1.5" />
        <rect
          x="68"
          y="60"
          width="24"
          height="4"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.25"
        />
      </svg>
    </motion.div>
  );
}

