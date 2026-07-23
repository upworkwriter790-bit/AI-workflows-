import { useEffect, useState } from "react";
import { api } from "./api";
import { Orchestrator } from "./components/Orchestrator";
import { ProfileForm } from "./components/ProfileForm";
import { ContentForm } from "./components/ContentForm";
import { JobsForm } from "./components/JobsForm";
import { ResumeForm } from "./components/ResumeForm";
import { OutreachForm } from "./components/OutreachForm";
import { StatusDashboard } from "./components/StatusDashboard";
import { ExecutionLog } from "./components/ExecutionLog";

const TABS = [
  { id: "orchestrate", label: "Ask the copilot", render: () => <Orchestrator /> },
  { id: "profile", label: "Profile", render: () => <ProfileForm /> },
  { id: "content", label: "Content & Network", render: () => <ContentForm /> },
  { id: "jobs", label: "Job Discovery", render: () => <JobsForm /> },
  { id: "resume", label: "Resume Tailoring", render: () => <ResumeForm /> },
  { id: "outreach", label: "Outreach", render: () => <OutreachForm /> },
  { id: "status", label: "Status & Pipeline", render: () => <StatusDashboard /> },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function App() {
  const [active, setActive] = useState<TabId>("orchestrate");
  const [health, setHealth] = useState<{ api_key_configured: boolean; model: string; provider: string } | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch((e) => setHealthError(e instanceof Error ? e.message : String(e)));
  }, []);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>LinkedIn Agent</h1>
          <p>Career copilot -- drafts and researches only, nothing here ever posts or applies for you.</p>
        </div>
        <div className="health-badge">
          {healthError ? (
            <span className="badge badge-error">Backend unreachable</span>
          ) : health ? (
            <span className={`badge ${health.api_key_configured ? "badge-success" : "badge-error"}`}>
              {health.api_key_configured
                ? `Connected -- ${health.provider} / ${health.model}`
                : `${health.provider}: API key not configured`}
            </span>
          ) : (
            <span className="badge">Checking backend...</span>
          )}
        </div>
      </header>

      <div className="app-body">
        <nav className="tabs">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              className={tab.id === active ? "tab active" : "tab"}
              onClick={() => setActive(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <main className="tab-content">{TABS.find((t) => t.id === active)?.render()}</main>

        <aside className="execution-sidebar">
          <h3>Agent execution</h3>
          <ExecutionLog />
        </aside>
      </div>
    </div>
  );
}
