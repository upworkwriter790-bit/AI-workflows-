/* HR-02 Lifecycle Agent — UI. State lives in the backend (SQLite); this renders it and sends actions. */
(() => {
  let cards = [];
  let logs = [];
  let openCardId = null;
  let modalMode = "onboarding";
  let connected = false;
  let pendingOpen = null;

  const $ = (s, r = document) => r.querySelector(s);
  const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // ---------- backend (HTTP server on localhost, or the artifact database when hosted) ----------
  const call = async (fn) => { try { return await fn(); } catch (e) { toast(e.message || "Something went wrong", true); throw e; } };
  const act = (cardId, payload) => call(() => Backend.action(cardId, payload)).catch(() => {});
  function onData(d) {
    cards = d.cards.map((c) => Agent.reviveDates(c));
    logs = d.logs.map((l) => ({ ...l, at: new Date(l.at) }));
    renderAll();
  }
  function setLive(on) {
    connected = on;
    const b = $("#liveBadge");
    b.textContent = on ? "● Live · saved to database" : "● Reconnecting…";
    b.className = "live " + (on ? "on" : "off");
  }
  function toast(msg, bad) {
    const t = el("div", "toast" + (bad ? " bad" : ""), esc(msg));
    $("#toasts").appendChild(t);
    setTimeout(() => t.remove(), 3500);
  }

  // ---------- ring ----------
  function ring(pct, color) {
    const r = 17, c = 2 * Math.PI * r, off = c * (1 - pct / 100);
    return `<svg class="ring" width="44" height="44" viewBox="0 0 44 44">
      <circle cx="22" cy="22" r="${r}" fill="none" stroke="#2a3340" stroke-width="4"/>
      <circle cx="22" cy="22" r="${r}" fill="none" stroke="${color}" stroke-width="4" stroke-linecap="round" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${off.toFixed(1)}" transform="rotate(-90 22 22)"/>
      <text x="22" y="26" text-anchor="middle" font-size="11" font-weight="700" fill="#e8edf3">${pct}%</text></svg>`;
  }

  // ---------- board ----------
  function renderAll() {
    renderColumn("onboarding", "cards-joining", "count-joining");
    renderColumn("offboarding", "cards-exiting", "count-exiting");
    renderLog();
    if (openCardId) renderDrawer(openCardId);
  }
  let lastDrawerSig = "";
  function renderColumn(type, listId, countId) {
    const list = $("#" + listId);
    const subset = cards.filter((c) => c.type === type);
    $("#" + countId).textContent = subset.length;
    list.innerHTML = "";
    if (!subset.length) { list.appendChild(el("div", "empty-col", "No active events. Click <b>+ New lifecycle event</b> to trigger the agent.")); return; }
    subset.forEach((c) => list.appendChild(cardEl(c)));
  }
  function cardEl(c) {
    const comp = Agent.completion(c);
    const dtd = Agent.daysBetween(c.anchor, new Date());
    const overdue = Agent.overdueItems(c);
    const clearance = c.type === "offboarding" ? Agent.clearanceState(c) : null;
    const blocked = clearance && !clearance.allClear;
    const flagged = c.classification && c.classification.status === "amber";
    const color = blocked ? "#ff5d5d" : comp.pct === 100 ? "#35c66b" : "#4f8cff";
    const card = el("div", "card" + (blocked ? " has-block" : ""));
    const dtdLabel = dtd === 0 ? `${c.anchorLabel}: today` : dtd > 0 ? `${c.anchorLabel} in ${dtd}d` : `${c.anchorLabel} ${-dtd}d ago`;
    card.innerHTML = `
      <div class="card-top">${ring(comp.pct, color)}<div>
        <div class="card-id">${c.id}${c.caseRef ? " · " + esc(c.caseRef) : ""}</div>
        <div class="card-name">${esc(c.name)}</div>
        <div class="card-sub">${esc(c.role)} · ${esc(c.department)} · ${esc(c.location)}</div></div></div>
      <div class="card-meta"><span class="tag">${esc(c.employmentType)}</span>
        <span class="tag days ${overdue.length ? "overdue" : ""}">${dtdLabel}</span>
        <span class="tag">${comp.done}/${comp.total} items</span>
        ${overdue.length ? `<span class="tag days overdue">${overdue.length} overdue</span>` : ""}</div>
      ${c.classification ? classifStrip(c.classification) : ""}
      ${blocked ? `<div class="banner block">🔒 Final settlement blocked — ${clearance.outstanding.length} clearance(s) outstanding</div>` : ""}
      ${flagged ? `<div class="banner flag">⚠ Classification contradiction raised — awaiting legal counsel</div>` : ""}`;
    card.addEventListener("click", () => openDrawer(c.id));
    return card;
  }
  function classifStrip(cl) {
    return cl.status === "green"
      ? `<div class="classif green"><span class="cl-dot"></span> Classification: contract matches observed pattern</div>`
      : `<div class="classif amber"><span class="cl-dot"></span> Classification: ${cl.contradictions.length} signals contradict “${esc(cl.contracted)}”</div>`;
  }

  // ---------- drawer ----------
  function openDrawer(id) {
    openCardId = id; lastDrawerSig = ""; renderDrawer(id);
    $("#drawer").classList.add("open"); $("#scrim").classList.add("open"); $("#drawer").setAttribute("aria-hidden", "false");
  }
  function closeDrawer() {
    openCardId = null;
    $("#drawer").classList.remove("open"); $("#scrim").classList.remove("open"); $("#drawer").setAttribute("aria-hidden", "true");
  }
  function renderDrawer(id) {
    const c = cards.find((x) => x.id === id);
    if (!c) { if (pendingOpen === id) return; return closeDrawer(); }
    pendingOpen = null;
    const d = $("#drawer");
    const sig = JSON.stringify(c);
    if (sig === lastDrawerSig && d.dataset.id === id) return; // nothing changed: leave inputs alone
    lastDrawerSig = sig; d.dataset.id = id;
    // keep what the user is typing / has selected across live re-renders
    const keep = {};
    d.querySelectorAll("[data-keep]:not([type=file])").forEach((n) => { keep[n.dataset.keep] = n.value; });
    const keepFiles = {};
    d.querySelectorAll('input[type=file][data-keep]').forEach((n) => { if (n.files[0]) keepFiles[n.dataset.keep] = n.files[0]; });
    const focusKey = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.keep : null;
    const scroll = d.scrollTop;
    const comp = Agent.completion(c);
    let html = `
      <div class="drawer-head"><div class="dh-top"><div>
        <div class="card-id">${c.id}${c.caseRef ? " · from HR-07 " + esc(c.caseRef) : ""} · ${c.type === "onboarding" ? "Joining" : "Exiting"}</div>
        <h2>${esc(c.name)}</h2>
        <div class="card-sub">${esc(c.role)} · ${esc(c.department)} · ${esc(c.location)} · ${esc(c.employmentType)}</div></div>
        <button class="icon-btn" id="drawerClose">✕</button></div>
        <div class="card-meta" style="margin-top:12px">
          <span class="tag days">${c.anchorLabel}: ${Agent.fmtDate(c.anchor)}</span>
          <span class="tag">${comp.done}/${comp.total} complete (${comp.pct}%)</span>
          <button class="btn btn-sm btn-ghost danger" data-delete="${c.id}">Delete event</button></div></div>
      <div class="drawer-body">`;
    if (c.classification) html += classifSection(c);
    if (c.type === "offboarding") html += clearanceSection(c);
    html += `<div class="section"><div class="section-title">Checklist · grouped by owner</div>`;
    c.groups.forEach((g) => {
      const gdone = g.items.filter((i) => i.state === "done").length;
      html += `<div class="owner-group"><div class="owner-head">${ownerIcon(g.owner)} ${g.owner}<span class="ochip">${gdone}/${g.items.length}</span></div>`;
      g.items.forEach((it) => (html += itemEl(c, it)));
      html += `</div>`;
    });
    html += `</div></div>`;
    d.innerHTML = html;
    d.querySelectorAll("[data-keep]:not([type=file])").forEach((n) => { if (keep[n.dataset.keep] !== undefined) n.value = keep[n.dataset.keep]; });
    Object.entries(keepFiles).forEach(([k, f]) => {
      const n = d.querySelector(`input[type=file][data-keep="${k}"]`);
      if (n) { const dt = new DataTransfer(); dt.items.add(f); n.files = dt.files; }
    });
    if (focusKey) { const n = d.querySelector(`[data-keep="${focusKey}"]`); if (n) n.focus(); }
    d.scrollTop = scroll;
    $("#drawerClose").addEventListener("click", closeDrawer);
    wireDrawer(c, d);
  }
  function classifSection(c) {
    const cl = c.classification, amber = cl.status === "amber";
    const rows = Object.entries(cl.observed).map(([k, v]) => `<div class="cl-row"><span class="k">${k}</span><span class="v ${v.contradicts ? "bad" : "ok"}">${esc(v.value)}${v.contradicts ? " ⚠" : " ✓"}</span></div>`).join("");
    return `<div class="section"><div class="section-title">Worker classification check <span class="badge ${amber ? "escalated" : "valid"}">${amber ? "contradiction" : "consistent"}</span></div>
      <div class="cl-card"><div class="cl-row"><span class="k">Contracted as</span><span class="v">${esc(cl.contracted)}</span></div>${rows}
      <div class="mini-note" style="margin-top:12px">${amber ? `Raised and stopped on ${cl.contradictions.length} concurring signals. The agent never reclassifies and never alters a contract — ${esc(cl.determination)}` : `Contracted type is consistent with the observed working pattern.`}</div></div></div>`;
  }
  function clearanceSection(c) {
    const cs = Agent.clearanceState(c);
    const rows = cs.items.map((it) => `<div class="cl-dept"><span>${esc(it.label)}</span><span class="badge ${it.state === "done" ? "valid" : "pending"}">${it.state === "done" ? "cleared" : "outstanding"}</span></div>`).join("");
    const banner = cs.allClear
      ? `<div class="banner" style="background:var(--green-bg);color:#8fe3ac;border:1px solid #1c5234">✓ All clearances green — final settlement unlocked</div>`
      : `<div class="banner block">🔒 Final settlement hard-locked — ${cs.outstanding.length} clearance(s) outstanding (blocked, not warned)</div>`;
    return `<div class="section"><div class="section-title">Exit clearance aggregation</div>${banner}<div class="clearance" style="margin-top:10px">${rows}</div></div>`;
  }
  function itemEl(c, it) {
    const overdue = it.state !== "done" && it.state !== "locked" && it.due < new Date();
    const stateClass = it.state === "done" ? "done" : it.state === "locked" ? "locked" : "";
    let sub = "";
    if (it.kind === "document") {
      const s = it.doc.status;
      const badge = s === "valid" ? `<span class="badge valid">valid</span>` : s === "invalid" ? `<span class="badge invalid">rejected</span>` : s === "escalated" ? `<span class="badge escalated">escalated to HR</span>` : `<span class="badge pending">awaiting upload</span>`;
      sub = `<div class="item-sub">${badge} ${esc(it.doc.message)}${it.doc.failures ? ` · ${it.doc.failures}/3 attempts` : ""}${it.doc.file ? `<br>📎 ${esc(it.doc.file.name)} (${Math.max(1, Math.round(it.doc.file.size / 1024))} KB, saved)` : ""}</div>`;
    } else if (it.kind === "ticket" && it.ticket) {
      const t = it.ticket, st = t.confirmed ? "confirmed" : t.escalated ? "ESCALATED — security incident" : "raised, awaiting confirmation";
      sub = `<div class="item-sub ${t.escalated && !t.confirmed ? "overdue" : ""}">${esc(t.system)} · ${st}${t.effectiveAt ? " · effective " + Agent.fmtDateTime(t.effectiveAt) : ""}</div>`;
    } else if (it.kind === "settlement" && it.state === "locked") sub = `<div class="item-sub locked">Hard-locked until all clearances are green</div>`;
    else if (it.kind === "checkin") sub = `<div class="item-sub ${overdue ? "overdue" : ""}">Due ${Agent.fmtDate(it.due)}${it.checkin.held ? " · held" : overdue ? " · not held — manager chased" : ""}</div>`;
    else if (it.kind === "interview") sub = `<div class="item-sub">Interviewer: ${esc(it.interview.interviewer)} · ${it.interview.done ? "completed (stored in restricted store)" : "scheduled"}</div>`;
    else if (it.kind === "goal") sub = `<div class="item-sub">${it.goal.recorded ? "Recorded: " + esc(it.goal.text) : "Required before checklist can complete"}</div>`;
    else sub = `<div class="item-sub ${overdue ? "overdue" : ""}">Due ${Agent.fmtDate(it.due)}${it.state === "done" ? " · done" : overdue ? " · overdue" : ""}</div>`;

    let actions = "";
    if (it.state !== "done") {
      if (it.kind === "document" && it.doc.status !== "escalated") {
        actions = `<div class="doc-sim"><input type="file" class="sim file" data-keep="file-${it.id}" data-file="${it.id}" accept="image/*,.pdf">
          <select class="sim" data-keep="q-${it.id}" data-q="${it.id}" title="Demo only: no AI key is connected, so choose what the validator should find">
            <option value="valid">Validator finds: valid</option><option value="wrong_type">Validator finds: wrong type</option><option value="illegible">Validator finds: illegible</option><option value="name_mismatch">Validator finds: name mismatch</option><option value="expired">Validator finds: expired</option></select>
          <button class="btn btn-sm" data-upload="${it.id}">Upload &amp; validate</button></div>`;
      } else if (it.kind === "document") {
        actions = `<button class="btn btn-sm" data-act="hrResolve" data-item="${it.id}">HR: accept manually</button>`;
      } else if (it.kind === "ticket" && it.ticket && !it.ticket.confirmed) {
        actions = `<button class="btn btn-sm" data-act="confirmTicket" data-item="${it.id}">IT confirms done</button>`;
        if (it.ticket.effectiveAt && !it.ticket.escalated) actions += ` <button class="btn btn-sm btn-ghost" data-act="simulateEscalation" data-item="${it.id}">Simulate 4h, no confirmation</button>`;
      } else if (it.kind === "settlement") {
        actions = Agent.clearanceState(c).allClear ? `<button class="btn btn-sm" data-act="complete" data-item="${it.id}">Release settlement</button>` : `<span class="hint">Unlocks when clearances are green</span>`;
      } else if (it.kind === "checkin") actions = `<button class="btn btn-sm" data-act="complete" data-item="${it.id}">Mark held</button>`;
      else if (it.kind === "interview") actions = `<button class="btn btn-sm" data-act="complete" data-item="${it.id}">Record response</button>`;
      else if (it.kind === "goal") actions = `<div class="doc-sim"><input class="sim" style="flex:1;min-width:140px" placeholder="e.g. Ship onboarding flow by day 30" data-keep="g-${it.id}" data-goal="${it.id}"><button class="btn btn-sm" data-act="complete" data-item="${it.id}" data-needs-goal="${it.id}">Record goal</button></div>`;
      else actions = `<button class="btn btn-sm" data-act="complete" data-item="${it.id}">Mark complete</button>`;
      if (overdue && it.kind !== "settlement") actions += ` <button class="btn btn-sm btn-ghost" data-act="chase" data-item="${it.id}">Chase now</button>`;
    } else if (it.kind !== "settlement") {
      actions = `<button class="btn btn-sm btn-ghost" data-act="reopen" data-item="${it.id}">Reopen</button>`;
    }
    return `<div class="item"><div class="state"><span class="sdot ${stateClass}"></span></div><div class="item-main"><div class="item-label">${esc(it.label)}</div>${sub}${actions ? `<div class="item-actions">${actions}</div>` : ""}</div></div>`;
  }

  function wireDrawer(c, d) {
    d.querySelectorAll("[data-act]").forEach((b) => b.addEventListener("click", async () => {
      const payload = { action: b.dataset.act, itemId: b.dataset.item };
      if (b.dataset.needsGoal) {
        const inp = d.querySelector(`[data-goal="${b.dataset.needsGoal}"]`);
        payload.text = (inp.value || "").trim();
        if (!payload.text) { inp.focus(); toast("Enter a measurable 30-day goal first", true); return; }
      }
      b.disabled = true;
      await act(c.id, payload);
      b.disabled = false;
    }));
    d.querySelectorAll("[data-upload]").forEach((b) => b.addEventListener("click", async () => {
      const id = b.dataset.upload;
      const file = d.querySelector(`[data-file="${id}"]`).files[0];
      const quality = d.querySelector(`[data-q="${id}"]`).value;
      if (!file) { toast("Choose a file to upload first", true); return; }
      b.disabled = true; b.textContent = "Uploading…";
      try {
        const r = await call(() => Backend.upload(c.id, id, file, quality));
        toast(r.message, r.status !== "valid");
      } catch {} finally { b.disabled = false; }
    }));
    d.querySelectorAll("[data-delete]").forEach((b) => b.addEventListener("click", async () => {
      if (b.dataset.confirm !== "1") { b.dataset.confirm = "1"; b.textContent = "Click again to confirm delete"; setTimeout(() => { b.dataset.confirm = ""; b.textContent = "Delete event"; }, 3000); return; }
      await call(() => Backend.remove(b.dataset.delete)).catch(() => {});
      closeDrawer(); toast("Event deleted");
    }));
  }

  // ---------- agent log ----------
  function renderLog() {
    const box = $("#agentLog"); box.innerHTML = "";
    if (!logs.length) { box.appendChild(el("div", "hint", "No activity yet.")); return; }
    logs.forEach((en) => {
      const t = en.at.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
      const item = el("div", "log-item k-" + en.kind);
      item.innerHTML = `<div class="lt"><span class="log-badge">${en.kind}</span>${t} · ${esc(en.card)}</div><div class="lm">${esc(en.msg)}</div>`;
      box.appendChild(item);
    });
  }

  // ---------- modal ----------
  const iso = (d) => d.toISOString().slice(0, 10);
  const inDays = (n) => iso(Agent.addDays(new Date(), n));
  function openModal() { $("#modalScrim").classList.add("open"); renderForm(); }
  function closeModal() { $("#modalScrim").classList.remove("open"); }
  function renderForm() {
    const f = $("#eventForm");
    const loc = `<select name="location"><option>India</option><option>United Kingdom</option><option>United States</option></select>`;
    f.innerHTML = modalMode === "onboarding" ? `
      <div class="field"><label>Employee name</label><input name="name" placeholder="e.g. Ananya Rao" required></div>
      <div class="field-row"><div class="field"><label>Role</label><input name="role" value="Backend Engineer" required></div>
        <div class="field"><label>Department</label><input name="department" value="Engineering" required></div></div>
      <div class="field-row"><div class="field"><label>Location</label>${loc}</div>
        <div class="field"><label>Employment type</label><select name="employmentType"><option>Full-time</option><option>Contractor</option><option>Intern</option></select></div></div>
      <div class="field"><label>Start date</label><input type="date" name="startDate" value="${inDays(14)}" required></div>
      <p class="hint">Pick <b>Contractor</b> to see the worker-classification check fire at contract issue.</p>` : `
      <div class="field"><label>Employee name</label><input name="name" placeholder="e.g. Rohit Menon" required></div>
      <div class="field-row"><div class="field"><label>Role</label><input name="role" value="Account Manager" required></div>
        <div class="field"><label>Department</label><input name="department" value="Commercial" required></div></div>
      <div class="field-row"><div class="field"><label>Location</label>${loc}</div>
        <div class="field"><label>Last working day</label><input type="date" name="lastWorkingDay" value="${inDays(7)}" required></div></div>
      <div class="field"><label>HR-07 case reference (optional — involuntary / disciplinary exits)</label><input name="caseRef" placeholder="e.g. HR-07-2041"></div>
      <p class="hint">Leave case reference blank for a standard resignation.</p>`;
  }
  async function submitForm() {
    const data = Object.fromEntries(new FormData($("#eventForm")).entries());
    if (!String(data.name || "").trim()) { toast("Employee name is required", true); return; }
    try {
      const r = await call(() => Backend.createEvent(modalMode, data));
      closeModal(); pendingOpen = r.id; openDrawer(r.id); toast("Agent assembled the checklist");
    } catch {}
  }
  function ownerIcon(o) { return `<span>${{ Employee: "👤", IT: "💻", Payroll: "💰", Facilities: "🏢", Manager: "🧭", HR: "📋" }[o] || "•"}</span>`; }

  // ---------- wire ----------
  $("#btnNew").addEventListener("click", openModal);
  $("#btnReset").addEventListener("click", async () => {
    const b = $("#btnReset");
    if (b.dataset.confirm !== "1") { b.dataset.confirm = "1"; b.textContent = "Click again to wipe data"; setTimeout(() => { b.dataset.confirm = ""; b.textContent = "Reset demo data"; }, 3000); return; }
    b.dataset.confirm = ""; b.textContent = "Reset demo data";
    await call(() => Backend.reset()).catch(() => {}); closeDrawer(); toast("Database reset to sample data");
  });
  $("#modalClose").addEventListener("click", closeModal);
  $("#modalCancel").addEventListener("click", closeModal);
  $("#modalSubmit").addEventListener("click", submitForm);
  $("#scrim").addEventListener("click", closeDrawer);
  $("#modalScrim").addEventListener("click", (e) => { if (e.target.id === "modalScrim") closeModal(); });
  document.querySelectorAll(".mtab").forEach((t) => t.addEventListener("click", () => {
    document.querySelectorAll(".mtab").forEach((x) => x.classList.remove("active"));
    t.classList.add("active"); modalMode = t.dataset.mode;
    $("#modalTitle").textContent = modalMode === "onboarding" ? "New joiner" : "New leaver";
    renderForm();
  }));
  setInterval(() => { if (document.visibilityState === "visible") renderColumn("onboarding", "cards-joining", "count-joining"), renderColumn("offboarding", "cards-exiting", "count-exiting"); }, 60000);
  Backend.subscribe(onData, setLive);
})();
