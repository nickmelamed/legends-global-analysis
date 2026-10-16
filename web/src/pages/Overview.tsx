import { useState } from "react";
import { errorMessage, type Overview as OverviewData, type Trend } from "../api";
import { DepartmentRevenue } from "../components/DepartmentRevenue";
import { KpiTile } from "../components/KpiTile";
import { RevenueTrend } from "../components/RevenueTrend";
import { useFilters } from "../filters";
import { formatDate, formatRange } from "../format";
import type { Theme } from "../theme";
import { useApi } from "../useApi";

export function Overview({ theme }: { theme: Theme }) {
  const { query, needsDates } = useFilters();
  const [grain, setGrain] = useState<Trend["grain"]>("day");
  const overview = useApi<OverviewData>(needsDates ? null : `/api/overview?${query}`);
  const trend = useApi<Trend>(needsDates ? null : `/api/trend?${query}&grain=${grain}`);

  if (needsDates) {
    return (
      <div className="notice" data-testid="pick-dates">
        Pick a start and end date in the filters to see a custom range.
      </div>
    );
  }
  if (overview.state === "loading") return <div className="muted">Loading…</div>;
  if (overview.state === "error") {
    return (
      <div className="notice error" role="alert" data-testid="error">
        ✕ {errorMessage(overview.error)}
      </div>
    );
  }
  const o = overview.data;
  const w = o.window;
  return (
    <>
      <div className="page-head">
        <h1>Overview</h1>
        <span className="meta" data-testid="window">
          {o.venues.join(", ")} · {formatRange(w.start, w.end)}
          {w.days_elapsed < w.days_total &&
            ` · ${w.days_elapsed} of ${w.days_total} days elapsed${w.elapsed_end ? `, through ${formatDate(w.elapsed_end)}` : ""}`}
        </span>
        {w.compare_mode && (
          <span className="meta">
            vs {w.compare_mode === "last_year" ? "last year" : "prior period"}{" "}
            {formatRange(w.comparison_start, w.comparison_elapsed_end)}
          </span>
        )}
      </div>
      {w.crosses_cutover && (
        <div className="notice" data-testid="cutover">
          ! The comparison crosses the {formatDate(w.cutover_date)} ticketing system cutover, so
          ticket figures on each side come from different systems.
        </div>
      )}
      {o.data_gaps.length > 0 && (
        <div className="notice" data-testid="data-gaps">
          ! No data for{" "}
          {o.data_gaps.map((g) => `${g.venue} ${g.feed} on ${formatDate(g.date)}`).join("; ")}.
          Affected figures leave those days out and show no delta.
        </div>
      )}
      <h2 className="section-title">Business</h2>
      <div className="tiles">
        {o.kpis.map((m) => (
          <KpiTile key={m.key} metric={m} window={w} showPace />
        ))}
      </div>
      <h2 className="section-title">Labor</h2>
      <div className="tiles">
        {o.labor.map((m) => (
          <KpiTile key={m.key} metric={m} window={w} />
        ))}
      </div>
      <h2 className="section-title">Revenue</h2>
      <div className="grid-2">
        <DepartmentRevenue rows={o.departments} window={w} />
        <RevenueTrend trend={trend} grain={grain} onGrain={setGrain} theme={theme} />
      </div>
    </>
  );
}
