/* Backend for the localhost Node server: REST + Server-Sent Events. */
const Backend = (() => {
  async function req(method, url, body, headers = {}) {
    const raw = body instanceof Blob;
    const res = await fetch(url, { method, headers: raw ? headers : { "Content-Type": "application/json", ...headers }, body: body == null ? undefined : raw ? body : JSON.stringify(body) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
    return data;
  }
  return {
    subscribe(onData, onLive) {
      const load = async () => onData(await (await fetch("/api/state")).json());
      const es = new EventSource("/api/stream");
      es.addEventListener("hello", () => { onLive(true); load(); });
      es.addEventListener("change", load);
      es.onerror = () => onLive(false);
      load().catch(() => onLive(false));
    },
    action: (id, payload) => req("POST", `/api/cards/${id}/action`, payload),
    upload: (id, itemId, file, quality) => req("POST", `/api/cards/${id}/upload/${itemId}`, file, { "x-filename": encodeURIComponent(file.name), "x-validation": quality }),
    createEvent: (mode, data) => req("POST", "/api/events", { mode, ...data }),
    remove: (id) => req("DELETE", `/api/cards/${id}`),
    reset: () => req("POST", "/api/reset"),
  };
})();
