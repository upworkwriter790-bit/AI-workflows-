const BAND_STYLES = {
  'Very Poor': { ring: '#ef4444', bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
  'Poor': { ring: '#f97316', bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200' },
  'Good': { ring: '#eab308', bg: 'bg-yellow-50', text: 'text-yellow-700', border: 'border-yellow-200' },
  'Very Good': { ring: '#22c55e', bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' },
};

const BAND_DESCRIPTIONS = {
  'Very Poor': 'Needs a substantial rewrite before it will work for you.',
  'Poor': 'Missing the basics — significant gaps are holding this back.',
  'Good': 'Solid foundation, but there is clear room to improve.',
  'Very Good': 'Already strong — fine-tune it to push toward 95+.',
};

export default function ScoreGauge({ score, band }) {
  const style = BAND_STYLES[band] || BAND_STYLES['Good'];
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - Math.min(Math.max(score, 0), 100) / 100);

  return (
    <div className={`flex items-center gap-6 rounded-2xl border ${style.border} ${style.bg} p-6`}>
      <div className="relative w-32 h-32 shrink-0">
        <svg className="w-32 h-32 -rotate-90">
          <circle cx="64" cy="64" r={radius} fill="none" stroke="#e2e8f0" strokeWidth="12" />
          <circle
            cx="64"
            cy="64"
            r={radius}
            fill="none"
            stroke={style.ring}
            strokeWidth="12"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-bold text-slate-900">{score}</span>
          <span className="text-xs text-slate-500">/ 100</span>
        </div>
      </div>
      <div>
        <p className={`text-lg font-semibold ${style.text}`}>{band}</p>
        <p className="text-sm text-slate-600 mt-1">{BAND_DESCRIPTIONS[band]}</p>
      </div>
    </div>
  );
}
