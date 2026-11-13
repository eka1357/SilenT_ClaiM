import type { GlyphProps } from "./PlayGlyph";

export function OpenExternalGlyph({ title, className, ...props }: GlyphProps) {
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
      <polyline points="11,4 16,4 16,9" />
      <line x1="9" y1="11" x2="16" y2="4" />
      <polyline points="14,12 14,16 4,16 4,6 8,6" />
    </svg>
  );
}

