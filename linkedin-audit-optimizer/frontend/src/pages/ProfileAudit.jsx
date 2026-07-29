import { useState } from 'react';
import UploadDropzone from '../components/UploadDropzone.jsx';
import ReportView from '../components/ReportView.jsx';
import { submitAudit } from '../api/auditApi.js';

export default function ProfileAudit() {
  const [pasted, setPasted] = useState('');
  const [file, setFile] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [report, setReport] = useState(null);

  const looksLikeUrl = /^https?:\/\//i.test(pasted.trim());
  const canSubmit = (pasted.trim().length > 0 || file) && !isLoading;

  async function handleTestAudit() {
    setError('');
    setReport(null);
    setIsLoading(true);
    try {
      const result = await submitAudit({
        link: looksLikeUrl ? pasted.trim() : undefined,
        content: !looksLikeUrl ? pasted.trim() : undefined,
        file,
      });
      setReport(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto p-6 sm:p-10 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Profile Audit</h1>
        <p className="text-sm text-slate-600 mt-1">
          Paste a link or your LinkedIn profile content below, and/or drop a document to have it
          scanned. Then run the audit to get a scored report.
        </p>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-5">
        <div>
          <label htmlFor="pasted-content" className="block text-sm font-medium text-slate-700 mb-2">
            Paste a link or content
          </label>
          <textarea
            id="pasted-content"
            rows={6}
            value={pasted}
            onChange={(e) => setPasted(e.target.value)}
            placeholder="Paste your LinkedIn profile URL, or paste the actual profile text (headline, About section, experience bullets, etc.)"
            className="w-full rounded-xl border border-slate-300 p-3 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Or upload a document
          </label>
          <UploadDropzone file={file} onFileSelected={setFile} onFileRemoved={() => setFile(null)} />
        </div>

        <button
          type="button"
          onClick={handleTestAudit}
          disabled={!canSubmit}
          className={[
            'w-full rounded-xl py-3 text-sm font-semibold transition-colors',
            canSubmit
              ? 'bg-blue-600 text-white hover:bg-blue-700'
              : 'bg-slate-200 text-slate-400 cursor-not-allowed',
          ].join(' ')}
        >
          {isLoading ? 'Running audit…' : 'Test the Audit'}
        </button>

        {error && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">
            {error}
          </p>
        )}
      </div>

      {report && <ReportView report={report} />}
    </div>
  );
}
