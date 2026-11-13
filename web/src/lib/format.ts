import type { ShopView } from "./api";

export type ShopStatusText =
  | "Trading"
  | "Shutter down"
  | "Asked"
  | "Filed"
  | "Closed: on leave"
  | "Closed: declined";

export function resolveShopStatusText(shop: ShopView): ShopStatusText {
  if (shop.claim) {
    return "Filed";
  }
  if (shop.ask) {
    if (
      shop.ask.status === "declined" ||
      shop.ask.cause_label === "consent_declined"
    ) {
      return "Closed: declined";
    }
    if (
      shop.ask.cause_label === "leave" ||
      shop.ask.status === "closed"
    ) {
      return "Closed: on leave";
    }
    return "Asked";
  }
  if (shop.status === "dropped" || shop.status === "quiet") {
    return "Shutter down";
  }
  return "Trading";
}

const inrNumberFormatter = new Intl.NumberFormat("en-IN", {
  maximumFractionDigits: 0,
});

const inrPaiseFormatter = new Intl.NumberFormat("en-IN", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

export function formatNumberIN(value: number): string {
  return inrNumberFormatter.format(Math.round(value));
}

export function formatRupeesFromPaise(paise: number): string {
  const rupees = paise / 100;
  if (paise % 100 === 0) {
    return `\u20B9${inrNumberFormatter.format(rupees)}`;
  }
  return `\u20B9${inrPaiseFormatter.format(rupees)}`;
}

export function formatClockTimeIST(isoTimestamp: string | null): string {
  if (!isoTimestamp) {
    return "07:00 IST";
  }
  const date = new Date(isoTimestamp);
  if (Number.isNaN(date.getTime())) {
    return isoTimestamp;
  }
  const formatter = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return `${formatter.format(date)} IST`;
}

export function formatDayHuman(isoDay: string | null): string {
  if (!isoDay) {
    return "21 Oct 2026";
  }
  const parts = isoDay.split("-").map(Number);
  if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) {
    return isoDay;
  }
  const [year, month, day] = parts;
  const utcDate = new Date(Date.UTC(year, month - 1, day));
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(utcDate);
}

export function formatDurationMmSs(seconds: number): string {
  const clamped = Math.max(0, Math.round(seconds));
  const mins = Math.floor(clamped / 60);
  const secs = clamped % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

