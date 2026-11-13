import { cn } from "@/lib/utils";

export interface SparklineProps {
  values: number[];
  maxReference?: number;
  width?: number;
  height?: number;
  className?: string;
}

export function Sparkline({
  values,
  maxReference,
  width = 136,
  height = 24,
  className,
}: SparklineProps) {
  const padded = values.length > 0 ? values.slice(0, 24) : [0];
  const maxVal = Math.max(maxReference ?? 0, ...padded, 100);
  const padX = 3;
  const padY = 3;
  const innerW = Math.max(1, width - padX * 2);
  const innerH = Math.max(1, height - padY * 2);
  const denom = Math.max(1, padded.length - 1);

  const coords = padded.map((val, idx) => {
    const x = padX + (idx / denom) * innerW;
    const ratio = Math.min(1, Math.max(0, val / maxVal));
    const y = padY + innerH - ratio * innerH;
    return { x, y };
  });

  const pathData = coords
    .map((pt, idx) => `${idx === 0 ? "M" : "L"}${pt.x.toFixed(1)},${pt.y.toFixed(1)}`)
    .join(" ");

  const last = coords[coords.length - 1] ?? { x: padX, y: padY + innerH };

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      fill="none"
      aria-hidden="true"
      className={cn("overflow-visible", className)}
    >
      <path
        d={pathData}
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="square"
        strokeLinejoin="miter"
      />
      <circle cx={last.x} cy={last.y} r="2" fill="currentColor" />
    </svg>
  );
}

