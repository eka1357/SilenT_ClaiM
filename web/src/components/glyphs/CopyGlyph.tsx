import type { GlyphProps } from "./PlayGlyph";

export function CopyGlyph({ title, className, ...props }: GlyphProps) {
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
      <rect x="7" y="7" width="9" height="9" />
      <polyline points="13,7 13,4 4,4 4,13 7,13" />
    </svg>
  );
}

