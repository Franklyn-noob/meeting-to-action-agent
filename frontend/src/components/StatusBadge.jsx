/* Status / escalation visual treatments. */
const STATUS_LABEL = {
  on_track: "On Track",
  overdue: "Overdue",
  needs_attention: "Needs Attention",
  done: "Done",
};

const STATUS_COLOR = {
  on_track: "bg-emerald-500/15 text-emerald-400 ring-emerald-500/30",
  overdue: "bg-red-500/15 text-red-400 ring-red-500/30",
  needs_attention: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  done: "bg-slate-500/15 text-slate-400 ring-slate-500/30",
};

export function StatusBadge({ status }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${
        STATUS_COLOR[status] || STATUS_COLOR.on_track
      }`}
    >
      {STATUS_LABEL[status] || status}
    </span>
  );
}

export function EscalationBadge({ reason }) {
  const label = reason?.replace("_", " ") || "Escalation";
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-red-500/20 px-2.5 py-0.5 text-xs font-semibold text-red-300 ring-1 ring-red-500/40">
      ⚠ {label}
    </span>
  );
}
