import type { GlyphProps } from "./PlayGlyph";

export function ReceiptGlyph({ title, className, ...props }: GlyphProps) {
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
      <polygon points="4,3 16,3 16,17 13,15 10,17 7,15 4,17" />
      <line x1="7" y1="7" x2="13" y2="7" />
      <line x1="7" y1="10.5" x2="13" y2="10.5" />
    </svg>
  );
}

