import type { Metric, PaceStatus } from "../api";
import { formatPct, formatValue } from "../format";

const STATUS: Record<PaceStatus, { cls: string; glyph: string; label: string }> = {
  green: { cls: "good", glyph: "✓", label: "On plan" },
  amber: { cls: "warn", glyph: "!", label: "Near plan" },
  red: { cls: "bad", glyph: "✕", label: "Behind plan" },
};

export function PaceBar({ metric }: { metric: Metric }) {
  const pace = metric.pace;
  if (!pace) {
    return (
      <div className="pace note muted">
        {metric.ticket_filtered ? "No plan for a filtered view" : "No plan"}
      </div>
    );
  }
  const status = pace.status ? STATUS[pace.status] : null;
  const width = pace.pct === null ? 0 : Math.min(pace.pct, 100);
  return (
    <div className="pace" data-testid={`pace-${metric.key}`}>
      <div
        className="track"
        role="meter"
        aria-label={`${metric.label} pace to plan`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pace.pct ?? undefined}
      >
        <div className={`fill ${status?.cls ?? "muted"}`} style={{ width: `${width}%` }} />
      </div>
      <div className="text">
        <span className={status?.cls ?? "muted"}>
          {status
            ? `${status.glyph} ${formatPct(pace.pct)} ${status.label}`
            : pace.data_gap
              ? `${formatPct(pace.pct)} · data gap, no status`
              : "No data"}
        </span>
        <span className="muted">plan {formatValue(pace.budget, metric.unit)}</span>
      </div>
    </div>
  );
}
