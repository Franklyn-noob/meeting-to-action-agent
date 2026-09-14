import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { StatusBadge } from "./StatusBadge";

export function MeetingsFeed({ stateKey }) {
  const [meetings, setMeetings] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.state();
      const bySource = {};
      for (const t of data.tasks || []) {
        const m = (bySource[t.transcript_source] = bySource[t.transcript_source] || {
          source: t.transcript_source,
          total: 0,
          open: 0,
          escalated: 0,
        });
        m.total += 1;
        if (t.status !== "done") m.open += 1;
        if (t.status === "overdue" || t.status === "needs_attention") m.escalated += 1;
      }
      setMeetings(Object.values(bySource).sort((a, b) => b.escalated - a.escalated));
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // SSE covers live pushes; 10s poll keeps summary fresh without churn.
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateKey]);

  if (loading && meetings.length === 0)
    return (
      <div className="rounded-xl border border-slate-700 bg-surface p-5">
        <p className="text-sm text-slate-400">Loading meetings…</p>
      </div>
    );

  return (
    <div className="flex flex-col gap-3">
      {meetings.map((m) => (
        <div
          key={m.source}
          className={`rounded-xl border p-4 shadow-sm ${
            m.escalated > 0
              ? "border-red-500/40 bg-red-900/10"
              : "border-slate-700 bg-surface2"
          }`}
        >
          <div className="flex items-start justify-between gap-3">
            <h3 className="font-semibold text-slate-100">{m.source}</h3>
            {m.escalated > 0 ? (
              <span className="shrink-0 rounded-full bg-red-500/20 px-2.5 py-0.5 text-xs font-semibold text-red-300 ring-1 ring-red-500/40">
                ⚠ {m.escalated} needs input
              </span>
            ) : (
              <span className="shrink-0 rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-xs font-medium text-emerald-400 ring-1 ring-emerald-500/30">
                handled
              </span>
            )}
          </div>
          <p className="mt-1 text-xs text-slate-400">
            {m.total} task{m.total === 1 ? "" : "s"} · {m.open} open ·{" "}
            {m.escalated} escalated
          </p>
        </div>
      ))}
      {meetings.length === 0 && (
        <p className="text-sm text-slate-400">No meetings processed yet.</p>
      )}
    </div>
  );
}
