import { useCallback, useEffect, useRef, useState } from "react";
import { PauseGlyph } from "@/components/glyphs/PauseGlyph";
import { PlayGlyph } from "@/components/glyphs/PlayGlyph";
import { cn } from "@/lib/utils";
import { StateLabel } from "./StateLabel";

const WAVEFORM_PEAKS = [5, 11, 8, 15, 12, 18, 9, 14, 17, 10, 6, 13, 16, 11, 7, 4];

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
  const [durationSec, setDurationSec] = useState<number>(6);

  const handleTogglePlay = useCallback(() => {
    const el = audioRef.current;
    if (!el) return;
    if (playing) {
      el.pause();
      setPlaying(false);
    } else {
      void el.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
    }
  }, [playing]);

  useEffect(() => {
    if (!audioUrl) return;
    const onKeyDown = (evt: KeyboardEvent) => {
      if (evt.code !== "Space") return;
      const target = evt.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "BUTTON" ||
          target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "A")
      ) {
        return;
      }
      evt.preventDefault();
      handleTogglePlay();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [audioUrl, handleTogglePlay]);

  const mins = Math.floor(durationSec / 60);
  const secs = Math.round(durationSec % 60);
  const formattedDuration = `${mins}:${String(secs).padStart(2, "0")}`;

  return (
    <div
      className={cn(
        "flex flex-col gap-1 rounded-[6px] border border-[var(--line)] bg-[var(--card)] p-2",
        className
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[12px] leading-[16px] font-semibold uppercase tracking-[0.4px] text-[var(--text-3)]">
          Tamil Voice Prompt
        </span>
        <StateLabel kind={live ? "live" : "replay"} surface="paper" />
      </div>

      <p lang="ta" className="font-tamil-prompt text-[var(--text-1)]">
        {promptTextTa}
      </p>

      <p className="text-[14px] leading-[18px] text-[var(--text-2)]">
        {promptEn}
      </p>

      {audioUrl ? (
        <div className="flex items-center justify-between gap-2 pt-0.5">
          <button
            type="button"
            onClick={handleTogglePlay}
            className="inline-flex items-center gap-1.5 rounded-[4px] border border-[var(--line)] bg-[var(--paper)] px-2.5 py-1 text-[14px] leading-[20px] font-medium text-[var(--text-1)] hover:border-[var(--rust)] cursor-pointer"
          >
            {playing ? (
              <PauseGlyph className="h-3.5 w-3.5 text-[var(--rust)]" />
            ) : (
              <PlayGlyph className="h-3.5 w-3.5 text-[var(--rust)]" />
            )}
            <span>{playing ? "Pause audio" : "Play Tamil audio"}</span>
          </button>

          <div className="flex items-center gap-2">
            <svg
              width={64}
              height={18}
              viewBox="0 0 64 18"
              aria-hidden="true"
              className={cn(
                "shrink-0",
                playing ? "text-[var(--rust)]" : "text-[var(--text-3)]"
              )}
            >
              {WAVEFORM_PEAKS.map((h, idx) => (
                <rect
                  key={idx}
                  x={idx * 4}
                  y={Math.round((18 - h) / 2)}
                  width={2}
                  height={h}
                  fill="currentColor"
                />
              ))}
            </svg>
            <span className="font-figures text-[14px] leading-[20px] text-[var(--text-2)]">
              {formattedDuration}
            </span>
          </div>

          <audio
            ref={audioRef}
            src={audioUrl}
            onLoadedMetadata={(evt) => {
              const dur = evt.currentTarget.duration;
              if (Number.isFinite(dur) && dur > 0) {
                setDurationSec(dur);
              }
            }}
            onEnded={() => setPlaying(false)}
            onPause={() => setPlaying(false)}
            preload="metadata"
          />
        </div>
      ) : null}
    </div>
  );
}
