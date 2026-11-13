import type { GlyphProps } from "./PlayGlyph";

export function RainDropGlyph({ title, className, ...props }: GlyphProps) {
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
      <path d="M10 3C10 3 5 9 5 12.5C5 15.26 7.24 17 10 17C12.76 17 15 15.26 15 12.5C15 9 10 3 10 3Z" />
    </svg>
  );
}

