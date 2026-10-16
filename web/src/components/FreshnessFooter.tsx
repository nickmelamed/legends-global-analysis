import { errorMessage, type Freshness } from "../api";
import { formatDate } from "../format";
import type { Loaded } from "../useApi";

export function FreshnessFooter({ fresh }: { fresh: Loaded<Freshness> }) {
  if (fresh.state === "error") {
    return (
      <footer className="fresh" data-testid="freshness">
        Data freshness unavailable. {errorMessage(fresh.error)}
      </footer>
    );
  }
  if (fresh.state !== "ok") return <footer className="fresh">Data freshness: checking…</footer>;
  const f = fresh.data;
  const loaded = f.last_load_finished_at
    ? new Date(f.last_load_finished_at).toLocaleString("en-US", {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : "never";
  return (
    <footer className="fresh" data-testid="freshness">
      Data last refreshed {loaded}. Expected through {formatDate(f.expected_latest_day)}.{" "}
      {f.stale ? (
        <span className="warn">
          ! Stale:{" "}
          {f.stale_feeds.length
            ? f.stale_feeds.map((s) => `${s.venue} ${s.feed}`).join(", ")
            : "no load has run"}
        </span>
      ) : (
        <span className="good">✓ Current</span>
      )}
    </footer>
  );
}
