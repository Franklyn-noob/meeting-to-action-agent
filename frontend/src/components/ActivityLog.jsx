import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { EscalationBadge } from "./StatusBadge";

const KIND_LABEL = { auto_handled: "Auto-handled", escalation: "Escalation" };

export function ActivityLog({ stateKey }) {
  const [events, setEvents] = useState([]);
  const [visibleEscalations, setVisibleEscalations] = useState([]);
  const esRef = useRef(null);

  const refresh = async () => {
    try {
      const data = await api.activity();
      setEvents(data);
      setVisibleEscalations(data.filter((e) => e.kind === "escalation"));
    } catch (e) {
      console.error(e);
    }
  };

  // Live SSE stream: push new activity as the agent emits it.
  useEffect(() => {
    const src = api.activitySSE();
    src.onmessage = (ev) => {
      try {
        const payload = JSON.parse(ev.data);
        if (payload.type === "snapshot") {
          setEvents(payload.data);
          setVisibleEscalations(
            payload.data.filter((e) => e.kind === "escalation")
          );
        }
      } catch {
        /* ignore malformed frames */
      }
    };
    src.onerror = () => src.close();
    return () => src.close();
  }, []);

  useEffect(() => {
    refresh();
    // SSE is the primary live activity channel; this poll is a fallback safety net.
    const t = setInterval(refresh, 10000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateKey]);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
          Agent activity
        </h3>
        <span className="rounded-full bg-red-500/15 px-2.5 py-0.5 text-xs font-semibold text-red-300 ring-1 ring-red-500/30">
          ⚠ {visibleEscalations.length} escalation
          {visibleEscalations.length === 1 ? "" : "s"} need your input
        </span>
      </div>

      <div className="max-h-[560px] overflow-y-auto">
        {events.length === 0 ? (
          <p className="text-sm text-slate-400">No activity yet.</p>
        ) : (
          events.slice().reverse().map((e) => (
            <EventRow key={`${e.timestamp}-${e.summary}`} event={e} />
          ))
        )}
      </div>
    </div>
  );
}

function EventRow({ event }) {
  const isEsc = event.kind === "escalation";
  return (
    <div
      className={`border-l-4 py-3 pr-3 pl-4 mb-2 rounded-md bg-surface last:mb-0 ${
        isEsc
          ? "border-l-red-500 bg-red-900/15"
          : "border-l-slate-600"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-0.5">
          <span
            className={`text-xs font-semibold uppercase ${
              isEsc ? "text-red-300" : "text-slate-400"
            }`}
          >
            {isEsc ? (
              <EscalationBadge reason={event.escalation_reason} />
            ) : (
              "Auto-handled"
            )}
          </span>
          <p
            className={`text-sm ${isEsc ? "text-red-200" : "text-slate-200"}`}
          >
            {event.summary}
          </p>
        </div>
        <time dateTime={event.timestamp} className="shrink-0 text-xs text-slate-500">
          {new Date(event.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          })}
        </time>
      </div>
    </div>
  );
}
