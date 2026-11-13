import type { GlyphProps } from "./PlayGlyph";

export function AlertGlyph({ title, className, ...props }: GlyphProps) {
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
      <polygon points="10,3 17.5,16.5 2.5,16.5" />
      <line x1="10" y1="8" x2="10" y2="11.5" />
      <line x1="10" y1="14" x2="10" y2="14.2" />
    </svg>
  );
}

