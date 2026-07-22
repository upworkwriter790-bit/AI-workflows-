import { useState } from "react";
import { api } from "../api";
import { useAsyncAction } from "../hooks";
import { ReportPanel } from "./ReportPanel";

export function ResumeForm() {
  const [masterResume, setMasterResume] = useState("");
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [location, setLocation] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [channel, setChannel] = useState<"cold" | "referral">("cold");
  const [usedReferral, setUsedReferral] = useState(false);
  const [logToPipeline, setLogToPipeline] = useState(true);
  const { data, loading, error, run } = useAsyncAction(api.runResume);

  const canSubmit = [masterResume, company, role, location, jobDescription].every((v) => v.trim()) && !loading;

  return (
    <section>
      <h2>Resume Tailoring &amp; Pipeline Agent</h2>
      <p className="hint">
        Tailors your resume to one specific listing, flags hard requirement gaps honestly, and (unless
        disabled) logs the application to your pipeline tracker.
      </p>

      <div className="grid-2">
        <label className="field">
          <span>Company *</span>
          <input value={company} onChange={(e) => setCompany(e.target.value)} />
        </label>
        <label className="field">
          <span>Role *</span>
          <input value={role} onChange={(e) => setRole(e.target.value)} />
        </label>
        <label className="field">
          <span>Location *</span>
          <input value={location} onChange={(e) => setLocation(e.target.value)} />
        </label>
        <label className="field">
          <span>Channel</span>
          <select value={channel} onChange={(e) => setChannel(e.target.value as "cold" | "referral")}>
            <option value="cold">Cold</option>
            <option value="referral">Referral</option>
          </select>
        </label>
      </div>

      <label className="checkbox-field">
        <input type="checkbox" checked={usedReferral} onChange={(e) => setUsedReferral(e.target.checked)} />
        <span>Used a referral</span>
      </label>
      <label className="checkbox-field">
        <input type="checkbox" checked={logToPipeline} onChange={(e) => setLogToPipeline(e.target.checked)} />
        <span>Log this application to the pipeline tracker</span>
      </label>

      <label className="field">
        <span>Job description *</span>
        <textarea rows={8} value={jobDescription} onChange={(e) => setJobDescription(e.target.value)} />
      </label>

      <label className="field">
        <span>Master resume *</span>
        <textarea rows={10} value={masterResume} onChange={(e) => setMasterResume(e.target.value)} />
      </label>

      <button
        className="primary"
        disabled={!canSubmit}
        onClick={() =>
          run({
            master_resume_text: masterResume,
            company,
            role,
            location,
            job_description: jobDescription,
            channel,
            used_referral: usedReferral,
            log_to_pipeline: logToPipeline,
          })
        }
      >
        {loading ? "Tailoring..." : "Tailor resume"}
      </button>

      {error && <div className="banner banner-error">{error}</div>}
      {data && <ReportPanel result={data} />}
    </section>
  );
}
