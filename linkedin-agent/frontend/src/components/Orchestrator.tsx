import { useState } from "react";
import { api } from "../api";
import { useAsyncAction } from "../hooks";
import { ReportPanel } from "./ReportPanel";
import type { OrchestrateResponse } from "../types";

const EXAMPLES = [
  "Find me remote backend intern roles at Stripe, Notion, and Ramp",
  "Review my LinkedIn profile for a backend SDE internship search",
  "Draft outreach to Jane Doe, Engineering Manager at Stripe, about a backend intern role",
  "Build a content and networking plan targeting fintech recruiters",
];

export function Orchestrator() {
  const [task, setTask] = useState("");
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const { data, loading, error, run } = useAsyncAction((t: string, ov: Record<string, string>) =>
    api.orchestrate(t, ov)
  );

  const submit = async (nextOverrides = overrides) => {
    const result = await run(task, nextOverrides);
    return result;
  };

  const onMissingFieldChange = (field: string, value: string) => {
    setOverrides((prev) => ({ ...prev, [field]: value }));
  };

  const continueWithFilledFields = async () => {
    await submit(overrides);
  };

  return (
    <section>
      <h2>Describe what you want done</h2>
      <p className="hint">
        One box, five specialist agents. The router reads your request, picks the right agent, and
        pulls out whatever details it can find -- it will never invent a company, resume, or profile
        you didn't actually give it. Anything it's missing, you'll be asked for below.
      </p>

      <textarea
        value={task}
        onChange={(e) => setTask(e.target.value)}
        placeholder="e.g. Find me remote backend intern roles at Stripe, Notion, and Ramp"
        rows={4}
      />

      <div className="example-chips">
        {EXAMPLES.map((ex) => (
          <button key={ex} type="button" className="chip" onClick={() => setTask(ex)}>
            {ex}
          </button>
        ))}
      </div>

      <button
        className="primary"
        disabled={loading || !task.trim()}
        onClick={() => {
          setOverrides({});
          submit({});
        }}
      >
        {loading ? "Routing..." : "Submit task"}
      </button>

      {error && <div className="banner banner-error">{error}</div>}

      {data && data.status === "needs_input" && (
        <NeedsInput
          data={data}
          overrides={overrides}
          onChange={onMissingFieldChange}
          onContinue={continueWithFilledFields}
          loading={loading}
        />
      )}

      {data && data.status === "completed" && (
        <div className="result-block">
          <div className="agent-chosen">
            Routed to <strong>{data.agent}</strong> agent -- {data.reasoning}
          </div>
          <ReportPanel result={data.result} />
        </div>
      )}
    </section>
  );
}

function NeedsInput({
  data,
  overrides,
  onChange,
  onContinue,
  loading,
}: {
  data: Extract<OrchestrateResponse, { status: "needs_input" }>;
  overrides: Record<string, string>;
  onChange: (field: string, value: string) => void;
  onContinue: () => void;
  loading: boolean;
}) {
  return (
    <div className="needs-input">
      <p>
        The router matched this to the <strong>{data.agent}</strong> agent ({data.description}) but needs
        a few more details it couldn't find in your message:
      </p>
      {data.missing.map((field) => (
        <label key={field} className="field">
          <span>{field.replace(/_/g, " ")}</span>
          {field.toLowerCase().includes("text") || field.toLowerCase().includes("description") ? (
            <textarea rows={4} value={overrides[field] ?? ""} onChange={(e) => onChange(field, e.target.value)} />
          ) : (
            <input value={overrides[field] ?? ""} onChange={(e) => onChange(field, e.target.value)} />
          )}
        </label>
      ))}
      <button
        className="primary"
        disabled={loading || data.missing.some((f) => !overrides[f]?.trim())}
        onClick={onContinue}
      >
        {loading ? "Running..." : "Continue"}
      </button>
    </div>
  );
}
