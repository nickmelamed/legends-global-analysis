import { useState } from "react";
import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Trend, TrendPoint } from "../api";
import { formatDate, formatRange, formatValue } from "../format";
import type { Theme } from "../theme";
import type { Loaded } from "../useApi";

type Grain = Trend["grain"];

// SVG attributes do not take CSS variables, so the chart colours sit here per theme.
const COLORS: Record<Theme, { gold: string; ink: string; cmp: string; grid: string; text: string }> = {
  light: { gold: "#FFC000", ink: "#1a1a1a", cmp: "#8a8a8a", grid: "#ececec", text: "#555555" },
  dark: { gold: "#FFC000", ink: "#e6e6e6", cmp: "#8f8f8f", grid: "#262626", text: "#b0b0b0" },
};

interface Row {
  key: string;
  label: string;
  cur: TrendPoint | null;
  cmp: TrendPoint | null;
  revenue: number | null;
  perCap: number | null;
  cmpRevenue: number | null;
}

function bucketLabel(iso: string, grain: Grain): string {
  const d = formatDate(iso);
  if (grain === "month") return d.replace(/ \d+,/, "");
  return d.replace(/, \d{4}$/, "");
}

// The API shifts comparison buckets onto the current dates, so the two pair up
// by bucket_start.
function merge(trend: Trend): Row[] {
  const rows = new Map<string, Row>();
  const row = (p: TrendPoint): Row => {
    let r = rows.get(p.bucket_start);
    if (!r) {
      r = {
        key: p.bucket_start,
        label: bucketLabel(p.bucket_start, trend.grain),
        cur: null,
        cmp: null,
        revenue: null,
        perCap: null,
        cmpRevenue: null,
      };
      rows.set(p.bucket_start, r);
    }
    return r;
  };
  for (const p of trend.current) Object.assign(row(p), { cur: p, revenue: p.revenue, perCap: p.per_cap });
  for (const p of trend.comparison ?? []) Object.assign(row(p), { cmp: p, cmpRevenue: p.revenue });
  return [...rows.values()].sort((a, b) => a.key.localeCompare(b.key));
}

function pointNote(p: TrendPoint | null): string {
  if (!p) return "";
  const notes = [];
  if (p.data_gap) notes.push(`${p.no_data_days} day(s) no data`);
  if (p.partial) notes.push(`partial, ${p.days} days`);
  return notes.length ? ` (${notes.join(", ")})` : "";
}

function Tip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="chart-tip">
      <div>
        <strong>{r.cur ? formatRange(r.cur.first_day, r.cur.last_day) : r.label}</strong>
      </div>
      <div>
        Revenue {formatValue(r.revenue, "usd")}
        {pointNote(r.cur)}
      </div>
      <div>Per cap {formatValue(r.perCap, "usd")}</div>
      {r.cmp && (
        <div>
          Comparison {formatValue(r.cmpRevenue, "usd")} ({formatRange(r.cmp.first_day, r.cmp.last_day)})
          {pointNote(r.cmp)}
        </div>
      )}
    </div>
  );
}

interface Props {
  trend: Loaded<Trend>;
  grain: Grain;
  onGrain: (g: Grain) => void;
  theme: Theme;
}

