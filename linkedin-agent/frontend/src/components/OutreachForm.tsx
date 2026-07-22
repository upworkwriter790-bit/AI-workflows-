import { useState } from "react";
import { api } from "../api";
import { useAsyncAction } from "../hooks";
import { ReportPanel } from "./ReportPanel";

const STATUS_OPTIONS = ["sent", "responded_positive", "responded_negative", "no_response", "closed"];

export function OutreachForm() {
  const [company, setCompany] = useState("");
  const [targetPerson, setTargetPerson] = useState("");
  const [role, setRole] = useState("");
  const [resumeSummary, setResumeSummary] = useState("");
  const [warmth, setWarmth] = useState<"cold" | "warmed-up" | "referral-available">("cold");
  const [referralAvailable, setReferralAvailable] = useState(false);
  const { data, loading, error, run } = useAsyncAction(api.runOutreach);

  const [statusCompany, setStatusCompany] = useState("");
  const [statusPerson, setStatusPerson] = useState("");
  const [status, setStatus] = useState(STATUS_OPTIONS[0]);
  const { loading: statusLoading, error: statusError, run: runStatus, data: statusData } =
    useAsyncAction(api.updateOutreachStatus);

  const canSubmit = company.trim() && targetPerson.trim() && role.trim() && !loading;

  return (
    <section>
      <h2>Cold Outreach &amp; Recruiter Engagement Agent</h2>
      <p className="hint">
        Researches a specific named person, then drafts a low-friction first-touch message with a
        differentiation check and follow-up plan.
      </p>

      <div className="grid-2">
        <label className="field">
          <span>Company *</span>
          <input value={company} onChange={(e) => setCompany(e.target.value)} />
        </label>
        <label className="field">
          <span>Target person (name, title) *</span>
          <input value={targetPerson} onChange={(e) => setTargetPerson(e.target.value)} placeholder="Jane Doe, Engineering Manager" />
        </label>
        <label className="field">
          <span>Role *</span>
          <input value={role} onChange={(e) => setRole(e.target.value)} />
        </label>
        <label className="field">
          <span>Relationship warmth</span>
          <select value={warmth} onChange={(e) => setWarmth(e.target.value as typeof warmth)}>
            <option value="cold">Cold</option>
            <option value="warmed-up">Warmed-up</option>
            <option value="referral-available">Referral available</option>
          </select>
        </label>
      </div>

      <label className="checkbox-field">
        <input type="checkbox" checked={referralAvailable} onChange={(e) => setReferralAvailable(e.target.checked)} />
        <span>A referral path is available</span>
      </label>

      <label className="field">
        <span>Tailored resume/application summary (optional)</span>
        <textarea rows={4} value={resumeSummary} onChange={(e) => setResumeSummary(e.target.value)} />
      </label>

      <button
        className="primary"
        disabled={!canSubmit}
        onClick={() =>
          run({
            company,
            target_person: targetPerson,
            role,
            resume_summary: resumeSummary || undefined,
            relationship_warmth: warmth,
            referral_available: referralAvailable,
          })
        }
      >
        {loading ? "Researching & drafting..." : "Draft outreach"}
      </button>

      {error && <div className="banner banner-error">{error}</div>}
      {data && <ReportPanel result={data} />}

      <hr />

      <h3>Update outreach status</h3>
      <div className="grid-2">
        <label className="field">
          <span>Company</span>
          <input value={statusCompany} onChange={(e) => setStatusCompany(e.target.value)} />
        </label>
        <label className="field">
          <span>Target person</span>
          <input value={statusPerson} onChange={(e) => setStatusPerson(e.target.value)} />
        </label>
        <label className="field">
          <span>Status</span>
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
      </div>
      <button
        disabled={!statusCompany.trim() || !statusPerson.trim() || statusLoading}
        onClick={() => runStatus({ company: statusCompany, target_person: statusPerson, status })}
      >
        {statusLoading ? "Updating..." : "Update status"}
      </button>
      {statusError && <div className="banner banner-error">{statusError}</div>}
      {statusData?.ok && <div className="banner banner-info">Updated.</div>}
    </section>
  );
}
