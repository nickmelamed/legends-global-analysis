// Types mirror the JSON from api/main.py, api/overview.py and api/trend.py.
// The UI renders these values as they come. It never derives a window,
// a delta or a pace status itself.

export type PaceStatus = "green" | "amber" | "red";

export interface Pace {
  actual: number | null;
  budget: number;
  pct: number | null;
  status: PaceStatus | null;
  data_gap: boolean;
}

export interface Metric {
  key: string;
  label: string;
  unit: "usd" | "count" | "hours" | "ratio" | "pct";
  current: number | null;
  comparison: number | null;
  delta_pct: number | null;
  cost: boolean;
  ticket_filtered: boolean;
  data_gap: boolean;
  comparison_data_gap: boolean;
  pace: Pace | null;
  incomplete?: { missing_rate_shifts: number; missing_rate_hours: number } | null;
}

export interface WindowInfo {
  start: string;
  end: string;
  days_total: number;
  days_elapsed: number;
  elapsed_end: string | null;
  compare_mode: "prior_period" | "last_year" | null;
  comparison_start: string | null;
  comparison_end: string | null;
  comparison_elapsed_end: string | null;
  crosses_cutover: boolean;
  cutover_date: string;
}

export interface Overview {
  venues: string[];
  window: WindowInfo;
  filters: { package_class: string[]; sales_channel: string[]; ticket_filter_applies_to: string[] };
  kpis: Metric[];
  labor: Metric[];
  departments: Metric[];
  revenue_lines: Metric[];
  data_gaps: { venue: string; date: string; feed: string }[];
}

export interface TrendPoint {
  bucket_start: string;
  first_day: string;
  last_day: string;
  days: number;
  partial: boolean;
  revenue: number | null;
  attendance: number | null;
  per_cap: number | null;
  data_gap: boolean;
  no_data_days: number;
}

export interface Trend {
  window: WindowInfo;
  grain: "day" | "week" | "month";
  current: TrendPoint[];
  comparison: TrendPoint[] | null;
}

export interface Filters {
  user: { email: string; display_name: string; role: string };
  venues: { code: string; name: string }[];
  selected_venues: string[];
  package_classes: string[];
  sales_channels: string[];
  app_today: string;
}

export interface Freshness {
  app_today: string;
  last_load_run: string | null;
  last_load_finished_at: string | null;
  expected_latest_day: string;
  stale: boolean;
  stale_feeds: { venue: string; feed: string }[];
}

export interface AskRow {
  metric: string;
  unit: Metric["unit"];
  start: string;
  end: string | null;
  compared: boolean;
  comparison_start: string | null;
  comparison_end: string | null;
  current: number | null;
  comparison: number | null;
  percent_change: number | null;
  no_data: boolean;
}

export interface AskReply {
  venues: string[];
  answer: string | null;
  grounded: boolean;
  fallback: string | null;
  ungrounded: string[];
  tool_calls: { name: string; args: Record<string, unknown> }[];
  table: AskRow[];
  model: string;
  model_called: boolean;
  usage: { input_tokens: number; output_tokens: number };
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path, { signal });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body: unknown = await res.json();
      if (body && typeof body === "object" && "detail" in body) detail = String(body.detail);
    } catch {
      // A non-JSON error body keeps the status text.
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 403) return "You do not have access to this venue.";
    if (err.status === 401) return "You are not signed in.";
    return `The API returned ${err.status}: ${err.message}`;
  }
  return "The API could not be reached.";
}
