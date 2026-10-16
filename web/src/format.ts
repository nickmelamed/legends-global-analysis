import type { Metric } from "./api";

const NO_DATA = "No data";

function short(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (abs >= 1e4) return `${(n / 1e3).toFixed(1)}K`;
  if (abs >= 1e3) return `${(n / 1e3).toFixed(2)}K`;
  return n.toFixed(abs < 100 && !Number.isInteger(n) ? 2 : 0);
}

export function formatValue(value: number | null, unit: Metric["unit"]): string {
  if (value === null) return NO_DATA;
  switch (unit) {
    case "usd":
      return Math.abs(value) < 1000 ? `$${value.toFixed(2)}` : `$${short(value)}`;
    case "count":
      return short(value);
    case "hours":
      return `${short(value)} h`;
    case "ratio":
      return value.toFixed(2);
    case "pct":
      return `${value.toFixed(1)}%`;
  }
}

export function formatPct(value: number | null): string {
  return value === null ? NO_DATA : `${value.toFixed(1)}%`;
}

export function formatDate(iso: string | null): string {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function formatRange(start: string | null, end: string | null): string {
  if (!start || !end) return "";
  return start === end ? formatDate(start) : `${formatDate(start)} – ${formatDate(end)}`;
}
