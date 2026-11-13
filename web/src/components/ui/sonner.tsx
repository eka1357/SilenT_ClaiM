import { Toaster as Sonner } from "sonner";
import type { ComponentProps } from "react";

type ToasterProps = ComponentProps<typeof Sonner>;

export function Toaster({ ...props }: ToasterProps) {
  return (
    <Sonner
      toastOptions={{
        classNames: {
          toast:
            "rounded-[4px] border border-[var(--line-dark)] bg-[var(--ink-2)] text-[var(--text-dark-1)] font-body",
          description: "text-[var(--text-dark-2)] text-[12px]",
          actionButton:
            "bg-[var(--marigold)] text-[var(--ink)] font-semibold rounded-[4px]",
          cancelButton:
            "bg-[var(--ink-3)] text-[var(--text-dark-2)] rounded-[4px]",
        },
      }}
      {...props}
    />
  );
}

