/*
 * Backend for the hosted artifact: the claude.ai artifact database (capability `db`).
 * One document per lifecycle event in `cards/<id>`; the agent's activity log lives inside each card.
 * Every viewer subscribes with onSnapshot, so a change made anywhere appears everywhere in real time.
 */
const Backend = (() => {
  let db = null, assets = null, user = null;
  const cardsCol = () => db.collection("cards");
  const LOG_KEEP = 60;

  // Agent log() -> appended to the card's own history
  const log = (card, kind, msg, important = false) => {
    (card.logs || (card.logs = [])).push({ kind, msg, important: !!important, at: new Date().toISOString(), card: card.name, cardId: card.id });
    if (card.logs.length > LOG_KEEP) card.logs.splice(0, card.logs.length - LOG_KEEP);
  };
  const { actions, need, findItem, tickCard } = Actions.make(log);

  const write = (c) => cardsCol().doc(c.id).set({ type: c.type, created: c.created, json: JSON.stringify(c) });
  async function load(id) {
    const snap = await cardsCol().doc(id).get();
    need(snap.exists, "That event no longer exists");
    return Agent.reviveDates(JSON.parse(snap.data().json));
  }
  const iso = (d) => d.toISOString().slice(0, 10);
  const inDays = (n) => iso(Agent.addDays(new Date(), n));

  async function seed() {
    const specs = [
      ["ONB-101", () => Agent.buildOnboarding({ name: "Priya Sharma", role: "Product Designer", location: "India", department: "Design", employmentType: "Full-time", startDate: inDays(10) })],
      ["ONB-102", () => Agent.buildOnboarding({ name: "Daniel Okafor", role: "Data Analyst", location: "India", department: "Analytics", employmentType: "Contractor", startDate: inDays(4) })],
      ["OFB-101", () => Agent.buildOffboarding({ name: "Meera Iyer", role: "Operations Lead", location: "India", department: "Operations", lastWorkingDay: inDays(3) })],
      ["OFB-102", () => Agent.buildOffboarding({ name: "Arjun Nair", role: "Sales Executive", location: "India", department: "Commercial", lastWorkingDay: inDays(-1), caseRef: "HR-07-2041" })],
    ];
    let n = 0;
    for (const [id, build] of specs) {
      const c = build();
      c.id = id; c.created = Date.now() + n++;
      c.logs = c.logs.map((l) => ({ ...l, at: new Date(l.at).toISOString(), card: c.name, cardId: id }));
      await write(c);
    }
  }
  async function wipe() {
    const snap = await cardsCol().get();
    for (const d of snap.docs) await cardsCol().doc(d.id).delete();
  }

  return {
    async subscribe(onData, onLive) {
      db = await claude.use("db");
      assets = await claude.use("assets");
      user = await claude.use("user");
      if (!db) { onLive(false); onData({ cards: [], logs: [] }); document.title = "HR-02 Lifecycle Agent"; showNoDb(); return; }
      let cache = [];
      let seeded = false;
      const isOwner = !!(user && user.isOwner && user.isOwner());

      cardsCol().orderBy("created").onSnapshot((snap) => {
        cache = snap.docs.map((d) => JSON.parse(d.data().json));
        const logs = cache.flatMap((c) => c.logs || []).sort((a, b) => (a.at < b.at ? 1 : -1)).slice(0, 150);
        onLive(true);
        onData({ cards: cache, logs });
        // first ever open: the owner's view fills the empty database with sample events (one winner via a lease)
        if (!seeded && snap.empty && !snap.metadata.fromCache && isOwner) {
          seeded = true;
          db.doc("meta/seed").acquire({ holder: "owner", ttlMs: 20000 }).then((r) => { if (r.acquired) return seed(); }).catch(() => {});
        }
      }, () => onLive(false));

      // the agent's background duties (chase overdue, 4h access-revocation escalation) run in the owner's open page
      if (isOwner) setInterval(async () => {
        for (const raw of cache.slice()) {
          const c = Agent.reviveDates(JSON.parse(JSON.stringify(raw)));
          if (tickCard(c, new Date())) { try { await write(c); } catch {} }
        }
      }, 15000);
    },
    async action(id, payload) {
      const c = await load(id);
      need(actions[payload.action], "Unknown action");
      actions[payload.action](c, payload.itemId ? findItem(c, payload.itemId) : null, payload);
      await write(c);
    },
    async upload(id, itemId, file, quality) {
      const c = await load(id);
      const it = findItem(c, itemId); need(it, "Item not found");
      let stored = null;
      if (assets) { try { stored = (await assets.upload(file)).id; } catch { /* keep the validation result even if the file can't be stored */ } }
      actions.upload(c, it, { quality, fileName: file.name, fileSize: file.size, stored });
      await write(c);
      return { status: it.doc.status, message: it.doc.message };
    },
    async createEvent(mode, data) {
      need(String(data.name || "").trim(), "Employee name is required");
      let c;
      if (mode === "offboarding") { need(data.lastWorkingDay, "Last working day is required"); c = Agent.buildOffboarding({ ...data, caseRef: data.caseRef || null }); }
      else { need(data.startDate, "Start date is required"); c = Agent.buildOnboarding(data); }
      c.id = `${mode === "offboarding" ? "OFB" : "ONB"}-${Math.floor(Date.now() / 1000) % 100000}`;
      c.created = Date.now();
      c.logs = c.logs.map((l) => ({ ...l, at: new Date(l.at).toISOString(), card: c.name, cardId: c.id }));
      await write(c);
      return { id: c.id };
    },
    async remove(id) { await cardsCol().doc(id).delete(); },
    async reset() { await wipe(); await seed(); },
  };

  function showNoDb() {
    const t = document.getElementById("toasts");
    if (t) t.innerHTML = '<div class="toast bad">The database is not available in this view. Open the artifact while signed in.</div>';
  }
})();
