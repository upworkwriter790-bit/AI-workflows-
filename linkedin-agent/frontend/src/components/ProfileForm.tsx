import { useState } from "react";
import { api } from "../api";
import { useAsyncAction } from "../hooks";
import { ReportPanel } from "./ReportPanel";

export function ProfileForm() {
  const [profileText, setProfileText] = useState("");
  const [targetRole, setTargetRole] = useState("");
  const [referenceProfiles, setReferenceProfiles] = useState("");
  const { data, loading, error, run } = useAsyncAction(api.runProfile);

  const canSubmit = profileText.trim() && targetRole.trim() && !loading;

  return (
    <section>
      <h2>Profile Optimization Agent</h2>
      <p className="hint">Audits your current LinkedIn profile section-by-section against your target role.</p>

      <label className="field">
        <span>Target role / context *</span>
        <input
          value={targetRole}
          onChange={(e) => setTargetRole(e.target.value)}
          placeholder="Final-year CS student targeting backend SDE internships"
        />
      </label>

      <label className="field">
        <span>Current profile content *</span>
        <textarea
          rows={10}
          value={profileText}
          onChange={(e) => setProfileText(e.target.value)}
          placeholder="Paste your headline, About section, experience bullets, etc."
        />
      </label>

      <label className="field">
        <span>Reference/benchmark profiles (optional)</span>
        <textarea
          rows={4}
          value={referenceProfiles}
          onChange={(e) => setReferenceProfiles(e.target.value)}
          placeholder="Paste one or more profiles you want to benchmark against"
        />
      </label>

      <button
        className="primary"
        disabled={!canSubmit}
        onClick={() =>
          run({
            profile_text: profileText,
            target_role: targetRole,
            reference_profiles: referenceProfiles || undefined,
          })
        }
      >
        {loading ? "Auditing..." : "Run profile audit"}
      </button>

      {error && <div className="banner banner-error">{error}</div>}
      {data && <ReportPanel result={data} />}
    </section>
  );
}
