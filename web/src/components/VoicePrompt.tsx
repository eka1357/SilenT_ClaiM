import { useRef, useState } from "react";
import { PauseGlyph } from "@/components/glyphs/PauseGlyph";
import { PlayGlyph } from "@/components/glyphs/PlayGlyph";
import { cn } from "@/lib/utils";
import { StateLabel } from "./StateLabel";

export interface VoicePromptProps {
  promptTextTa: string;
  promptEn?: string;
  audioUrl?: string | null;
  live?: boolean;
  className?: string;
}

export function VoicePrompt({
  promptTextTa,
  promptEn = "Nine of twelve shops on your street were shut by the rain. Shall I file your insurance claim?",
  audioUrl,
  live = false,
  className,
}: VoicePromptProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);

  const handleTogglePlay = () => {
    const el = audioRef.current;
    if (!el) return;
    if (playing) {
      el.pause();
      setPlaying(false);
    } else {
      void el.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
    }
  };

  return (
    <div
      className={cn(
        "flex flex-col gap-2 rounded-[6px] border border-[var(--line)] bg-[var(--card)] p-3",
        className
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[12px] leading-[16px] font-semibold uppercase tracking-[0.4px] text-[var(--text-3)]">
          Tamil Voice Prompt (Sarvam Bulbul)
        </span>
        <StateLabel kind={live ? "live" : "replay"} surface="paper" />
      </div>

      <p lang="ta" className="font-tamil-prompt text-[var(--text-1)]">
        {promptTextTa}
      </p>

      <p className="text-[14px] leading-[20px] text-[var(--text-2)]">
        {promptEn}
      </p>

      {audioUrl ? (
        <div className="flex items-center gap-2 pt-1">
          <button
            type="button"
            onClick={handleTogglePlay}
            className="inline-flex items-center gap-1.5 rounded-[4px] border border-[var(--line)] bg-[var(--paper)] px-3 py-1.5 text-[14px] leading-[20px] font-medium text-[var(--text-1)] hover:border-[var(--rust)] cursor-pointer"
          >
            {playing ? (
              <PauseGlyph className="h-4 w-4 text-[var(--rust)]" />
            ) : (
              <PlayGlyph className="h-4 w-4 text-[var(--rust)]" />
            )}
            <span>{playing ? "Pause audio" : "Play Tamil audio"}</span>
          </button>
          <audio
            ref={audioRef}
            src={audioUrl}
            onEnded={() => setPlaying(false)}
            onPause={() => setPlaying(false)}
            preload="none"
          />
        </div>
      ) : null}
    </div>
  );
}
