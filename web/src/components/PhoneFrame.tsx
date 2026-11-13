import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { StateLabel } from "./StateLabel";

export interface PhoneFrameProps {
  children: ReactNode;
  className?: string;
}

export function PhoneFrame({ children, className }: PhoneFrameProps) {
  return (
    <div className="mx-auto flex w-full max-w-[390px] flex-col items-center max-[480px]:max-w-none">
      <div
        className={cn(
          "flex w-full max-w-[390px] flex-col justify-between rounded-[8px] border border-[var(--line)] bg-[var(--paper)] text-[var(--text-1)] max-[480px]:min-h-screen max-[480px]:max-w-none max-[480px]:rounded-none max-[480px]:border-0",
          className
        )}
      >
        <header className="flex items-center justify-between border-b border-[var(--line)] bg-[var(--card)] px-3 py-1">
          <span className="font-sign-sm text-[var(--text-1)]">
            SILENT CLAIM
          </span>
          <StateLabel kind="simulated" text="Simulated" surface="paper" />
        </header>

        <div className="flex flex-1 flex-col p-2">{children}</div>
      </div>

      <p className="mt-1.5 text-center text-[14px] leading-[20px] text-[var(--text-dark-2)] max-[480px]:mt-0 max-[480px]:w-full max-[480px]:bg-[var(--paper)] max-[480px]:pb-2 max-[480px]:pt-1 max-[480px]:text-[var(--text-2)]">
        Concept: inside Paytm for Business
      </p>
    </div>
  );
}
