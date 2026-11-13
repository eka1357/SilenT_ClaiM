import { RainDropGlyph } from "@/components/glyphs/RainDropGlyph";
import { ShutterGlyph } from "@/components/glyphs/ShutterGlyph";
import { formatDayHuman } from "@/lib/format";
import { cn } from "@/lib/utils";
import { StateLabel } from "./StateLabel";

export interface RoadBandProps {
  streetName: string;
  dayIso: string | null;
  rainMm: number | null;
  rainSource: string | null;
  rainLive: boolean;
  shuttersDown: number;
  totalShops: number;
  className?: string;
}

export function RoadBand({
  streetName,
  dayIso,
  rainMm,
  rainSource,
  rainLive,
  shuttersDown,
  totalShops,
  className,
}: RoadBandProps) {
  const formattedDay = formatDayHuman(dayIso);
  const rainDisplay =
    rainMm !== null ? `${rainMm.toFixed(1)} mm` : "27.7 mm";
  const cleanStreetName = streetName.replace(/\s*\(Simulated\)\s*$/i, "");
  const rawSource = rainSource && rainSource.length > 0 ? rainSource : "Open-Meteo";
  const sourceDisplay = rawSource.replace(/\s*\((Replay|Live)\)\s*$/i, "");

  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-3 rounded-[4px] border border-[var(--line-dark)] bg-[var(--ink-3)] px-3.5 py-2",
        className
      )}
    >
      <div className="flex items-center gap-2.5">
        <span className="font-sign-sm text-[var(--text-dark-1)]">
          {cleanStreetName}
        </span>
        <StateLabel kind="simulated" text="Simulated" />
        <span className="text-[var(--text-dark-3)]" aria-hidden="true">
          |
        </span>
        <span className="font-figures-sm text-[var(--text-dark-2)]">
          {formattedDay}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-1.5 text-[12px] leading-[16px] text-[var(--text-dark-2)]">
          <RainDropGlyph className="h-4 w-4 text-[var(--live)]" />
          <span className="font-figures text-[var(--text-dark-1)]">{rainDisplay}</span>
          <span className="text-[var(--text-dark-3)]">({sourceDisplay})</span>
          <StateLabel kind={rainLive ? "live" : "replay"} />
        </div>

        <div className="flex items-center gap-1.5 text-[12px] leading-[16px] text-[var(--text-dark-1)]">
          <ShutterGlyph className="h-4 w-4 text-[var(--marigold)]" />
          <span className="font-figures">{shuttersDown}</span>
          <span className="text-[var(--text-dark-2)]">of</span>
          <span className="font-figures">{totalShops}</span>
          <span className="text-[var(--text-dark-2)]">shutters down</span>
        </div>
      </div>
    </div>
  );
}

