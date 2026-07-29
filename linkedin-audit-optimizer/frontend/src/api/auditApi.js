export async function submitAudit({ link, content, file }) {
  const formData = new FormData();
  if (link) formData.append('link', link);
  if (content) formData.append('content', content);
  if (file) formData.append('file', file);

  const response = await fetch('/api/audit', {
    method: 'POST',
    body: formData,
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(data?.error || `Audit request failed (${response.status}).`);
  }

  return data;
}
