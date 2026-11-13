import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { StateLabel } from "./StateLabel";

export interface PhoneFrameProps {
  children: ReactNode;
  className?: string;
}

export function PhoneFrame({ children, className }: PhoneFrameProps) {
  return (
    <div
      className={cn(
        "mx-auto flex min-h-[760px] w-full max-w-[390px] flex-col justify-between rounded-[8px] border border-[var(--line)] bg-[var(--paper)] text-[var(--text-1)]",
        className
      )}
    >
      <header className="flex items-center justify-between border-b border-[var(--line)] bg-[var(--card)] px-4 py-2.5">
        <span className="text-[11px] leading-[14px] font-medium text-[var(--text-2)]">
          Concept: inside Paytm for Business
        </span>
        <StateLabel kind="simulated" text="Simulated shell" surface="paper" />
      </header>

      <div className="flex flex-1 flex-col p-4">{children}</div>
    </div>
  );
}

