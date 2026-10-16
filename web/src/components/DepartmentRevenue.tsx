import type { Metric, WindowInfo } from "../api";
import { formatPct, formatRange, formatValue } from "../format";

export function DepartmentRevenue({ rows, window }: { rows: Metric[]; window: WindowInfo }) {
  // Bars scale to the largest value shown.
  const max = Math.max(1, ...rows.flatMap((r) => [r.current ?? 0, r.comparison ?? 0]));
  const comparing = window.compare_mode !== null;
  return (
    <section className="panel" aria-label="Revenue by department">
      <div className="panel-head">
        <h2>Revenue by department</h2>
        {comparing && (
          <div className="legend">
            <span>
              <span className="swatch bar" />
              {formatRange(window.start, window.elapsed_end)}
            </span>
            <span>
              <span className="swatch" style={{ background: "var(--chart-cmp)", height: 4 }} />
              {formatRange(window.comparison_start, window.comparison_elapsed_end)}
            </span>
          </div>
        )}
      </div>
      {rows.map((r) => (
        <div className="dept" key={r.key} data-testid={`dept-${r.label}`}>
          <div>
            {r.label}
            {r.ticket_filtered && <div className="muted">Ticket filters applied</div>}
            {r.data_gap && <div className="warn">! Missing days</div>}
          </div>
          <div className="bars">
            {r.current === null ? (
              <span className="muted">No data</span>
            ) : (
              <div className="bar cur" style={{ width: `${(r.current / max) * 100}%` }} />
            )}
            {comparing && r.comparison !== null && (
              <div className="bar cmp" style={{ width: `${(r.comparison / max) * 100}%` }} />
            )}
          </div>
          <div className="num">
            {formatValue(r.current, r.unit)}
            {comparing && (
              <small>
                {r.delta_pct === null
                  ? `vs ${formatValue(r.comparison, r.unit)}`
                  : `${r.delta_pct > 0 ? "▲" : r.delta_pct < 0 ? "▼" : "▶"} ${formatPct(Math.abs(r.delta_pct))}`}
              </small>
            )}
          </div>
        </div>
      ))}
    </section>
  );
}
