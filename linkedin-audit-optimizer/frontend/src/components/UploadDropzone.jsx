import { useRef, useState } from 'react';

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB
const ALLOWED_EXTENSIONS = ['pdf', 'doc', 'docx', 'xlsx', 'xls', 'csv', 'png', 'jpg', 'jpeg', 'webp', 'gif'];
const ACCEPT_ATTR = ALLOWED_EXTENSIONS.map((ext) => `.${ext}`).join(',');

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export default function UploadDropzone({ file, onFileSelected, onFileRemoved }) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState('');
  const inputRef = useRef(null);

  function validateAndSet(selectedFile) {
    if (!selectedFile) return;

    const ext = selectedFile.name.split('.').pop().toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setError(`Unsupported file type ".${ext}". Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`);
      return;
    }
    if (selectedFile.size > MAX_FILE_SIZE) {
      setError(`"${selectedFile.name}" is ${formatBytes(selectedFile.size)} — files must be under 5MB.`);
      return;
    }

    setError('');
    onFileSelected(selectedFile);
  }

  function handleDrop(e) {
    e.preventDefault();
    setIsDragOver(false);
    validateAndSet(e.dataTransfer.files?.[0]);
  }

  function handleInputChange(e) {
    validateAndSet(e.target.files?.[0]);
    e.target.value = ''; // allow re-selecting the same file after removing it
  }

  function handleRemove() {
    setError('');
    onFileRemoved();
  }

  return (
    <div>
      {!file ? (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragOver(true);
          }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={[
            'flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-8 text-center cursor-pointer transition-colors',
            isDragOver ? 'border-blue-500 bg-blue-50' : 'border-slate-300 bg-white hover:bg-slate-50',
          ].join(' ')}
        >
          <svg
            className="w-8 h-8 text-slate-400"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"
            />
          </svg>
          <p className="text-sm font-medium text-slate-700">
            Drag and drop a file here, or click to browse
          </p>
          <p className="text-xs text-slate-500">
            Excel, Word, PDF, CSV, or an image — up to 5MB
          </p>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT_ATTR}
            onChange={handleInputChange}
            className="hidden"
          />
        </div>
      ) : (
        <div className="flex items-center justify-between rounded-xl border border-green-200 bg-green-50 p-4">
          <div className="flex items-center gap-3 min-w-0">
            <svg className="w-6 h-6 text-green-600 shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
            <div className="min-w-0">
              <p className="text-sm font-medium text-slate-800 truncate">{file.name}</p>
              <p className="text-xs text-slate-500">{formatBytes(file.size)} — Uploaded</p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleRemove}
            className="ml-3 text-slate-400 hover:text-red-500 shrink-0"
            aria-label="Remove file"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}
