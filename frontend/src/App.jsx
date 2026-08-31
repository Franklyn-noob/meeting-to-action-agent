import { useEffect, useState } from "react";
import { api } from "./lib/api";
import { MeetingsFeed } from "./components/MeetingsFeed";
import { TaskBoard } from "./components/TaskBoard";
import { ActivityLog } from "./components/ActivityLog";

export default function App() {
  const [config, setConfig] = useState(null);
  const [stateKey, setStateKey] = useState(0); // bump to refetch panels
  const [submitting, setSubmitting] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [resultMsg, setResultMsg] = useState("");

  const bump = () => setStateKey((k) => k + 1);

  useEffect(() => {
    api.config()
      .then(setConfig)
      .catch(() => setConfig({ model_provider: "unknown" }));
  }, []);

  const seed = async () => {
    const r = await api.seed();
    bump();
    setResultMsg(`Demo seeded: ${r.seeded.length} meetings.`);
  };

  const dailyCheck = async () => {
    const r = await api.runDailyCheck();
    bump();
    setResultMsg(`Daily check: ${r.count} new escalation(s).`);
  };

  const processTranscript = async () => {
    if (!transcript.trim()) return;
    setSubmitting(true);
    setResultMsg("");
    try {
      const r = await api.processTranscript({
        transcript,
        source: "live-meeting",
      });
      bump();
      setResultMsg(
        `Processed: ${r.tasks.length} task(s), ${r.escalations.length} escalation(s).`
      );
      setTranscript("");
    } catch (e) {
      setResultMsg(`Error: ${e.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const offline = config?.model_provider === "fake";

  return (
    <div className="flex min-h-full flex-col bg-slate-900 text-slate-100">
      <header className="border-b border-slate-800 bg-surface px-5 py-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold text-slate-50">
            Meeting-to-Action Agent
          </h1>
          <p className="text-sm text-slate-400">
            Extracts action items from transcripts, tracks them silently, and
            only interrupts you when a task is overdue or ownership is unclear.
          </p>
        </div>
        {config && (
          <span
            className={`mt-2 inline-flex items-center self-start rounded-full px-2.5 py-0.5 text-xs font-medium ${
              offline
                ? "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30"
                : "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30"
            }`}
          >
            {offline ? "Offline demo mode" : `Model: ${config.model_provider}`}
            {config && <span className="mx-1.5">·</span>}
            <span>email: {config.email_sender}</span>
          </span>
        )}
      </header>

      <main className="flex-1 overflow-y-auto p-5">
        <div className="mx-auto grid max-w-7xl gap-8">
          <Controls
            {...{ submitting, transcript, setTranscript, resultMsg }}
            onSeed={seed}
            onDailyCheck={dailyCheck}
            onSubmit={processTranscript}
          />
          <section className="grid gap-6 lg:grid-cols-3">
            <Panel title="Meetings" subtitle="Processed meetings">
              <MeetingsFeed stateKey={stateKey} />
            </Panel>
            <Panel title="Task board" subtitle="Grouped by status" className="lg:col-span-2">
              <TaskBoard stateKey={stateKey} />
            </Panel>
          </section>
          <Panel title="Activity log" subtitle="Auto-handled vs escalations">
            <ActivityLog stateKey={stateKey} />
          </Panel>
        </div>
      </main>

      <footer className="border-t border-slate-800 px-5 py-3 text-xs text-slate-500">
        <span>Built with the Strands Agents SDK · deployed on Amazon Bedrock AgentCore</span>
        <span className="mx-2">·</span>
        <span>MIT licensed</span>
      </footer>
    </div>
  );
}

function Panel({ title, subtitle, children, className = "" }) {
  return (
    <div
      className={`rounded-xl border border-slate-800 bg-surface p-5 shadow-xl ${className}`}
    >
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-slate-200">{title}</h2>
        <p className="text-sm text-slate-400">{subtitle}</p>
      </div>
      {children}
    </div>
  );
}

function Controls({
  submitting,
  transcript,
  setTranscript,
  resultMsg,
  onSeed,
  onDailyCheck,
  onSubmit,
}) {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-slate-800 bg-surface p-5">
      <div className="flex flex-wrap gap-2">
        <button
          onClick={onSeed}
          className="rounded-lg border border-slate-700 bg-surface2 px-3 py-1.5 text-sm font-medium text-slate-200 hover:bg-slate-700"
        >
          Seed demo meetings
        </button>
        <button
          onClick={onDailyCheck}
          className="rounded-lg border border-slate-700 bg-surface2 px-3 py-1.5 text-sm font-medium text-slate-200 hover:bg-slate-700"
        >
          Run daily check
        </button>
      </div>

      <div className="flex flex-col gap-2">
        <label className="text-xs font-medium text-slate-300">
          New meeting transcript
        </label>
        <textarea
          value={transcript}
          onChange={(e) => setTranscript(e.target.value)}
          placeholder="Paste a meeting transcript here, then process it…"
          rows={3}
          className="w-full resize-y rounded-lg border border-slate-700 bg-surface2 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
        />
        <div className="flex items-center justify-between">
          <button
            onClick={onSubmit}
            disabled={submitting || !transcript.trim()}
            className="rounded-lg bg-sky-500 px-3 py-1.5 text-sm font-semibold text-slate-900 transition hover:bg-sky-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "Processing…" : "Process transcript"}
          </button>
          {resultMsg && <span className="text-xs text-slate-300">{resultMsg}</span>}
        </div>
      </div>
    </div>
  );
}
