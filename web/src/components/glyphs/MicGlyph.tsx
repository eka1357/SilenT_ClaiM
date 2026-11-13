import type { GlyphProps } from "./PlayGlyph";

export function MicGlyph({ title, className, ...props }: GlyphProps) {
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
      <rect x="7.5" y="3" width="5" height="8" rx="2.5" />
      <path d="M5 9.5a5 5 0 0 0 10 0" />
      <line x1="10" y1="14.5" x2="10" y2="17" />
      <line x1="7" y1="17" x2="13" y2="17" />
    </svg>
  );
}

