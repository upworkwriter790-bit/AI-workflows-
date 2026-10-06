/*
 * Shared action logic for the HR-02 agent (used by the Node server AND the hosted artifact).
 * Actions mutate a card in place and report what the agent did through the supplied log().
 */
const Actions = (() => {
  function make(log) {
    const A = typeof Agent !== "undefined" ? Agent : require("./agent.js");
  // ---------- actions (all agent decisions happen here, server-side) ----------
  function maybeUnlockSettlement(c) {
    if (c.type !== "offboarding") return;
    const settle = c.groups.flatMap((g) => g.items).find((i) => i.kind === "settlement");
    if (settle && settle.state === "locked" && A.clearanceState(c).allClear) {
      settle.state = "pending";
      settle.settlement.locked = false;
      log(c, "validate", `${c.name}: final clearance complete — settlement hard-lock released. Payroll may now process.`);
    }
  }
  const need = (cond, msg) => { if (!cond) throw Object.assign(new Error(msg), { status: 400 }); };

  const actions = {
    upload(c, it, body) {
      need(it && it.kind === "document", "Not a document item");
      need(it.doc.status !== "escalated", "Item already escalated to HR");
      const res = A.validateDocument(it, body.quality || "valid", c.name);
      if (body.fileName) it.doc.file = { name: body.fileName, size: body.fileSize || 0, stored: body.stored || null };
      if (res.ok) {
        it.doc.status = "valid"; it.doc.message = res.msg; it.state = "done";
        log(c, "validate", `${c.name}: “${it.label}” validated — ${res.msg}`);
      } else {
        it.doc.failures++;
        if (it.doc.failures >= 3) {
          it.doc.status = "escalated";
          it.doc.message = `Escalated to HR after 3 failed attempts (last: ${res.reason}). No further automated requests sent.`;
          log(c, "escalate", `${c.name}: “${it.label}” failed validation 3× — escalated to HR for manual handling.`, true);
        } else {
          it.doc.status = "invalid"; it.doc.message = res.msg;
          log(c, "reject", `${c.name}: “${it.label}” rejected (${res.reason}) — specific re-request sent naming the exact problem.`);
        }
      }
    },
    hrResolve(c, it) { // HR manually accepts an escalated document
      need(it && it.kind === "document", "Not a document item");
      it.doc.status = "valid"; it.doc.message = "Accepted manually by HR after escalation."; it.state = "done";
      log(c, "human", `${c.name}: HR manually accepted “${it.label}”.`);
    },
    confirmTicket(c, it) {
      need(it && it.ticket, "Not a ticket item");
      it.ticket.confirmed = true; it.state = "done";
      log(c, "ticket", `${c.name}: “${it.label}” confirmed by IT${it.ticket.effectiveAt ? " — access revoked" : ""}.`);
    },
    simulateEscalation(c, it) {
      need(it && it.ticket, "Not a ticket item");
      escalateTicket(c, it);
    },
    complete(c, it, body) {
      need(it, "Item not found");
      if (it.kind === "settlement") need(A.clearanceState(c).allClear, "Final settlement is locked until every clearance is green");
      if (it.kind === "goal") {
        const t = String(body.text || "").trim();
        need(t, "A measurable 30-day goal is required");
        it.goal = { text: t, recorded: true };
        log(c, "assemble", `${c.name}: measurable 30-day goal recorded — “${t}”.`);
      } else if (it.kind === "checkin") { it.checkin.held = true; log(c, "validate", `${c.name}: “${it.label}” marked held and logged against the lifecycle record.`); }
      else if (it.kind === "interview") { it.interview.done = true; log(c, "human", `${c.name}: exit interview completed by ${it.interview.interviewer}; response stored in restricted store (HR-only).`); }
      else if (it.kind === "settlement") log(c, "validate", `${c.name}: all clearances green — final-settlement inputs released to payroll.`);
      else log(c, "validate", `${c.name}: “${it.label}” completed.`);
      if (it.kind === "feedback") it.feedback.captured = true;
      if (it.kind === "goal") {
        const open = c.groups.flatMap((g) => g.items).filter((i) => i.kind !== "goal" && i.state !== "done");
        void open; // goal is required before the checklist can complete; it is itself an item
      }
      it.state = "done";
      maybeUnlockSettlement(c);
    },
    reopen(c, it) {
      need(it && it.state === "done" && it.kind !== "settlement", "Cannot reopen this item");
      it.state = "pending";
      if (it.ticket) it.ticket.confirmed = false;
      if (it.doc) { it.doc.status = "pending"; it.doc.message = "Reopened — awaiting upload"; it.doc.failures = 0; }
      if (it.clearance && c.type === "offboarding") {
        const s = c.groups.flatMap((g) => g.items).find((i) => i.kind === "settlement");
        if (s && s.state !== "done") { s.state = "locked"; s.settlement.locked = true; }
      }
      log(c, "human", `${c.name}: “${it.label}” reopened by HR.`);
    },
    chase(c, it) {
      need(it, "Item not found");
      it.lastChased = new Date();
      log(c, "chase", `${c.name}: chased “${it.label}” (owner: ${it.owner}). Overdue — HR escalation at T-3 before ${c.anchorLabel.toLowerCase()}.`);
    },
  };

  function escalateTicket(c, it) {
    if (it.ticket.escalated) return;
    it.ticket.escalated = true;
    log(c, "escalate", `${c.name}: access revocation unconfirmed 4h after effective time — escalated to IT Lead + HR Manager. Logged as a SECURITY incident (an unrevoked account is not a pending task).`, true);
  }


    const findItem = (c, id) => c.groups.flatMap((g) => g.items).find((i) => i.id === id);
    const CHASE_EVERY_MS = 10 * 60 * 1000;
    // One scheduler pass over a card: PRD chase cadence + 4h access-revocation escalation. Returns true if changed.
    function tickCard(c, now = new Date()) {
      let dirty = false;
      for (const it of c.groups.flatMap((g) => g.items)) {
        if (it.ticket && it.ticket.effectiveAt && !it.ticket.confirmed && !it.ticket.escalated &&
            now - it.ticket.effectiveAt >= 4 * 3600 * 1000) { escalateTicket(c, it); dirty = true; }
        if (it.state !== "done" && it.state !== "locked" && it.due < now && (!it.lastChased || now - it.lastChased >= CHASE_EVERY_MS)) {
          it.lastChased = now; dirty = true;
          log(c, "chase", `${c.name}: auto-chased overdue “${it.label}” (owner: ${it.owner}).`);
        }
      }
      return dirty;
    }
    return { actions, escalateTicket, need, findItem, tickCard };
  }
  return { make };
})();
if (typeof module !== "undefined") module.exports = Actions;
