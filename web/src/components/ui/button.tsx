import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[4px] border text-[15px] leading-[22px] font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 cursor-pointer",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--marigold)] text-[var(--ink)] border-[var(--marigold)] hover:opacity-90 font-semibold",
        rust:
          "bg-[var(--rust)] text-[var(--paper)] border-[var(--rust)] hover:opacity-90 font-semibold",
        outline:
          "bg-[var(--ink-2)] text-[var(--text-dark-1)] border-[var(--line-dark)] hover:bg-[var(--ink-3)]",
        paperOutline:
          "bg-[var(--card)] text-[var(--text-1)] border-[var(--line)] hover:bg-[var(--paper)]",
        ghost:
          "border-transparent bg-transparent text-[var(--text-dark-2)] hover:text-[var(--text-dark-1)] hover:bg-[var(--ink-3)]",
        paperGhost:
          "border-transparent bg-transparent text-[var(--text-2)] hover:text-[var(--text-1)] hover:bg-[var(--paper)]",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 px-3 text-[12px] leading-[16px]",
        lg: "h-12 px-5 text-[16px] leading-[24px]",
        icon: "h-9 w-9 p-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