export function RevenueTrend({ trend, grain, onGrain, theme }: Props) {
  const [table, setTable] = useState(false);
  const c = COLORS[theme];
  const rows = trend.state === "ok" ? merge(trend.data) : [];
  const comparing = trend.state === "ok" && trend.data.comparison !== null;
  const money = (v: number) => formatValue(v, "usd");
  return (
    <section className="panel" aria-label="Revenue trend">
      <div className="panel-head">
        <h2>Revenue trend</h2>
        <div className="row" style={{ display: "flex", gap: 4 }}>
          {(["day", "week", "month"] as Grain[]).map((g) => (
            <button key={g} aria-pressed={grain === g} onClick={() => onGrain(g)}>
              {g[0].toUpperCase() + g.slice(1)}
            </button>
          ))}
          <button aria-pressed={table} onClick={() => setTable(!table)}>
            Table
          </button>
        </div>
      </div>
      <div className="legend" style={{ marginBottom: 6 }}>
        <span>
          <span className="swatch bar" />
          Revenue (left axis)
        </span>
        {comparing && (
          <span>
            <span className="swatch dash" />
            Comparison revenue (left axis)
          </span>
        )}
        <span>
          <span className="swatch line" />
          Per cap (right axis)
        </span>
      </div>
      {trend.state === "loading" && <div className="muted">Loading…</div>}
      {trend.state === "ok" && rows.length === 0 && <div className="muted">No data in this window yet.</div>}
      {trend.state === "ok" && rows.length > 0 && !table && (
        <div style={{ height: 260 }} data-testid="trend-chart">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rows} margin={{ top: 8, right: 4, bottom: 0, left: 4 }}>
              <CartesianGrid stroke={c.grid} vertical={false} />
              <XAxis dataKey="label" tick={{ fill: c.text, fontSize: 11 }} stroke={c.grid} minTickGap={8} />
              <YAxis
                yAxisId="rev"
                tickFormatter={money}
                tick={{ fill: c.text, fontSize: 11 }}
                stroke={c.grid}
                width={56}
              />
              <YAxis
                yAxisId="cap"
                orientation="right"
                tickFormatter={money}
                tick={{ fill: c.text, fontSize: 11 }}
                stroke={c.grid}
                width={52}
              />
              <Tooltip content={<Tip />} cursor={{ fill: c.grid }} />
              <Bar yAxisId="rev" dataKey="revenue" fill={c.gold} stroke={c.ink} strokeWidth={1} radius={[4, 4, 0, 0]} isAnimationActive={false}>
                {rows.map((r) => (
                  <Cell key={r.key} fillOpacity={r.cur?.data_gap ? 0.35 : 1} strokeDasharray={r.cur?.data_gap ? "3 2" : undefined} />
                ))}
              </Bar>
              {rows
                .filter((r) => r.cur?.data_gap && r.revenue === null)
                .map((r) => (
                  <ReferenceArea
                    key={`gap-${r.key}`}
                    yAxisId="rev"
                    x1={r.label}
                    x2={r.label}
                    fill={c.grid}
                    fillOpacity={0.6}
                    stroke={c.cmp}
                    strokeDasharray="3 3"
                    label={{ value: "No data", angle: -90, fill: c.text, fontSize: 11 }}
                  />
                ))}
              {comparing && (
                <Line
                  yAxisId="rev"
                  dataKey="cmpRevenue"
                  stroke={c.cmp}
                  strokeWidth={2}
                  strokeDasharray="5 4"
                  dot={false}
                  connectNulls={false}
                  isAnimationActive={false}
                />
              )}
              <Line
                yAxisId="cap"
                dataKey="perCap"
                stroke={c.ink}
                strokeWidth={2}
                dot={{ r: 3, fill: c.ink }}
                connectNulls={false}
                isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
      {trend.state === "ok" && rows.length > 0 && table && (
        <table className="data">
          <thead>
            <tr>
              <th>Period</th>
              <th>Revenue</th>
              <th>Per cap</th>
              {comparing && <th>Comparison</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key}>
                <td>
                  {r.label}
                  {pointNote(r.cur)}
                </td>
                <td>{formatValue(r.revenue, "usd")}</td>
                <td>{formatValue(r.perCap, "usd")}</td>
                {comparing && <td>{formatValue(r.cmpRevenue, "usd")}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="muted" style={{ marginTop: 6, fontSize: 12 }}>
        Shaded columns are days with no data. Faded, dashed bars include some no-data days. Total revenue. Ticket filters do not apply.
      </div>
    </section>
  );
}
