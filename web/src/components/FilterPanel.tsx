import type { Filters } from "../api";
import { type CompareMode, type Preset, useFilters } from "../filters";

const PRESET_LABELS: Record<Preset, string> = {
  last_week: "Last Week",
  month_to_date: "Month to Date",
  year_to_date: "Year to Date",
  custom: "Custom",
};

function toggle(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

export function FilterPanel({ options }: { options: Filters | null }) {
  const { filters, update, reset, query } = useFilters();
  return (
    <section className="filters" aria-label="Filters">
      <h2>Filters</h2>
      <fieldset>
        <legend>Venue</legend>
        {(options?.venues ?? []).map((v) => (
          <label key={v.code}>
            <input
              type="checkbox"
              checked={filters.venues.includes(v.code)}
              disabled={filters.venues.length === 1 && filters.venues.includes(v.code)}
              onChange={() => update({ venues: toggle(filters.venues, v.code) })}
            />
            {v.name}
          </label>
        ))}
      </fieldset>
      <fieldset>
        <legend>Dates</legend>
        <select
          aria-label="Date range"
          value={filters.preset}
          onChange={(e) => update({ preset: e.target.value as Preset })}
        >
          {(Object.keys(PRESET_LABELS) as Preset[]).map((p) => (
            <option key={p} value={p}>
              {PRESET_LABELS[p]}
            </option>
          ))}
        </select>
        {filters.preset === "custom" && (
          <div className="row" style={{ marginTop: 6 }}>
            <input
              type="date"
              aria-label="Start date"
              value={filters.start}
              onChange={(e) => update({ start: e.target.value })}
            />
            <input
              type="date"
              aria-label="End date"
              value={filters.end}
              onChange={(e) => update({ end: e.target.value })}
            />
          </div>
        )}
      </fieldset>
      <fieldset>
        <legend>Package class</legend>
        {(options?.package_classes ?? []).map((v) => (
          <label key={v}>
            <input
              type="checkbox"
              checked={filters.packageClasses.includes(v)}
              onChange={() => update({ packageClasses: toggle(filters.packageClasses, v) })}
            />
            {v}
          </label>
        ))}
        <div className="hint">None checked means all. Applies to ticket metrics only.</div>
      </fieldset>
      <fieldset>
        <legend>Sales channel</legend>
        {(options?.sales_channels ?? []).map((v) => (
          <label key={v}>
            <input
              type="checkbox"
              checked={filters.salesChannels.includes(v)}
              onChange={() => update({ salesChannels: toggle(filters.salesChannels, v) })}
            />
            {v}
          </label>
        ))}
      </fieldset>
      <fieldset>
        <legend>Compare</legend>
        <label>
          <input
            type="checkbox"
            checked={filters.compare}
            onChange={(e) => update({ compare: e.target.checked })}
          />
          Compare on
        </label>
        <select
          aria-label="Compare to"
          value={filters.compareMode}
          disabled={!filters.compare}
          onChange={(e) => update({ compareMode: e.target.value as CompareMode })}
        >
          <option value="prior_period">Prior period</option>
          <option value="last_year">Last year</option>
        </select>
      </fieldset>
      <div className="row">
        <button onClick={reset}>Reset</button>
        <a className="btn" href={`/api/export.csv?${query}`} download>
          Export CSV
        </a>
      </div>
    </section>
  );
}
