/* Lightweight JSON client for the FastAPI backend. */
const base = "/api";

export async function fetchJSON(url, opts = {}) {
  const res = await fetch(base + url, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  state: () => fetchJSON("/state"),
  config: () => fetchJSON("/config"),
  tasks: () => fetchJSON("/tasks"),
  escalations: () => fetchJSON("/escalations"),
  activity: () => fetchJSON("/activity"),
  processTranscript: (body) =>
    fetchJSON("/process-transcript", { method: "POST", body: JSON.stringify(body) }),
  runDailyCheck: () => fetchJSON("/run-daily-check", { method: "POST" }),
  markDone: (id) => fetchJSON(`/tasks/${id}/done`, { method: "POST" }),
  seed: () => fetchJSON("/demo/seed", { method: "POST" }),
  activitySSE: () => new EventSource(base + "/activity/sse"),
};
