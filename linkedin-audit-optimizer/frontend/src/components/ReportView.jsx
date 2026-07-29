import ScoreGauge from './ScoreGauge.jsx';

function Section({ title, children }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6">
      <h3 className="text-base font-semibold text-slate-900 mb-4">{title}</h3>
      {children}
    </div>
  );
}

function FlaggedQuote({ text }) {
  return (
    <blockquote className="mt-1 border-l-2 border-slate-300 pl-3 text-sm italic text-slate-600">
      “{text}”
    </blockquote>
  );
}

export default function ReportView({ report }) {
  return (
    <div className="space-y-6">
      <ScoreGauge score={report.score} band={report.band} />

      <Section title="Summary">
        <p className="text-sm text-slate-700 leading-relaxed">{report.summary}</p>
      </Section>

      {report.weaknesses?.length > 0 && (
        <Section title="What's dragging the score down">
          <ul className="space-y-4">
            {report.weaknesses.map((w, i) => (
              <li key={i} className="text-sm">
                <p className="font-medium text-slate-800">{w.issue}</p>
                <FlaggedQuote text={w.flagged_text} />
                <p className="mt-1 text-slate-600">{w.why_it_hurts}</p>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {report.strengths?.length > 0 && (
        <Section title="What's already working">
          <ul className="space-y-4">
            {report.strengths.map((s, i) => (
              <li key={i} className="text-sm">
                <p className="font-medium text-slate-800">{s.point}</p>
                <FlaggedQuote text={s.flagged_text} />
              </li>
            ))}
          </ul>
        </Section>
      )}

      {report.engagement_highlights?.length > 0 && (
        <Section title="Helping engagement">
          <ul className="space-y-4">
            {report.engagement_highlights.map((h, i) => (
              <li key={i} className="text-sm">
                <p className="font-medium text-slate-800">{h.point}</p>
                <FlaggedQuote text={h.flagged_text} />
              </li>
            ))}
          </ul>
        </Section>
      )}

      {report.recommendations?.length > 0 && (
        <Section title="Recommendations to push toward 95+">
          <ul className="list-disc list-inside space-y-2 text-sm text-slate-700">
            {report.recommendations.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}
