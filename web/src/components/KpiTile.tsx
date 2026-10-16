import type { Metric, WindowInfo } from "../api";
import { formatPct, formatRange, formatValue } from "../format";
import { PaceBar } from "./PaceBar";

function Delta({ metric }: { metric: Metric }) {
  if (metric.delta_pct === null) {
    if (!metric.data_gap && !metric.comparison_data_gap) return null;
    return <span className="delta muted">No change shown (data gap)</span>;
  }
  const up = metric.delta_pct > 0;
  const flat = metric.delta_pct === 0;
  // A rise in a cost is bad news, so cost metrics swap the colours.
  const good = flat ? null : up !== metric.cost;
  const cls = good === null ? "muted" : good ? "good" : "bad";
  const arrow = flat ? "▶" : up ? "▲" : "▼";
  return (
    <span className={`delta ${cls}`}>
      {arrow} {formatPct(Math.abs(metric.delta_pct))}
    </span>
  );
}

interface Props {
  metric: Metric;
  window: WindowInfo;
  showPace?: boolean;
}

export function KpiTile({ metric, window, showPace = false }: Props) {
  const value = formatValue(metric.current, metric.unit);
  const compareRange = formatRange(window.comparison_start, window.comparison_elapsed_end);
  return (
    <div className="tile" data-testid={`tile-${metric.key}`}>
      <div className="label">
        {metric.label}
        {metric.ticket_filtered && <span className="tag">Ticket filters applied</span>}
      </div>
      <div className={`value${metric.current === null ? " none" : ""}`} data-testid="value">
        {value}
      </div>
      {window.compare_mode && (
        <div className="cmp">
          <Delta metric={metric} />{" "}
          {metric.comparison !== null
            ? `vs ${formatValue(metric.comparison, metric.unit)} (${compareRange})`
            : compareRange
              ? `vs No data (${compareRange})`
              : "Nothing to compare yet"}
        </div>
      )}
      {metric.data_gap && <div className="note warn">! Missing feed days in this window</div>}
      {metric.incomplete && (
        <div className="note warn">
          ! Incomplete: {metric.incomplete.missing_rate_shifts} shifts (
          {metric.incomplete.missing_rate_hours} h) have no pay rate
        </div>
      )}
      {showPace && <PaceBar metric={metric} />}
    </div>
  );
}
