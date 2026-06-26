/* ============================================================================
 * Engine tests — run with: npm test
 * Uses Node's built-in test runner with native TS stripping (Node 22+).
 * Verifies the deterministic flow completes and emits clean booking objects,
 * plus the fixes (fulfilment kind, confirm ambiguity, opt-out, FAQ, cancel).
 * ==========================================================================*/

import assert from "node:assert/strict";
import { test } from "node:test";
import { newSession, step, type BusinessProfile, type Session } from "./index";
import { parseAiOutput } from "./parse-tags";

const clinic: BusinessProfile = {
  type: "clinic", brand: "CityCare", agentName: "Aria", oneLiner: "a clinic",
  days: "Mon–Sat", hours: "9–7", languages: ["English"], slots: ["9 AM", "11 AM"],
  providers: ["Dr. Rao"], address: "Madhapur",
  services: [{ name: "General Consultation", price: "₹500" }],
  faqs: [{ q: "Do you accept insurance?", a: "Yes, we accept most insurers." }],
};

const retail: BusinessProfile = {
  type: "retail", brand: "Riymay", agentName: "Noor", oneLiner: "a shop",
  days: "Mon–Sun", hours: "10–9", languages: ["English"], slots: [], delivery: true,
  services: [{ name: "Hoodie", price: "₹3,800" }],
};

/** Drive a scripted conversation and return the final reply object. */
function run(profile: BusinessProfile, msgs: string[], start?: Session) {
  let s = start ?? { ...newSession(), phase: "detect" as const };
  let out = step(s, msgs[0], profile);
  s = out.session;
  for (const m of msgs.slice(1)) {
    out = step(s, m, profile);
    s = out.session;
  }
  return out;
}

test("clinic booking completes and emits a clean object", () => {
  const out = run(clinic, [
    "I want to book",
    "General Consultation",
    "Dr. Rao",
    "tomorrow",
    "11 AM",
    "Priya Sharma",
    "9876543210",
    "yes",
  ]);
  assert.ok(out.booking, "should emit a booking");
  assert.equal(out.booking!.type, "clinic");
  assert.equal(out.booking!.name, "Priya Sharma");
  assert.equal(out.booking!.service, "General Consultation");
  assert.equal(out.booking!.phone, "9876543210");
  assert.match(out.reply, /booked/i);
});

test("retail uses fulfil slot and asks for address only on delivery", () => {
  const out = run(retail, ["I want to buy a Hoodie", "2", "delivery", "12 MG Road", "Rohan", "9876543210", "yes"]);
  assert.ok(out.booking);
  assert.equal(out.booking!.fulfilment, "delivery");
  assert.equal(out.booking!.address, "12 MG Road");
});

test("retail pickup skips the address slot", () => {
  const out = run(retail, ["buy Hoodie", "1", "pickup", "Rohan", "9876543210", "yes"]);
  assert.ok(out.booking);
  assert.equal(out.booking!.fulfilment, "pickup");
  assert.equal(out.booking!.address, undefined);
});

test("ambiguous reply at confirm does NOT wipe the booking", () => {
  let s: Session = { ...newSession(), phase: "detect" };
  const path = ["book", "General Consultation", "Dr. Rao", "tomorrow", "11 AM", "Priya", "9876543210"];
  let out = step(s, path[0], clinic);
  s = out.session;
  for (const m of path.slice(1)) { out = step(s, m, clinic); s = out.session; }
  assert.equal(s.phase, "confirm");
  out = step(s, "actually what's included?", clinic); // ambiguous, no yes/no keyword
  assert.equal(out.session.phase, "confirm", "stays in confirm");
  assert.equal(out.session.booking.name, "Priya", "keeps collected fields");
});

test("explicit no restarts collection", () => {
  let s: Session = { ...newSession(), phase: "detect" };
  const path = ["book", "General Consultation", "Dr. Rao", "tomorrow", "11 AM", "Priya", "9876543210"];
  let out = step(s, path[0], clinic);
  s = out.session;
  for (const m of path.slice(1)) { out = step(s, m, clinic); s = out.session; }
  out = step(s, "no", clinic);
  assert.equal(out.session.phase, "collecting");
  assert.deepEqual(out.session.booking, {});
});

test("STOP opts the contact out", () => {
  const out = run(clinic, ["STOP"]);
  assert.equal(out.optOut, true);
  assert.equal(out.session.phase, "opted_out");
});

test("human request escalates", () => {
  const out = run(clinic, ["can I talk to a person"]);
  assert.ok(out.escalate);
  assert.equal(out.session.phase, "escalated");
});

test("FAQ is answered directly", () => {
  const out = run(clinic, ["do you accept insurance?"]);
  assert.match(out.reply, /insurers/i);
});

test("cancel flow captures a structured CANCEL object", () => {
  const out = run(clinic, ["I want to cancel", "Priya Sharma", "tomorrow"]);
  assert.ok(out.cancel);
  assert.equal(out.cancel!.name, "Priya Sharma");
  assert.ok(out.escalate);
});

test("after-hours greeting notes closure but still books", () => {
  const closed: BusinessProfile = { ...clinic, businessHours: { days: [1], open: "09:00", close: "10:00" } };
  // Sunday 8am — closed
  const now = new Date("2026-06-28T08:00:00");
  const out = step(newSession(), "hi", closed, { now });
  assert.match(out.reply, /closed/i);
});

test("parseAiOutput extracts booking and strips tags", () => {
  const raw = `Great, all set!\n<<BOOKING type="clinic">>\nname: Priya\nservice: General Consultation\ndate: 2026-07-01\ntime: 11:00\nphone: 9876543210\n<<END_BOOKING>>`;
  const parsed = parseAiOutput(raw);
  assert.equal(parsed.booking?.name, "Priya");
  assert.equal(parsed.booking?.type, "clinic");
  assert.ok(!parsed.reply.includes("<<BOOKING"));
  assert.match(parsed.reply, /all set/i);
});

test("parseAiOutput drops empty placeholder values", () => {
  const raw = `<<BOOKING type="hotel">>\nroom: Garden Room\nguests: <value or empty>\nname: Sam\n<<END_BOOKING>>`;
  const parsed = parseAiOutput(raw);
  assert.equal(parsed.booking?.guests, undefined);
  assert.equal(parsed.booking?.room, "Garden Room");
});
