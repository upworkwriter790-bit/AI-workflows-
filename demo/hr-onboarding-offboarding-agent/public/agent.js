/*
 * HR-02 Onboarding + Offboarding Agent — engine (deterministic logic).
 * Mirrors the PRD: checklist assembly by role × location × department × employment-type,
 * document validation, worker-classification check, due-date anchoring, clearance hard-lock,
 * access-revocation ticket with 4h escalation. No reclassification, no settlement calc — by design.
 */
const Agent = (() => {
  const nextId = (p) => `${p}-${Math.random().toString(36).slice(2, 9)}`;
  const DAY = 86400000;

  const fmtDate = (d) =>
    d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
  const fmtDateTime = (d) =>
    d.toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  const addDays = (d, n) => new Date(d.getTime() + n * DAY);
  const daysBetween = (a, b) => Math.round((a - b) / DAY);

  // ---- Document checklist depends on location (India assumption from PRD) ----
  function docItems(location, anchor) {
    const india = /india/i.test(location);
    const base = india
      ? [
          ["PAN card", "pan"],
          ["Aadhaar", "aadhaar"],
          ["PF / UAN declaration", "pfuan"],
          ["Bank proof (cancelled cheque / passbook)", "bank"],
          ["Signed offer letter", "offer"],
          ["Educational certificates", "edu"],
        ]
      : [
          ["Government photo ID", "id"],
          ["Tax declaration form", "tax"],
          ["Bank proof", "bank"],
          ["Signed offer letter", "offer"],
          ["Educational certificates", "edu"],
        ];
    return base.map(([label, key]) => ({
      id: nextId("item"),
      label,
      owner: "Employee",
      kind: "document",
      due: addDays(anchor, -5),
      state: "pending",
      doc: { status: "pending", failures: 0, message: "Awaiting upload" },
      docKey: key,
    }));
  }

  function mkItem(label, owner, kind, due, extra = {}) {
    return { id: nextId("item"), label, owner, kind, due, state: "pending", ...extra };
  }

  // ---------------- ONBOARDING ----------------
  function buildOnboarding(input) {
    const { name, role, location, department, employmentType, startDate } = input;
    const anchor = new Date(startDate + "T09:00:00");
    const contractor = /contractor/i.test(employmentType);
    const intern = /intern/i.test(employmentType);

    const groups = [];

    // Employee — documents
    groups.push({ owner: "Employee", items: docItems(location, anchor) });

    // IT — accounts, hardware, access (via ticket only, never direct API write)
    const itItems = [
      mkItem("Create email account", "IT", "ticket", addDays(anchor, -2), {
        ticket: { system: "IT ticketing (Jira SM)", raised: true, confirmed: false },
      }),
      mkItem("Provision laptop / hardware", "IT", "ticket", addDays(anchor, -2), {
        ticket: { system: "Asset register", raised: true, confirmed: false },
      }),
      mkItem(`Grant role-based system access (${role})`, "IT", "ticket", addDays(anchor, -2), {
        ticket: { system: "Identity provider", raised: true, confirmed: false },
      }),
    ];
    groups.push({ owner: "IT", items: itItems });

    // Payroll
    groups.push({
      owner: "Payroll",
      items: [
        mkItem("Bank, PF & tax setup", "Payroll", "task", addDays(anchor, -1)),
        mkItem("Salary structure configured", "Payroll", "task", addDays(anchor, -1)),
      ],
    });

    // Facilities (lighter for contractor/intern)
    const facItems = [mkItem("Access card issued", "Facilities", "task", addDays(anchor, -1))];
    if (!contractor) facItems.unshift(mkItem("Seat allocated", "Facilities", "task", addDays(anchor, -1)));
    groups.push({ owner: "Facilities", items: facItems });

    // Manager — orientation, buddy, 30-day structure, check-ins, goal, feedback
    const mgr = [
      mkItem("Orientation session booked", "Manager", "task", anchor),
    ];
    if (!intern) mgr.push(mkItem("Buddy assigned", "Manager", "task", anchor));
    mgr.push(
      mkItem("Measurable 30-day goal agreed", "Manager", "goal", anchor, {
        goal: { text: "", recorded: false },
      }),
      mkItem("Day-7 manager check-in", "Manager", "checkin", addDays(anchor, 7), { checkin: { held: false } }),
      mkItem("Day-14 manager check-in", "Manager", "checkin", addDays(anchor, 14), { checkin: { held: false } }),
      mkItem("Day-30 manager check-in", "Manager", "checkin", addDays(anchor, 30), { checkin: { held: false } }),
      mkItem("Day-30 new-hire feedback captured", "HR", "feedback", addDays(anchor, 30), { feedback: { captured: false } }),
    );
    groups.push({ owner: "Manager", items: mgr });

    const card = {
      id: nextId("ONB"),
      type: "onboarding",
      name, role, location, department, employmentType,
      anchor, anchorLabel: "Start date",
      groups,
      classification: null,
      caseRef: null,
      logs: [],
    };

    // Classification check at contract issue (contractors only)
    if (contractor) card.classification = runClassification(card);

    // Initial agent activity
    const totalItems = groups.reduce((n, g) => n + g.items.length, 0);
    card.logs.push(
      logEntry("assemble", `Assembled ${totalItems}-item checklist for ${role} · ${department} · ${location} · ${employmentType} — no per-combination template used.`),
      logEntry("ticket", `Raised ${itItems.length} IT tickets (email, hardware, access) via ticketing — agent requests, IT provisions.`),
      logEntry("assemble", `Due dates anchored to start date ${fmtDate(anchor)}. Day-7/14/30 check-ins booked on manager's calendar.`),
    );
    if (contractor) {
      const c = card.classification;
      if (c.status === "amber")
        card.logs.push(logEntry("flag", `Classification check at contract issue: contradiction on ${c.contradictions.length} signals — raised and stopped. Agent never reclassifies; legal counsel decides.`, true));
      else card.logs.push(logEntry("validate", `Classification check at contract issue: contracted type matches observed pattern.`));
    }
    return card;
  }

  // ---------------- OFFBOARDING ----------------
  function buildOffboarding(input) {
    const { name, role, location, department, lastWorkingDay, caseRef } = input;
    const lwd = new Date(lastWorkingDay + "T18:00:00");

    const groups = [
      {
        owner: "Employee",
        items: [
          mkItem("Knowledge handover document", "Employee", "task", addDays(lwd, -2)),
          mkItem("Return company assets (laptop, devices)", "Employee", "task", lwd),
        ],
      },
      {
        owner: "IT",
        items: [
          mkItem("Access-revocation ticket (effective last working day)", "IT", "ticket", lwd, {
            ticket: {
              system: "Identity provider",
              raised: true,
              confirmed: false,
              effectiveAt: lwd,
              escalated: false,
            },
          }),
          mkItem("Email & SSO deactivation", "IT", "ticket", lwd, {
            ticket: { system: "IT ticketing (Jira SM)", raised: true, confirmed: false },
          }),
        ],
      },
      {
        owner: "Facilities",
        items: [mkItem("Access card & seat returned", "Facilities", "clearance", addDays(lwd, -1), { clearance: true })],
      },
      {
        owner: "Manager",
        items: [mkItem("Manager clearance sign-off", "Manager", "clearance", addDays(lwd, -1), { clearance: true })],
      },
      {
        owner: "HR",
        items: [
          mkItem("Exit interview (independent interviewer)", "HR", "interview", addDays(lwd, -1), {
            interview: { interviewer: pickInterviewer(role, department), done: false },
          }),
          mkItem("Final clearance (HR)", "HR", "clearance", lwd, { clearance: true }),
          mkItem("Release final-settlement inputs to payroll", "Payroll", "settlement", addDays(lwd, 7), {
            settlement: { locked: true },
            state: "locked",
          }),
        ],
      },
    ];
    // mark department clearances
    groups[1].items[0].clearance = true; // access revocation counts toward clearance
    groups[1].items[1].clearance = true;

    const card = {
      id: nextId("OFB"),
      type: "offboarding",
      name, role, location, department,
      employmentType: input.employmentType || "Full-time",
      anchor: lwd, anchorLabel: "Last working day",
      groups,
      classification: null,
      caseRef: caseRef || null,
      logs: [],
    };

    const totalItems = groups.reduce((n, g) => n + g.items.length, 0);
    card.logs.push(
      logEntry("assemble", `Built exit checklist in reverse — ${totalItems} items. Clearance sign-offs aggregated; final settlement hard-locked until all clear.`),
      logEntry("ticket", `Access-revocation ticket raised with effective date-time ${fmtDateTime(lwd)}. Agent tracks it to confirmed, not just raised.`),
      logEntry("block", `Final settlement is BLOCKED (not warned) until every department clearance is green.`, true),
    );
    if (caseRef)
      card.logs.push(logEntry("human", `Entered from HR-07 with case reference ${caseRef} (involuntary/disciplinary exit authorised upstream).`));
    card.logs.push(
      logEntry("human", `Exit interview assigned to ${card.groups[4].items[0].interview.interviewer} — never the departing employee's line manager.`),
    );
    return card;
  }

  function pickInterviewer(role, department) {
    // independent interviewer — a different department's HRBP, never the line manager
    const pool = ["HRBP — Operations", "HRBP — Engineering", "HRBP — Commercial", "People Partner — Central"];
    const idx = (role.length + department.length) % pool.length;
    return pool[idx];
  }

  // ---------------- CLASSIFICATION CHECK ----------------
  // Compares contracted worker type vs observed working pattern (schedule, equipment, supervision, reporting line).
  function runClassification(card) {
    // For the demo, a contractor on a full-time pattern with company equipment, direct supervision,
    // and a company reporting line is the classic contradiction described in the PRD.
    const contracted = "Independent contractor";
    const observed = {
      Schedule: { value: "Full-time hours (9–6, Mon–Fri)", contradicts: true },
      Equipment: { value: "Company-issued laptop & devices", contradicts: true },
      Supervision: { value: "Direct day-to-day supervision", contradicts: true },
      "Reporting line": { value: "Reports to a company manager", contradicts: true },
    };
    const contradictions = Object.entries(observed)
      .filter(([, v]) => v.contradicts)
      .map(([k]) => k);
    // PRD: flag requires MULTIPLE concurring signals, not one
    const status = contradictions.length >= 2 ? "amber" : "green";
    return { contracted, observed, contradictions, status, determination: "legal counsel decides." };
  }

  // ---------------- DOCUMENT VALIDATION ----------------
  // Validates type, legibility, name match, expiry; emits a specific re-request on failure.
  function validateDocument(item, quality, employeeName) {
    const map = {
      valid: { ok: true, msg: `Validated: correct type, legible, name matches ${employeeName}, not expired.` },
      wrong_type: { ok: false, reason: "wrong type", msg: `Rejected — this is not a ${docLabelShort(item)}. Please upload a clear ${docLabelShort(item)}.` },
      illegible: { ok: false, reason: "illegible", msg: `Rejected — the file is not legible. Please re-upload a clear, in-focus scan of your ${docLabelShort(item)}.` },
      name_mismatch: { ok: false, reason: "name mismatch", msg: `Flagged for HR review — the name on this document does not match the employee record (${employeeName}).` },
      expired: { ok: false, reason: "expired", msg: `Rejected — this ${docLabelShort(item)} appears expired. Please upload a valid, in-date copy.` },
    };
    return map[quality] || map.valid;
  }
  function docLabelShort(item) {
    return item.label.replace(/\s*\(.*\)\s*/, "").toLowerCase();
  }

  // ---------------- helpers used by UI ----------------
  function completion(card) {
    let total = 0, done = 0;
    card.groups.forEach((g) =>
      g.items.forEach((it) => {
        total++;
        if (it.state === "done") done++;
      })
    );
    return { total, done, pct: total ? Math.round((done / total) * 100) : 0 };
  }

  function clearanceState(card) {
    // for offboarding: are all clearance items green?
    const cl = [];
    card.groups.forEach((g) =>
      g.items.forEach((it) => {
        if (it.clearance) cl.push(it);
      })
    );
    const outstanding = cl.filter((it) => it.state !== "done");
    return { items: cl, outstanding, allClear: outstanding.length === 0 && cl.length > 0 };
  }

  function overdueItems(card, now = new Date()) {
    const out = [];
    card.groups.forEach((g) =>
      g.items.forEach((it) => {
        if (it.state !== "done" && it.state !== "locked" && it.due < now) out.push(it);
      })
    );
    return out;
  }

  function logEntry(kind, msg, important = false) {
    return { kind, msg, important, at: new Date() };
  }

  // JSON round-trips turn Dates into strings; restore them after loading from the API / DB.
  function reviveDates(card) {
    const D = (v) => (v ? new Date(v) : v);
    card.anchor = D(card.anchor);
    card.groups.forEach((g) =>
      g.items.forEach((it) => {
        it.due = D(it.due);
        if (it.ticket && it.ticket.effectiveAt) it.ticket.effectiveAt = D(it.ticket.effectiveAt);
        if (it.lastChased) it.lastChased = D(it.lastChased);
      })
    );
    return card;
  }

  return {
    reviveDates,
    buildOnboarding,
    buildOffboarding,
    validateDocument,
    runClassification,
    completion,
    clearanceState,
    overdueItems,
    logEntry,
    fmtDate,
    fmtDateTime,
    addDays,
    daysBetween,
    nextId,
  };
})();
if (typeof module !== "undefined") module.exports = Agent;
