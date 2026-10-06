/*
 * HR-02 Onboarding + Offboarding Agent — backend.
 * Node (built-in http + node:sqlite, no npm install) serving:
 *   - the UI from ./public
 *   - a REST API backed by a SQLite database (data/hr02.db)
 *   - a Server-Sent-Events stream so every open tab updates in real time
 *   - a background scheduler (chase overdue items, 4h access-revocation escalation)
 * Run: node server.js  ->  http://localhost:3000
 */
const http = require("http");
const fs = require("fs");
const path = require("path");
const { DatabaseSync } = require("node:sqlite");
const Agent = require("./public/agent.js");

const PORT = process.env.PORT || 3000;
const ROOT = path.join(__dirname, "public");
const DATA = process.env.DATA_DIR || path.join(__dirname, "data");
const UPLOADS = path.join(DATA, "uploads");
fs.mkdirSync(UPLOADS, { recursive: true });

const db = new DatabaseSync(path.join(DATA, "hr02.db"));
db.exec(`
  PRAGMA journal_mode = WAL;
  CREATE TABLE IF NOT EXISTS cards (id TEXT PRIMARY KEY, type TEXT, created INTEGER, json TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, card_id TEXT, card_name TEXT, kind TEXT, msg TEXT, important INTEGER, at TEXT);
  CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v INTEGER);
`);

// ---------- data access ----------
const q = {
  allCards: db.prepare("SELECT json FROM cards ORDER BY created"),
  getCard: db.prepare("SELECT json FROM cards WHERE id = ?"),
  putCard: db.prepare("INSERT INTO cards (id, type, created, json) VALUES (?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET json = excluded.json"),
  delCard: db.prepare("DELETE FROM cards WHERE id = ?"),
  addLog: db.prepare("INSERT INTO logs (card_id, card_name, kind, msg, important, at) VALUES (?, ?, ?, ?, ?, ?)"),
  logs: db.prepare("SELECT id, card_id AS cardId, card_name AS card, kind, msg, important, at FROM logs ORDER BY id DESC LIMIT 150"),
  getMeta: db.prepare("SELECT v FROM meta WHERE k = ?"),
  setMeta: db.prepare("INSERT INTO meta (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v"),
};
const loadCard = (id) => {
  const r = q.getCard.get(id);
  return r ? Agent.reviveDates(JSON.parse(r.json)) : null;
};
const saveCard = (c) => q.putCard.run(c.id, c.type, c.created || (c.created = Date.now()), JSON.stringify(c));
function log(card, kind, msg, important = false) {
  q.addLog.run(card.id, card.name, kind, msg, important ? 1 : 0, new Date().toISOString());
}
function nextDisplayId(prefix) {
  const r = q.getMeta.get(prefix);
  const n = (r ? r.v : 100) + 1;
  q.setMeta.run(prefix, n);
  return `${prefix}-${n}`;
}

function insertCard(card) {
  card.id = nextDisplayId(card.type === "onboarding" ? "ONB" : "OFB");
  card.created = Date.now() + db.prepare("SELECT COUNT(*) n FROM cards").get().n; // stable ordering
  const logs = card.logs.splice(0);
  saveCard(card);
  logs.forEach((l) => q.addLog.run(card.id, card.name, l.kind, l.msg, l.important ? 1 : 0, new Date(l.at).toISOString()));
  return card;
}

// ---------- realtime (SSE) ----------
const clients = new Set();
let version = 0;
function broadcast() {
  version++;
  for (const res of clients) res.write(`event: change\ndata: ${version}\n\n`);
}

// ---------- seed ----------
const iso = (d) => d.toISOString().slice(0, 10);
const inDays = (n) => iso(Agent.addDays(new Date(), n));
function seed() {
  db.exec("DELETE FROM cards; DELETE FROM logs; DELETE FROM meta;");
  insertCard(Agent.buildOnboarding({ name: "Priya Sharma", role: "Product Designer", location: "India", department: "Design", employmentType: "Full-time", startDate: inDays(10) }));
  insertCard(Agent.buildOnboarding({ name: "Daniel Okafor", role: "Data Analyst", location: "India", department: "Analytics", employmentType: "Contractor", startDate: inDays(4) }));
  insertCard(Agent.buildOffboarding({ name: "Meera Iyer", role: "Operations Lead", location: "India", department: "Operations", lastWorkingDay: inDays(3) }));
  insertCard(Agent.buildOffboarding({ name: "Arjun Nair", role: "Sales Executive", location: "India", department: "Commercial", lastWorkingDay: inDays(-1), caseRef: "HR-07-2041" }));
}
if (db.prepare("SELECT COUNT(*) n FROM cards").get().n === 0) seed();

const Actions = require("./public/actions.js");
const { actions, need, findItem, tickCard } = Actions.make(log);

// ---------- scheduler: the agent works without anyone clicking ----------
function tick() {
  let changed = false;
  const now = new Date();
  for (const row of q.allCards.all()) {
    const c = Agent.reviveDates(JSON.parse(row.json));
    if (tickCard(c, now)) { saveCard(c); changed = true; }
  }
  if (changed) broadcast();
}
setInterval(() => { try { tick(); } catch (e) { console.error("tick failed", e); } }, 15000);
setTimeout(() => { try { tick(); } catch (e) { console.error(e); } }, 1000);

