import { useState } from "react";
import { api } from "../api";
import { useAsyncAction } from "../hooks";
import { ReportPanel } from "./ReportPanel";

export function JobsForm() {
  const [targetRole, setTargetRole] = useState("");
  const [geography, setGeography] = useState("remote");
  const [experienceLevel, setExperienceLevel] = useState("not specified");
  const [companies, setCompanies] = useState("");
  const [activeOnly, setActiveOnly] = useState(false);
  const { data, loading, error, run } = useAsyncAction(api.runJobs);

  return (
    <section>
      <h2>Job Discovery &amp; Market Intelligence Agent</h2>
      <p className="hint">
        Searches live sources for open roles and early hiring signals. Never fabricates a listing,
        salary, or deadline -- unverifiable claims are flagged, not invented.
      </p>

      <label className="field">
        <span>Target role (optional -- defaults to your profile's target role)</span>
        <input value={targetRole} onChange={(e) => setTargetRole(e.target.value)} placeholder="Backend SDE Intern" />
      </label>

      <div className="grid-2">
        <label className="field">
          <span>Geography</span>
          <select value={geography} onChange={(e) => setGeography(e.target.value)}>
            <option value="remote">Remote</option>
            <option value="local">Local</option>
            <option value="national">National</option>
            <option value="international">International</option>
            <option value="all">All</option>
          </select>
        </label>
        <label className="field">
          <span>Experience level / eligibility</span>
          <input value={experienceLevel} onChange={(e) => setExperienceLevel(e.target.value)} placeholder="student, no prior internship" />
        </label>
      </div>

      <label className="field">
        <span>Prioritized target companies (optional)</span>
        <input value={companies} onChange={(e) => setCompanies(e.target.value)} placeholder="Stripe, Notion, Ramp" />
      </label>

      <label className="checkbox-field">
        <input type="checkbox" checked={activeOnly} onChange={(e) => setActiveOnly(e.target.checked)} />
        <span>Active openings only (skip early-signal scan)</span>
      </label>

      <button
        className="primary"
        disabled={loading}
        onClick={() =>
          run({
            target_role: targetRole || undefined,
            geography,
            experience_level: experienceLevel,
            target_companies: companies || undefined,
            active_only: activeOnly,
          })
        }
      >
        {loading ? "Searching..." : "Find opportunities"}
      </button>

      {error && <div className="banner banner-error">{error}</div>}
      {data && <ReportPanel result={data} />}
    </section>
  );
}
