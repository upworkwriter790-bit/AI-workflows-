import { marked } from "marked";
import type { AgentResult } from "../types";

export function ReportPanel({ result }: { result: AgentResult }) {
  const html = marked.parse(result.report, { async: false }) as string;

  return (
    <div className="report-panel">
      {result.warnings.length > 0 && (
        <div className="banner banner-warning">
          <strong>Guardrail warnings -- review before acting:</strong>
          <ul>
            {result.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="markdown-body" dangerouslySetInnerHTML={{ __html: html }} />

      {result.sources.length > 0 && (
        <div className="sources">
          <h4>Sources</h4>
          <ul>
            {result.sources.map((s, i) => (
              <li key={i}>
                <a href={s.url} target="_blank" rel="noreferrer">
                  {s.title || s.url}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.handoff && (
        <div className="banner banner-handoff">
          <strong>Handoff:</strong> {result.handoff}
        </div>
      )}

      {result.pipeline_entry && (
        <div className="banner banner-info">
          Logged to pipeline: id=<code>{String(result.pipeline_entry.id)}</code>
        </div>
      )}

      {result.path && <div className="report-path">Saved to {result.path}</div>}
    </div>
  );
}
