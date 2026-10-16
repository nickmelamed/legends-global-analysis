import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";

export type Preset = "last_week" | "month_to_date" | "year_to_date" | "custom";
export type CompareMode = "prior_period" | "last_year";

export interface FilterState {
  venues: string[];
  preset: Preset;
  start: string;
  end: string;
  packageClasses: string[];
  salesChannels: string[];
  compare: boolean;
  compareMode: CompareMode;
}

export const DEFAULTS: FilterState = {
  venues: ["SSD"],
  preset: "last_week",
  start: "",
  end: "",
  packageClasses: [],
  salesChannels: [],
  compare: true,
  compareMode: "prior_period",
};

const PRESETS: Preset[] = ["last_week", "month_to_date", "year_to_date", "custom"];

// An absent param means the default, so a bare URL shows the default view and
// Reset only has to clear the query string.
export function parse(params: URLSearchParams): FilterState {
  const preset = params.get("preset") as Preset | null;
  const venues = params.getAll("venue");
  return {
    venues: venues.length ? venues : DEFAULTS.venues,
    preset: preset && PRESETS.includes(preset) ? preset : DEFAULTS.preset,
    start: params.get("start") ?? "",
    end: params.get("end") ?? "",
    packageClasses: params.getAll("package_class"),
    salesChannels: params.getAll("sales_channel"),
    compare: params.get("compare") !== "false",
    compareMode: params.get("compare_mode") === "last_year" ? "last_year" : "prior_period",
  };
}

export function toParams(f: FilterState): URLSearchParams {
  const p = new URLSearchParams();
  f.venues.forEach((v) => p.append("venue", v));
  p.set("preset", f.preset);
  if (f.preset === "custom") {
    if (f.start) p.set("start", f.start);
    if (f.end) p.set("end", f.end);
  }
  f.packageClasses.forEach((v) => p.append("package_class", v));
  f.salesChannels.forEach((v) => p.append("sales_channel", v));
  p.set("compare", String(f.compare));
  if (f.compare) p.set("compare_mode", f.compareMode);
  return p;
}

export function useFilters() {
  const [params, setParams] = useSearchParams();
  const filters = parse(params);
  const update = useCallback(
    (patch: Partial<FilterState>) => setParams(toParams({ ...parse(params), ...patch })),
    [params, setParams],
  );
  const reset = useCallback(() => setParams(new URLSearchParams()), [setParams]);
  const needsDates = filters.preset === "custom" && (!filters.start || !filters.end);
  return { filters, update, reset, needsDates, query: toParams(filters).toString() };
}
