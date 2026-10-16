import { type FormEvent, useState } from "react";
import { ApiError, type AskReply, errorMessage } from "../api";
import { useFilters } from "../filters";
import { formatExact, formatRange } from "../format";

export function Ask() {
  const { filters } = useFilters();
  const [question, setQuestion] = useState("");
  const [reply, setReply] = useState<AskReply | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    setBusy(true);
    setError(null);
    setReply(null);
    const params = new URLSearchParams(filters.venues.map((v) => ["venue", v]));
    try {
      const res = await fetch(`/api/ask?${params}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      if (!res.ok) throw new ApiError(res.status, res.statusText);
      setReply((await res.json()) as AskReply);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>Ask the data</h1>
        <span className="meta">{filters.venues.join(", ")}</span>
      </div>
      <form className="ask-form" onSubmit={submit}>
        <label htmlFor="question">Question</label>
        <input
          id="question"
          value={question}
          maxLength={500}
          placeholder="How did last week compare to last year?"
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button type="submit" disabled={busy}>
          {busy ? "Asking…" : "Ask"}
        </button>
      </form>
      <p className="muted">
        Every figure in an answer is checked against the data before it is shown. If a check
        fails, you see the numbers only. The venue filter applies here. The question sets the
        dates, so the date and ticket filters do not.
      </p>
      {error && <p className="error">{error}</p>}
      {reply && (
        <section className="panel" data-testid="ask-reply">
          {reply.answer ? (
            <>
              <p data-testid="answer">{reply.answer}</p>
              <p className="muted" data-testid="check">
                Checked against the data
              </p>
            </>
          ) : (
            <p data-testid="check">{reply.notice}</p>
          )}
          {reply.table.length > 0 && (
            <table className="data" data-testid="ask-table">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Dates</th>
                  <th>Actual</th>
                  <th>Comparison</th>
                  <th>Change</th>
                </tr>
              </thead>
              <tbody>
                {reply.table.map((r, i) => (
                  <tr key={i}>
                    <td>{r.metric}</td>
                    <td>
                      {formatRange(r.start, r.end)}
                      {r.compared && ` vs ${formatRange(r.comparison_start, r.comparison_end)}`}
                    </td>
                    <td>
                      {formatExact(r.current, r.unit)}
                      {r.no_data && r.current !== null && " (some days have no data)"}
                    </td>
                    <td>{r.compared ? formatExact(r.comparison, r.unit) : "Not compared"}</td>
                    <td>{r.compared ? formatExact(r.percent_change, "pct") : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </>
  );
}
