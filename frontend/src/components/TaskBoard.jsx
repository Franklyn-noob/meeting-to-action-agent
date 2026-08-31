import { useEffect, useState } from "react";
import { api } from "../lib/api";

const STATUS_ORDER = ["on_track", "overdue", "needs_attention", "done"];
const STATUS_TITLE = {
  on_track: "On Track",
  overdue: "Overdue",
  needs_attention: "Needs Attention",
  done: "Done",
};

export function TaskBoard({ stateKey }) {
  const [tasksByStatus, setTasksByStatus] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = async () => {
    setLoading(true);
    try {
      const data = await api.state();
      setTasksByStatus(data.tasks_by_status || {});
    } catch (e) {
      setError(String(e.message));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let ignore = false;
    (async () => {
      await refresh();
      if (ignore) return;
      const t = setInterval(refresh, 4000);
      return () => clearInterval(t);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateKey]);

  const onMarkDone = async (id) => {
    try {
      await api.markDone(id);
      await refresh();
    } catch (e) {
      setError(String(e.message));
    }
  };

  if (loading && Object.keys(tasksByStatus).length === 0)
    return (
      <div className="rounded-xl border border-slate-700 bg-surface p-5">
        <p className="text-sm text-slate-400">Loading tasks…</p>
      </div>
    );

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {STATUS_ORDER.map((status) => {
        const items = tasksByStatus[status] || [];
        const border =
          status === "overdue"
            ? "border-red-500/40"
            : status === "needs_attention"
              ? "border-amber-500/40"
              : "border-slate-700";
        return (
          <div
            key={status}
            className={`flex flex-col gap-3 rounded-xl border ${border} bg-surface2 p-4`}
          >
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
              {STATUS_TITLE[status]} <span className="text-slate-500">({items.length})</span>
            </h3>
            {items.length === 0 ? (
              <p className="text-xs text-slate-500">No tasks here.</p>
            ) : (
              items.map((t) => <TaskCard key={t.id} task={t} onMarkDone={onMarkDone} />)
            )}
          </div>
        );
      })}
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  );
}

function TaskCard({ task, onMarkDone }) {
  const duePast =
    task.due_date && new Date(task.due_date) < new Date();
  return (
    <div className="rounded-lg border border-slate-700 bg-surface p-3 shadow-sm">
      <p className="text-sm text-slate-100">{task.description}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-400">
        {task.owner ? (
          <span className="font-medium text-slate-200">@{task.owner}</span>
        ) : (
          <span className="font-medium text-amber-300">unassigned</span>
        )}
        {task.due_date && (
          <span
            className={
              duePast && task.status !== "done"
                ? "text-red-400"
                : "text-slate-400"
            }
          >
            due {task.due_date}
          </span>
        )}
        <span className="rounded bg-slate-800 px-1.5 py-0.25">conf {Math.round((task.owner_confidence || 0) * 100)}%</span>
      </div>
      {task.status !== "done" && (
        <button
          onClick={() => onMarkDone(task.id)}
          className="mt-2 text-xs font-medium text-sky-400 hover:text-sky-300"
        >
          Mark done
        </button>
      )}
    </div>
  );
}
