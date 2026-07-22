import { useState } from "react";
import { api } from "../api";
import { useAsyncAction } from "../hooks";
import { ReportPanel } from "./ReportPanel";

export function ContentForm() {
  const [companies, setCompanies] = useState("");
  const [priorPerformance, setPriorPerformance] = useState("");
  const { data, loading, error, run } = useAsyncAction(api.runContent);

  const [logIdea, setLogIdea] = useState("");
  const [likes, setLikes] = useState(0);
  const [comments, setComments] = useState(0);
  const [shares, setShares] = useState(0);
  const [profileViews, setProfileViews] = useState(0);
  const [connections, setConnections] = useState(0);
  const { loading: logLoading, error: logError, run: runLog, data: logData } = useAsyncAction(api.logPost);

  return (
    <section>
      <h2>Network Building &amp; Content Strategy Agent</h2>
      <p className="hint">
        Requires a profile audit to already be on file (run the Profile agent first). Builds content
        pillars, a live trend scan, post ideas, and a recruiter-targeting plan.
      </p>

      <label className="field">
        <span>Target companies / recruiter types (optional)</span>
        <input value={companies} onChange={(e) => setCompanies(e.target.value)} placeholder="Stripe, Notion, Ramp" />
      </label>

      <label className="field">
        <span>Prior post performance notes (optional, for repeat cycles)</span>
        <textarea rows={4} value={priorPerformance} onChange={(e) => setPriorPerformance(e.target.value)} />
      </label>

      <button
        className="primary"
        disabled={loading}
        onClick={() => run({ target_companies: companies || undefined, prior_post_performance: priorPerformance || undefined })}
      >
        {loading ? "Building strategy..." : "Generate content strategy"}
      </button>

      {error && <div className="banner banner-error">{error}</div>}
      {data && <ReportPanel result={data} />}

      <hr />

      <h3>Log real post performance</h3>
      <p className="hint">
        Once you've actually published a post from this agent's ideas, log the real numbers here so the
        next cycle's feedback loop can use them.
      </p>
      <div className="grid-2">
        <label className="field">
          <span>Post idea *</span>
          <input value={logIdea} onChange={(e) => setLogIdea(e.target.value)} />
        </label>
        <label className="field">
          <span>Likes</span>
          <input type="number" value={likes} onChange={(e) => setLikes(Number(e.target.value))} />
        </label>
        <label className="field">
          <span>Comments</span>
          <input type="number" value={comments} onChange={(e) => setComments(Number(e.target.value))} />
        </label>
        <label className="field">
          <span>Shares</span>
          <input type="number" value={shares} onChange={(e) => setShares(Number(e.target.value))} />
        </label>
        <label className="field">
          <span>Profile views after</span>
          <input type="number" value={profileViews} onChange={(e) => setProfileViews(Number(e.target.value))} />
        </label>
        <label className="field">
          <span>New connection requests after</span>
          <input type="number" value={connections} onChange={(e) => setConnections(Number(e.target.value))} />
        </label>
      </div>
      <button
        disabled={!logIdea.trim() || logLoading}
        onClick={() => runLog({ idea: logIdea, likes, comments, shares, profile_views: profileViews, connections })}
      >
        {logLoading ? "Logging..." : "Log performance"}
      </button>
      {logError && <div className="banner banner-error">{logError}</div>}
      {logData?.ok && <div className="banner banner-info">Logged.</div>}
    </section>
  );
}