// ---------- http ----------
const TYPES = { ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "application/javascript; charset=utf-8", ".svg": "image/svg+xml", ".ico": "image/x-icon" };
const json = (res, code, obj) => { res.writeHead(code, { "Content-Type": "application/json" }); res.end(JSON.stringify(obj)); };
const readBody = (req, limit = 15e6) => new Promise((resolve, reject) => {
  const chunks = []; let n = 0;
  req.on("data", (d) => { n += d.length; if (n > limit) { reject(Object.assign(new Error("Payload too large"), { status: 413 })); req.destroy(); } else chunks.push(d); });
  req.on("end", () => resolve(Buffer.concat(chunks)));
  req.on("error", reject);
});
const readJson = async (req) => { const b = await readBody(req); try { return b.length ? JSON.parse(b) : {}; } catch { throw Object.assign(new Error("Invalid JSON"), { status: 400 }); } };

async function api(req, res, url) {
  const m = req.method;
  if (m === "GET" && url === "/api/state") {
    return json(res, 200, { cards: q.allCards.all().map((r) => JSON.parse(r.json)), logs: q.logs.all().map((l) => ({ ...l, important: !!l.important })), version });
  }
  if (m === "GET" && url === "/api/stream") {
    res.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-cache", Connection: "keep-alive" });
    res.write(`event: hello\ndata: ${version}\n\n`);
    clients.add(res);
    const ka = setInterval(() => res.write(": keepalive\n\n"), 25000);
    req.on("close", () => { clearInterval(ka); clients.delete(res); });
    return;
  }
  if (m === "POST" && url === "/api/events") {
    const b = await readJson(req);
    need(b.name && String(b.name).trim(), "Employee name is required");
    let card;
    if (b.mode === "offboarding") {
      need(b.lastWorkingDay, "Last working day is required");
      card = Agent.buildOffboarding({ ...b, caseRef: b.caseRef || null });
    } else {
      need(b.startDate, "Start date is required");
      card = Agent.buildOnboarding(b);
    }
    insertCard(card); broadcast();
    return json(res, 201, { id: card.id });
  }
  if (m === "POST" && url === "/api/reset") { seed(); broadcast(); return json(res, 200, { ok: true }); }

  let mm = url.match(/^\/api\/cards\/([\w-]+)\/upload\/([\w-]+)$/); // raw file body
  if (m === "POST" && mm) {
    const c = loadCard(mm[1]); need(c, "Card not found");
    const it = findItem(c, mm[2]); need(it, "Item not found");
    const buf = await readBody(req);
    need(buf.length > 0, "Empty file");
    const fileName = decodeURIComponent(req.headers["x-filename"] || "upload.bin");
    const stored = `${c.id}_${it.id}_${Date.now()}_${path.basename(fileName).replace(/[^\w.\-]/g, "_")}`;
    fs.writeFileSync(path.join(UPLOADS, stored), buf);
    actions.upload(c, it, { quality: req.headers["x-validation"] || "valid", fileName, fileSize: buf.length, stored });
    saveCard(c); broadcast();
    return json(res, 200, { status: it.doc.status, message: it.doc.message });
  }
  mm = url.match(/^\/api\/cards\/([\w-]+)\/action$/);
  if (m === "POST" && mm) {
    const c = loadCard(mm[1]); need(c, "Card not found");
    const b = await readJson(req);
    need(actions[b.action], "Unknown action");
    actions[b.action](c, b.itemId ? findItem(c, b.itemId) : null, b);
    saveCard(c); broadcast();
    return json(res, 200, { ok: true });
  }
  mm = url.match(/^\/api\/cards\/([\w-]+)$/);
  if (m === "DELETE" && mm) {
    need(loadCard(mm[1]), "Card not found");
    q.delCard.run(mm[1]); broadcast();
    return json(res, 200, { ok: true });
  }
  json(res, 404, { error: "Not found" });
}

const server = http.createServer(async (req, res) => {
  const url = req.url.split("?")[0];
  if (url.startsWith("/api/")) {
    try { await api(req, res, url); }
    catch (e) { if (!res.headersSent) json(res, e.status || 500, { error: e.message }); else res.end(); if (!e.status) console.error(e); }
    return;
  }
  let p = decodeURIComponent(url);
  if (p === "/") p = "/index.html";
  const filePath = path.join(ROOT, path.normalize(p));
  if (!filePath.startsWith(ROOT)) { res.writeHead(403); return res.end("Forbidden"); }
  fs.readFile(filePath, (err, data) => {
    if (err) { res.writeHead(404, { "Content-Type": "text/plain" }); return res.end("Not found"); }
    res.writeHead(200, { "Content-Type": TYPES[path.extname(filePath).toLowerCase()] || "application/octet-stream", "Cache-Control": "no-cache" });
    res.end(data);
  });
});
server.listen(PORT, () => {
  console.log(`\n  HR-02 Lifecycle Agent (backend + SQLite)\n\n    ➜  http://localhost:${PORT}\n    database: ${path.join(DATA, "hr02.db")}\n`);
});
