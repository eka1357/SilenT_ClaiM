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
          : "text-[var(--text-dark-3)]";

  return (
    <article
      aria-label={`${shop.name}, ${shop.owner}, ${statusText}`}
      className={cn(
        "relative flex h-[120px] w-full flex-col justify-between overflow-hidden rounded-[6px] border border-[var(--line-dark)] bg-[var(--ink-2)] p-2.5",
        statusText === "Filed" && "border-[var(--ok)]/50",
        statusText === "Asked" && "border-[var(--marigold)]/60",
        className
      )}
    >
      <Shutter isDown={isShutterDown} />

      {eventSimulatedLabel ? (
        <div className="pointer-events-none absolute right-2 top-[42px] z-20">
          <StateLabel
            kind="simulated"
            text={eventSimulatedLabel}
            className="gap-1 bg-[var(--ink)] px-1.5 py-0.5 text-[9.5px] leading-[12px]"
          />
        </div>
      ) : null}

      {/* Top 56%: Shop window with category, today's payments, and 24h sparkline */}
      <div className="relative z-0 flex flex-col gap-1">
        <div className="flex items-center justify-between gap-1 text-[11px] leading-[14px] text-[var(--text-dark-3)]">
          <span className="truncate uppercase tracking-[0.4px]">{shop.category}</span>
          <span className="font-figures-sm text-[var(--text-dark-2)]">
            {formatRupeesFromPaise(shop.today_income_paise)}
          </span>
        </div>
        <div
          className={cn(
            "pt-0.5",
            isShutterDown ? "text-[var(--text-dark-3)]" : "text-[var(--live)]"
          )}
        >
          <Sparkline values={hourlyAmounts} maxReference={maxRef} width={136} height={24} />
        </div>
      </div>

      {/* Bottom 44%: Fascia with shop name, owner, polite live status, and event-only simulated label */}
      <div className="relative z-20 flex flex-col gap-0.5 pt-1">
        <div className="flex items-baseline justify-between gap-1">
          <h3 className="truncate text-[13px] leading-[16px] font-semibold text-[var(--text-dark-1)]">
            {shop.name}
          </h3>
          <span className="shrink-0 text-[11px] leading-[14px] text-[var(--text-dark-2)]">
            {shop.owner}
          </span>
        </div>

        <div className="flex items-center justify-between gap-1">
          <span
            aria-live="polite"
            className={cn(
              "truncate text-[11px] leading-[14px] font-medium",
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

