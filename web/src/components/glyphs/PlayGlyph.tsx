import type { SVGProps } from "react";

export interface GlyphProps extends SVGProps<SVGSVGElement> {
  title?: string;
}

export function PlayGlyph({ title, className, ...props }: GlyphProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      width="20"
      height="20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="square"
      strokeLinejoin="miter"
      aria-hidden={title ? undefined : true}
      role={title ? "img" : undefined}
      className={className}
      {...props}
    >
      {title ? <title>{title}</title> : null}
      <polygon points="6,4 16,10 6,16" />
    </svg>
  );
}

