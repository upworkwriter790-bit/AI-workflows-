import { useEffect, useState } from "react";
import { api } from "../api";
import type { ExecutionEntry } from "../types";

const POLL_MS = 4000;

export function ExecutionLog() {
  const [entries, setEntries] = useState<ExecutionEntry[]>([]);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const data = await api.getExecutions();
        if (!cancelled) setEntries(data);
      } catch {
        // transient network hiccups shouldn't spam the console during polling
      }
    };
    poll();
    const interval = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  if (entries.length === 0) {
    return <div className="hint">No agent runs yet this session.</div>;
  }

  return (
    <ul className="execution-log">
      {entries.map((e) => (
        <li key={e.id} className={`execution-entry status-${e.status}`}>
          <div className="execution-top">
            <span className="execution-agent">{e.agent}</span>
            <span className={`badge badge-${e.status}`}>{e.status}</span>
            <span className="execution-source">via {e.source}</span>
            {e.duration_s != null && <span className="execution-duration">{e.duration_s}s</span>}
          </div>
          <div className="execution-time">{e.started_at}</div>
          {e.error && <div className="execution-error">{e.error}</div>}
        </li>
      ))}
    </ul>
  );
}
