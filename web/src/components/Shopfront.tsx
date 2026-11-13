import type { ShopView } from "@/lib/api";
import { formatRupeesFromPaise, resolveShopStatusText } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Shutter } from "./Shutter";
import { Sparkline } from "./Sparkline";
import { StateLabel } from "./StateLabel";

export interface ShopfrontProps {
  shop: ShopView;
  className?: string;
}

export function Shopfront({ shop, className }: ShopfrontProps) {
  const statusText = resolveShopStatusText(shop);
  const isShutterDown = statusText !== "Trading";
  const hourlyAmounts =
    shop.hourly.length > 0
      ? shop.hourly.map((pt) => pt.amount_paise)
      : [0];
  const maxRef = Math.max(Math.round(shop.baseline_paise / 8), 5000);

  const eventSimulatedLabel =
    shop.ask?.simulated_label === "Simulated consent" ||
    shop.ask?.simulated_label === "Simulated reply"
      ? shop.ask.simulated_label
      : null;

  const statusTone =
    statusText === "Filed"
      ? "text-[var(--ok)]"
      : statusText === "Asked"
        ? "text-[var(--marigold)]"
        : statusText === "Trading"
          ? "text-[var(--live)]"
          : "text-[var(--text-dark-2)]";

  const takingsLabel = isShutterDown
    ? `${formatRupeesFromPaise(shop.today_income_paise)} today`
    : formatRupeesFromPaise(shop.today_income_paise);

  return (
    <article
      aria-label={`${shop.name}, ${shop.owner}, ${statusText}`}
      className={cn(
        "relative flex h-[126px] w-full flex-col justify-between overflow-hidden rounded-[6px] border border-[var(--line-dark)] bg-[var(--ink-2)] p-2",
        statusText === "Filed" && "border-[var(--ok)]/50",
        statusText === "Asked" && "border-[var(--marigold)]/60",
        className
      )}
    >
      {/* Top category & takings line (always visible above shutter; long categories wrap) */}
      <div className="relative z-20 flex min-h-[22px] shrink-0 items-start justify-between gap-1">
        <span className="text-[12px] leading-[13px] font-medium uppercase tracking-[0.3px] text-[var(--text-dark-2)]">
          {shop.category.replace(/_/g, " ")}
        </span>
        <span className="shrink-0 font-figures text-[14px] leading-[16px] text-[var(--text-dark-1)]">
          {takingsLabel}
        </span>
      </div>

      {/* Shutter covering the 60% middle storefront window when down */}
      <Shutter isDown={isShutterDown} />

      {eventSimulatedLabel ? (
        <div className="pointer-events-none absolute right-1.5 top-[44px] z-20">
          <StateLabel
            kind="simulated"
            text={eventSimulatedLabel}
            className="bg-[var(--ink)] px-1.5 py-0.5"
          />
        </div>
      ) : null}

      {/* Middle window: 24h sparkline (visible when shutter is open) */}
      <div
        className={cn(
          "relative z-0 flex flex-1 items-center py-1",
          isShutterDown ? "text-[var(--text-dark-3)] opacity-25" : "text-[var(--live)]"
        )}
      >
        <Sparkline values={hourlyAmounts} maxReference={maxRef} width={136} height={24} />
      </div>

      {/* Bottom fascia: Shop name, owner, and polite live status */}
      <div className="relative z-20 flex shrink-0 flex-col gap-0.5 bg-[var(--ink-2)] pt-1">
        <div className="flex items-baseline justify-between gap-1">
          <h3 className="truncate text-[14px] leading-[18px] font-semibold text-[var(--text-dark-1)]">
            {shop.name}
          </h3>
          <span className="shrink-0 text-[14px] leading-[18px] text-[var(--text-dark-2)]">
            {shop.owner}
          </span>
        </div>

        <div className="flex items-center justify-between gap-1">
          <span
            aria-live="polite"
            className={cn(
              "truncate text-[12px] leading-[16px] font-medium",
              statusTone
            )}
          >
            {statusText}
          </span>
        </div>
      </div>
    </article>
  );
}
