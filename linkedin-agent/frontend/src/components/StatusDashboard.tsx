import { useEffect, useState, useCallback } from "react";
import { api } from "../api";
import type { StatusResponse } from "../types";

export function StatusDashboard() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [trackingId, setTrackingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const s = await api.getStatus();
      setStatus(s);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const stages = ["Applied", "Screened", "Assessment", "Interview", "Offer", "Rejected"];

  const setStage = async (id: string, stage: string) => {
    await api.trackPipeline({ id, stage });
    setTrackingId(null);
    load();
  };

  const resolveHandoff = async (index: number) => {
    await api.resolveHandoff(index);
    load();
  };

  if (error) return <div className="banner banner-error">{error}</div>;
  if (!status) return <div className="hint">Loading status...</div>;

  const diag = status.pipeline.diagnostics;

  return (
    <section>
      <div className="dashboard-header">
        <h2>Status</h2>
        <button onClick={load}>Refresh</button>
      </div>

      <div className="card">
        <h3>Profile</h3>
        {status.profile ? (
          <>
            <div>Target role: {status.profile.target_role}</div>
            <div>Last audited: {status.profile.updated_at}</div>
          </>
        ) : (
          <div className="hint">No profile audit on file yet.</div>
        )}
      </div>

      <div className="card">
        <div className="dashboard-header">
          <h3>Pipeline</h3>
          <a href={api.exportPipelineUrl()}>Export CSV</a>
        </div>
        <div className="stats-row">
          {Object.entries(status.pipeline.stats).map(([k, v]) => (
            <div key={k} className="stat-pill">
              <span className="stat-value">{v}</span>
              <span className="stat-label">{k}</span>
            </div>
          ))}
        </div>

        {status.pipeline.items.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Company</th>
                <th>Role</th>
                <th>Channel</th>
                <th>Stage</th>
                <th>Applied</th>
                <th>Last update</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {status.pipeline.items.map((it) => (
                <tr key={it.id} className={it.is_stale ? "row-stale" : ""}>
                  <td>{it.company}</td>
                  <td>{it.role}</td>
                  <td>{it.channel}</td>
                  <td>{it.display_stage}</td>
                  <td>{it.applied_date.slice(0, 10)}</td>
                  <td>{it.last_update.slice(0, 10)}</td>
                  <td>
                    {trackingId === it.id ? (
                      <select
                        autoFocus
                        defaultValue=""
                        onChange={(e) => e.target.value && setStage(it.id, e.target.value)}
                        onBlur={() => setTrackingId(null)}
                      >
                        <option value="" disabled>
                          Set stage...
                        </option>
                        {stages.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <button onClick={() => setTrackingId(it.id)}>Update</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {diag && (
          <div className="diagnostics">
            <div>
              Referral applications: {diag.referral_count} (ghost rate: {diag.referral_ghost_rate_pct ?? "n/a"}%)
            </div>
            <div>
              Cold applications: {diag.cold_count} (ghost rate: {diag.cold_ghost_rate_pct ?? "n/a"}%)
            </div>
            {diag.referral_ghost_rate_pct != null &&
              diag.cold_ghost_rate_pct != null &&
              diag.cold_ghost_rate_pct > diag.referral_ghost_rate_pct + 15 && (
                <div className="banner banner-warning">
                  Cold applications are ghosting noticeably more than referred ones -- prioritize
                  outreach/networking before applying cold to the next batch of roles.
                </div>
              )}
          </div>
        )}
      </div>

      <div className="card">
        <h3>Outreach</h3>
        {status.outreach.length > 0 ? (
          <table>
            <thead>
              <tr>
                <th>Company</th>
                <th>Person</th>
                <th>Role</th>
                <th>Status</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {status.outreach.map((o, i) => (
                <tr key={i}>
                  <td>{o.company}</td>
                  <td>{o.target_person}</td>
                  <td>{o.role}</td>
                  <td>{o.status}</td>
                  <td>{o.date.slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="hint">No outreach drafted yet.</div>
        )}
      </div>

      <div className="card">
        <h3>Open cross-agent handoffs</h3>
        {status.handoffs.filter((h) => !h.resolved).length > 0 ? (
          <ul className="handoff-list">
            {status.handoffs
              .filter((h) => !h.resolved)
              .map((h) => (
                <li key={h.index}>
                  <span>
                    <strong>({h.from_agent})</strong> {h.note}
                  </span>
                  <button onClick={() => resolveHandoff(h.index)}>Resolve</button>
                </li>
              ))}
          </ul>
        ) : (
          <div className="hint">None open.</div>
        )}
      </div>
    </section>
  );
}
