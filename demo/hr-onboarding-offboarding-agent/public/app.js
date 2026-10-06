/* HR-02 Lifecycle Agent — UI controller */
(() => {
  let cards = [];
  let globalLog = [];
  let openCardId = null;
  let modalMode = "onboarding";

  const $ = (s, r = document) => r.querySelector(s);
  const el = (tag, cls, html) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  };

  // ---------- logging ----------
  function pushLogs(card, entries) {
    entries.forEach((en) => globalLog.unshift({ ...en, card: card.name, cardId: card.id }));
    renderLog();
  }
  function agentDo(card, kind, msg, important = false) {
    pushLogs(card, [Agent.logEntry(kind, msg, important)]);
  }

  // ---------- state ----------
  function addCard(card) {
    cards.push(card);
    const entries = card.logs.splice(0);
    entries.reverse().forEach((en) => globalLog.unshift({ ...en, card: card.name, cardId: card.id }));
    renderAll();
  }

  // ---------- SVG ring ----------
  function ring(pct, color) {
    const r = 17, c = 2 * Math.PI * r;
    const off = c * (1 - pct / 100);
    return `<svg class="ring" width="44" height="44" viewBox="0 0 44 44">
      <circle cx="22" cy="22" r="${r}" fill="none" stroke="#2a3340" stroke-width="4"/>
      <circle cx="22" cy="22" r="${r}" fill="none" stroke="${color}" stroke-width="4"
        stroke-linecap="round" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${off.toFixed(1)}"
        transform="rotate(-90 22 22)"/>
      <text x="22" y="26" text-anchor="middle" font-size="11" font-weight="700" fill="#e8edf3">${pct}%</text>
    </svg>`;
  }

  // ---------- board ----------
  function renderAll() {
    renderColumn("onboarding", "cards-joining", "count-joining");
    renderColumn("offboarding", "cards-exiting", "count-exiting");
    if (openCardId) renderDrawer(openCardId);
  }

  function renderColumn(type, listId, countId) {
    const list = $("#" + listId);
    const subset = cards.filter((c) => c.type === type);
    $("#" + countId).textContent = subset.length;
    list.innerHTML = "";
    if (!subset.length) {
      list.appendChild(el("div", "empty-col", "No active events. Click <b>+ New lifecycle event</b> to trigger the agent."));
      return;
    }
    subset.forEach((c) => list.appendChild(cardEl(c)));
  }

  function cardEl(c) {
    const comp = Agent.completion(c);
    const now = new Date();
    const dtd = Agent.daysBetween(c.anchor, now);
    const overdue = Agent.overdueItems(c);
    const clearance = c.type === "offboarding" ? Agent.clearanceState(c) : null;
    const blocked = clearance && !clearance.allClear;
    const flagged = c.classification && c.classification.status === "amber";

    let color = "#4f8cff";
    if (comp.pct === 100) color = "#35c66b";
    if (blocked) color = "#ff5d5d";

    const card = el("div", "card" + (blocked ? " has-block" : ""));
    card.dataset.id = c.id;

    const dtdLabel =
      dtd === 0 ? `${c.anchorLabel}: today`
      : dtd > 0 ? `${c.anchorLabel} in ${dtd}d`
      : `${c.anchorLabel} ${-dtd}d ago`;
    const dtdOverdue = overdue.length > 0;

    card.innerHTML = `
      <div class="card-top">
        ${ring(comp.pct, color)}
        <div>
          <div class="card-id">${c.id}${c.caseRef ? " · " + c.caseRef : ""}</div>
          <div class="card-name">${esc(c.name)}</div>
          <div class="card-sub">${esc(c.role)} · ${esc(c.department)} · ${esc(c.location)}</div>
        </div>
      </div>
      <div class="card-meta">
        <span class="tag">${esc(c.employmentType)}</span>
        <span class="tag days ${dtdOverdue ? "overdue" : ""}">${dtdLabel}</span>
        <span class="tag">${comp.done}/${comp.total} items</span>
        ${overdue.length ? `<span class="tag days overdue">${overdue.length} overdue</span>` : ""}
      </div>
      ${c.classification ? classifStrip(c.classification) : ""}
      ${blocked ? `<div class="banner block">🔒 Final settlement blocked — ${clearance.outstanding.length} clearance(s) outstanding</div>` : ""}
      ${flagged ? `<div class="banner flag">⚠ Classification contradiction raised — awaiting legal counsel</div>` : ""}
    `;
    card.addEventListener("click", () => openDrawer(c.id));
    return card;
  }

  function classifStrip(cl) {
    if (cl.status === "green")
      return `<div class="classif green"><span class="cl-dot"></span> Classification: contract matches observed pattern</div>`;
    return `<div class="classif amber"><span class="cl-dot"></span> Classification: ${cl.contradictions.length} signals contradict “${esc(cl.contracted)}”</div>`;
  }

  // ---------- drawer ----------
  function openDrawer(id) {
    openCardId = id;
    renderDrawer(id);
    $("#drawer").classList.add("open");
    $("#scrim").classList.add("open");
    $("#drawer").setAttribute("aria-hidden", "false");
  }
  function closeDrawer() {
    openCardId = null;
    $("#drawer").classList.remove("open");
    $("#scrim").classList.remove("open");
    $("#drawer").setAttribute("aria-hidden", "true");
  }

  function renderDrawer(id) {
    const c = cards.find((x) => x.id === id);
    if (!c) return closeDrawer();
    const comp = Agent.completion(c);
    const d = $("#drawer");
    const now = new Date();
    const dtd = Agent.daysBetween(c.anchor, now);

    let html = `
      <div class="drawer-head">
        <div class="dh-top">
          <div>
            <div class="card-id">${c.id}${c.caseRef ? " · from HR-07 " + c.caseRef : ""} · ${c.type === "onboarding" ? "Joining" : "Exiting"}</div>
            <h2>${esc(c.name)}</h2>
            <div class="card-sub">${esc(c.role)} · ${esc(c.department)} · ${esc(c.location)} · ${esc(c.employmentType)}</div>
          </div>
          <button class="icon-btn" id="drawerClose">✕</button>
        </div>
        <div class="card-meta" style="margin-top:12px">
          <span class="tag days">${c.anchorLabel}: ${Agent.fmtDate(c.anchor)}</span>
          <span class="tag">${comp.done}/${comp.total} complete (${comp.pct}%)</span>
        </div>
      </div>
      <div class="drawer-body">
    `;

    // classification section
    if (c.classification) html += classifSection(c);

    // clearance + settlement (offboarding)
    if (c.type === "offboarding") html += clearanceSection(c);

    // checklist by owner
    html += `<div class="section"><div class="section-title">Checklist · grouped by owner</div>`;
    c.groups.forEach((g) => {
      const gdone = g.items.filter((i) => i.state === "done").length;
      html += `<div class="owner-group">
        <div class="owner-head">${ownerIcon(g.owner)} ${g.owner}<span class="ochip">${gdone}/${g.items.length}</span></div>`;
      g.items.forEach((it) => (html += itemEl(c, it)));
      html += `</div>`;
    });
    html += `</div>`;

    html += `</div>`;
    d.innerHTML = html;

    $("#drawerClose").addEventListener("click", closeDrawer);
    wireDrawer(c, d);
  }

  function classifSection(c) {
    const cl = c.classification;
    const amber = cl.status === "amber";
    let rows = Object.entries(cl.observed)
      .map(
        ([k, v]) =>
          `<div class="cl-row"><span class="k">${k}</span><span class="v ${v.contradicts ? "bad" : "ok"}">${esc(v.value)}${v.contradicts ? " ⚠" : " ✓"}</span></div>`
      )
      .join("");
    return `<div class="section">
      <div class="section-title">Worker classification check <span class="badge ${amber ? "escalated" : "valid"}">${amber ? "contradiction" : "consistent"}</span></div>
      <div class="cl-card">
        <div class="cl-row"><span class="k">Contracted as</span><span class="v">${esc(cl.contracted)}</span></div>
        ${rows}
        <div class="mini-note" style="margin-top:12px">${amber
          ? `Raised and stopped on ${cl.contradictions.length} concurring signals. The agent never reclassifies and never alters a contract — ${esc(cl.determination)}`
          : `Contracted type is consistent with the observed working pattern.`}</div>
      </div>
    </div>`;
  }

  function clearanceSection(c) {
    const cs = Agent.clearanceState(c);
    const rows = cs.items
      .map(
        (it) =>
          `<div class="cl-dept"><span>${esc(it.label)}</span><span class="badge ${it.state === "done" ? "valid" : "pending"}">${it.state === "done" ? "cleared" : "outstanding"}</span></div>`
      )
      .join("");
    const banner = cs.allClear
      ? `<div class="banner" style="background:var(--green-bg);color:#8fe3ac;border:1px solid #1c5234">✓ All clearances green — final settlement unlocked</div>`
      : `<div class="banner block">🔒 Final settlement hard-locked — ${cs.outstanding.length} clearance(s) outstanding (blocked, not warned)</div>`;
    return `<div class="section">
      <div class="section-title">Exit clearance aggregation</div>
      ${banner}
      <div class="clearance" style="margin-top:10px">${rows}</div>
    </div>`;
  }

  function itemEl(c, it) {
    const now = new Date();
    const overdue = it.state !== "done" && it.state !== "locked" && it.due < now;
    let stateClass = it.state === "done" ? "done" : it.state === "locked" ? "locked" : "";
    let sub = "";

    if (it.kind === "document") {
      const s = it.doc.status;
      const badge =
        s === "valid" ? `<span class="badge valid">valid</span>`
        : s === "invalid" ? `<span class="badge invalid">rejected</span>`
        : s === "escalated" ? `<span class="badge escalated">escalated to HR</span>`
        : `<span class="badge pending">awaiting upload</span>`;
      sub = `<div class="item-sub">${badge} ${esc(it.doc.message)}${it.doc.failures ? ` · ${it.doc.failures}/3 attempts` : ""}</div>`;
    } else if (it.kind === "ticket" && it.ticket) {
      const t = it.ticket;
      let st = t.confirmed ? "confirmed" : t.escalated ? "ESCALATED — security incident" : "raised, awaiting confirmation";
      sub = `<div class="item-sub ${t.escalated ? "overdue" : ""}">${esc(t.system)} · ${st}${t.effectiveAt ? " · effective " + Agent.fmtDateTime(t.effectiveAt) : ""}</div>`;
    } else if (it.kind === "settlement" && it.state === "locked") {
      sub = `<div class="item-sub locked">Hard-locked until all clearances are green</div>`;
    } else if (it.kind === "checkin") {
      sub = `<div class="item-sub ${overdue ? "overdue" : ""}">Due ${Agent.fmtDate(it.due)}${it.checkin.held ? " · held" : overdue ? " · not held — manager chased" : ""}</div>`;
    } else if (it.kind === "interview") {
      sub = `<div class="item-sub">Interviewer: ${esc(it.interview.interviewer)} · ${it.interview.done ? "completed (stored in restricted store)" : "scheduled"}</div>`;
    } else if (it.kind === "goal") {
      sub = `<div class="item-sub">${it.goal.recorded ? "Recorded: " + esc(it.goal.text) : "Required before checklist can complete"}</div>`;
    } else {
      sub = `<div class="item-sub ${overdue ? "overdue" : ""}">Due ${Agent.fmtDate(it.due)}${it.state === "done" ? " · done" : overdue ? " · overdue" : ""}</div>`;
    }

    // actions
    let actions = "";
    if (it.state !== "done") {
      if (it.kind === "document" && it.doc.status !== "escalated") {
        actions = `<div class="doc-sim">
          <select class="sim" data-doc="${it.id}">
            <option value="valid">Upload: valid document</option>
            <option value="wrong_type">Upload: wrong type</option>
            <option value="illegible">Upload: illegible scan</option>
            <option value="name_mismatch">Upload: name mismatch</option>
            <option value="expired">Upload: expired</option>
          </select>
          <button class="btn btn-sm" data-upload="${it.id}">Submit to agent</button>
        </div>`;
      } else if (it.kind === "ticket" && it.ticket && !it.ticket.confirmed) {
        actions = `<button class="btn btn-sm" data-confirm="${it.id}">IT confirms done</button>`;
        if (it.ticket.effectiveAt && !it.ticket.escalated)
          actions += ` <button class="btn btn-sm btn-ghost" data-escalate="${it.id}">Simulate 4h, no confirmation</button>`;
      } else if (it.kind === "settlement") {
        const cs = Agent.clearanceState(c);
        actions = cs.allClear
          ? `<button class="btn btn-sm" data-complete="${it.id}">Release settlement</button>`
          : `<span class="hint">Unlocks when clearances are green</span>`;
      } else if (it.kind === "checkin") {
        actions = `<button class="btn btn-sm" data-complete="${it.id}">Mark held</button>`;
      } else if (it.kind === "interview") {
        actions = `<button class="btn btn-sm" data-complete="${it.id}">Record response</button>`;
      } else if (it.kind === "goal") {
        actions = `<div class="doc-sim"><input class="sim" style="flex:1;min-width:140px" placeholder="e.g. Ship onboarding flow by day 30" data-goaltext="${it.id}">
          <button class="btn btn-sm" data-complete="${it.id}">Record goal</button></div>`;
      } else {
        actions = `<button class="btn btn-sm" data-complete="${it.id}">Mark complete</button>`;
      }
      if (overdue && it.kind !== "settlement")
        actions += ` <button class="btn btn-sm btn-ghost" data-chase="${it.id}">Chase now</button>`;
    }

    return `<div class="item">
      <div class="state"><span class="sdot ${stateClass}"></span></div>
      <div class="item-main">
        <div class="item-label">${esc(it.label)}</div>
        ${sub}
        ${actions ? `<div class="item-actions">${actions}</div>` : ""}
      </div>
    </div>`;
  }

  // ---------- drawer interactions ----------
  function wireDrawer(c, d) {
    const find = (id) => {
      for (const g of c.groups) for (const it of g.items) if (it.id === id) return it;
    };

    d.querySelectorAll("[data-upload]").forEach((b) =>
      b.addEventListener("click", () => {
        const it = find(b.dataset.upload);
        const quality = d.querySelector(`select[data-doc="${it.id}"]`).value;
        const res = Agent.validateDocument(it, quality, c.name);
        if (res.ok) {
          it.doc.status = "valid";
          it.doc.message = res.msg;
          it.state = "done";
          agentDo(c, "validate", `${c.name}: “${it.label}” validated — ${res.msg}`);
        } else {
          it.doc.failures++;
          if (it.doc.failures >= 3) {
            it.doc.status = "escalated";
            it.doc.message = `Escalated to HR after 3 failed attempts (last: ${res.reason}). No further automated requests sent.`;
            agentDo(c, "escalate", `${c.name}: “${it.label}” failed validation 3× — escalated to HR for manual handling.`, true);
          } else {
            it.doc.status = "invalid";
            it.doc.message = res.msg;
            agentDo(c, "reject", `${c.name}: “${it.label}” rejected (${res.reason}) — specific re-request sent naming the exact problem.`);
          }
        }
        renderAll();
      })
    );

    d.querySelectorAll("[data-confirm]").forEach((b) =>
      b.addEventListener("click", () => {
        const it = find(b.dataset.confirm);
        it.ticket.confirmed = true;
        it.state = "done";
        agentDo(c, "ticket", `${c.name}: “${it.label}” confirmed by IT${it.ticket.effectiveAt ? " — access revoked within SLA" : ""}.`);
        renderAll();
      })
    );

    d.querySelectorAll("[data-escalate]").forEach((b) =>
      b.addEventListener("click", () => {
        const it = find(b.dataset.escalate);
        it.ticket.escalated = true;
        agentDo(c, "escalate", `${c.name}: access revocation unconfirmed 4h after effective time — escalated to IT Lead + HR Manager. Logged as a SECURITY incident (an unrevoked account is not a pending task).`, true);
        renderAll();
      })
    );

    d.querySelectorAll("[data-complete]").forEach((b) =>
      b.addEventListener("click", () => {
        const it = find(b.dataset.complete);
        if (it.kind === "goal") {
          const input = d.querySelector(`input[data-goaltext="${it.id}"]`);
          const txt = (input.value || "").trim();
          if (!txt) { input.focus(); return; }
          it.goal.text = txt; it.goal.recorded = true;
          agentDo(c, "assemble", `${c.name}: measurable 30-day goal recorded — “${txt}”.`);
        } else if (it.kind === "checkin") {
          it.checkin.held = true;
          agentDo(c, "validate", `${c.name}: “${it.label}” marked held and logged against the lifecycle record.`);
        } else if (it.kind === "interview") {
          it.interview.done = true;
          agentDo(c, "human", `${c.name}: exit interview completed by ${it.interview.interviewer}; response stored in restricted store (HR-only).`);
        } else if (it.kind === "settlement") {
          agentDo(c, "validate", `${c.name}: all clearances green — final-settlement inputs released to payroll.`);
        } else {
          agentDo(c, "validate", `${c.name}: “${it.label}” completed.`);
        }
        it.state = "done";
        // settlement unlock check after any clearance completes
        maybeUnlockSettlement(c);
        renderAll();
      })
    );

    d.querySelectorAll("[data-chase]").forEach((b) =>
      b.addEventListener("click", () => {
        const it = find(b.dataset.chase);
        agentDo(c, "chase", `${c.name}: chased “${it.label}” (owner: ${it.owner}). Overdue — HR escalation at T-3 before ${c.anchorLabel.toLowerCase()}.`);
      })
    );
  }

  function maybeUnlockSettlement(c) {
    if (c.type !== "offboarding") return;
    const cs = Agent.clearanceState(c);
    const settle = c.groups.flatMap((g) => g.items).find((i) => i.kind === "settlement");
    if (!settle) return;
    if (cs.allClear && settle.state === "locked") {
      settle.state = "pending";
      settle.settlement.locked = false;
      agentDo(c, "validate", `${c.name}: final clearance complete — settlement hard-lock released. Payroll may now process.`);
    }
  }

  // ---------- agent log ----------
  function renderLog() {
    const box = $("#agentLog");
    box.innerHTML = "";
    if (!globalLog.length) {
      box.appendChild(el("div", "hint", "No activity yet."));
      return;
    }
    globalLog.slice(0, 80).forEach((en) => {
      const t = en.at.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
      const item = el("div", "log-item k-" + en.kind);
      item.innerHTML = `<div class="lt"><span class="log-badge">${en.kind}</span>${t} · ${esc(en.card)}</div><div class="lm">${esc(en.msg)}</div>`;
      box.appendChild(item);
    });
  }

  // ---------- modal ----------
  function openModal() {
    $("#modalScrim").classList.add("open");
    renderForm();
  }
  function closeModal() {
    $("#modalScrim").classList.remove("open");
  }
  function renderForm() {
    const f = $("#eventForm");
    if (modalMode === "onboarding") {
      f.innerHTML = `
        <div class="field"><label>Employee name</label><input name="name" value="Ananya Rao" required></div>
        <div class="field-row">
          <div class="field"><label>Role</label><input name="role" value="Backend Engineer" required></div>
          <div class="field"><label>Department</label><input name="department" value="Engineering" required></div>
        </div>
        <div class="field-row">
          <div class="field"><label>Location</label>
            <select name="location"><option>India</option><option>United Kingdom</option><option>United States</option></select>
          </div>
          <div class="field"><label>Employment type</label>
            <select name="employmentType"><option>Full-time</option><option>Contractor</option><option>Intern</option></select>
          </div>
        </div>
        <div class="field"><label>Start date</label><input type="date" name="startDate" value="${in14()}" required></div>
        <p class="hint">Pick <b>Contractor</b> to see the worker-classification check fire at contract issue.</p>`;
    } else {
      f.innerHTML = `
        <div class="field"><label>Employee name</label><input name="name" value="Rohit Menon" required></div>
        <div class="field-row">
          <div class="field"><label>Role</label><input name="role" value="Account Manager" required></div>
          <div class="field"><label>Department</label><input name="department" value="Commercial" required></div>
        </div>
        <div class="field-row">
          <div class="field"><label>Location</label>
            <select name="location"><option>India</option><option>United Kingdom</option><option>United States</option></select>
          </div>
          <div class="field"><label>Last working day</label><input type="date" name="lastWorkingDay" value="${in7()}" required></div>
        </div>
        <div class="field"><label>HR-07 case reference (optional — involuntary / disciplinary exits)</label><input name="caseRef" placeholder="e.g. HR-07-2041"></div>
        <p class="hint">Leave case reference blank for a standard resignation. The exit interview is auto-assigned to an independent interviewer.</p>`;
    }
  }

  function submitForm() {
    const f = $("#eventForm");
    const data = Object.fromEntries(new FormData(f).entries());
    if (!data.name) return;
    let card;
    if (modalMode === "onboarding") {
      card = Agent.buildOnboarding(data);
    } else {
      card = Agent.buildOffboarding(data);
    }
    addCard(card);
    closeModal();
    openDrawer(card.id);
  }

  // ---------- seed ----------
  function seed() {
    cards = [];
    globalLog = [];
    const j1 = Agent.buildOnboarding({ name: "Priya Sharma", role: "Product Designer", location: "India", department: "Design", employmentType: "Full-time", startDate: iso(Agent.addDays(new Date(), 10)) });
    const j2 = Agent.buildOnboarding({ name: "Daniel Okafor", role: "Data Analyst", location: "India", department: "Analytics", employmentType: "Contractor", startDate: iso(Agent.addDays(new Date(), 4)) });
    const x1 = Agent.buildOffboarding({ name: "Meera Iyer", role: "Operations Lead", location: "India", department: "Operations", lastWorkingDay: iso(Agent.addDays(new Date(), 3)) });
    const x2 = Agent.buildOffboarding({ name: "Arjun Nair", role: "Sales Executive", location: "India", department: "Commercial", lastWorkingDay: iso(Agent.addDays(new Date(), -1)), caseRef: "HR-07-2041" });

    [j1, j2, x1, x2].forEach(addCard);

    // make x2 realistic: some clearances already in, access revocation overdue/unconfirmed
    const itTicket = x2.groups[1].items[0];
    // leave unconfirmed to show the blocked settlement + overdue access revocation
    agentDo(x2, "chase", `${x2.name}: last working day passed — access revocation still unconfirmed. Agent tracking to confirmed.`);
  }

  // ---------- utils ----------
  function esc(s) { return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
  function iso(d) { return d.toISOString().slice(0, 10); }
  function in14() { return iso(Agent.addDays(new Date(), 14)); }
  function in7() { return iso(Agent.addDays(new Date(), 7)); }
  function ownerIcon(o) {
    const m = { Employee: "👤", IT: "💻", Payroll: "💰", Facilities: "🏢", Manager: "🧭", HR: "📋" };
    return `<span>${m[o] || "•"}</span>`;
  }

  // ---------- wire top-level ----------
  $("#btnNew").addEventListener("click", openModal);
  $("#btnReset").addEventListener("click", () => { seed(); closeDrawer(); });
  $("#modalClose").addEventListener("click", closeModal);
  $("#modalCancel").addEventListener("click", closeModal);
  $("#modalSubmit").addEventListener("click", submitForm);
  $("#scrim").addEventListener("click", closeDrawer);
  $("#modalScrim").addEventListener("click", (e) => { if (e.target.id === "modalScrim") closeModal(); });
  document.querySelectorAll(".mtab").forEach((t) =>
    t.addEventListener("click", () => {
      document.querySelectorAll(".mtab").forEach((x) => x.classList.remove("active"));
      t.classList.add("active");
      modalMode = t.dataset.mode;
      $("#modalTitle").textContent = modalMode === "onboarding" ? "New joiner" : "New leaver";
      renderForm();
    })
  );

  // init
  seed();
})();
