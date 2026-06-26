/* ============================================================================
 * vertical-engine — config-driven, multi-vertical WhatsApp booking engine.
 *
 * Fill in ONE BusinessProfile (clinic, dental, salon, hotel, restaurant,
 * retail, travel, fitness, automotive or generic) and this module produces:
 *
 *   1. generateSystemPrompt(profile) — an adaptive AI system prompt for the
 *      exact business (persona, flow, guardrails, escalation, output tags).
 *   2. step(session, message, profile) — a deterministic booking state machine
 *      that runs the interactive conversation reliably WITHOUT depending on an
 *      LLM for the happy path. It always completes the flow and always emits a
 *      clean structured booking object.
 *
 * Why deterministic + LLM (not LLM-only): a booking flow must never lose a
 * field or hallucinate a confirmation. The FSM guarantees completion; the LLM
 * layer (Gemini -> OpenAI) wraps it for fuzzy, natural-language understanding.
 *
 * --- What was fixed vs. the original prototype ------------------------------
 *  • retail "fulfilment" is now its own `fulfil` slot kind (was mislabelled as
 *    optionsFrom:"services", which leaked product names into the pickup/delivery
 *    step).
 *  • Confirmation no longer wipes the whole booking on ANY non-"yes" reply. It
 *    only restarts on an explicit "no/change"; ambiguous replies re-ask.
 *  • Added STOP / opt-out handling (WATI-style broadcast suppression).
 *  • Cancellation now captures a structured CANCEL object instead of a blind
 *    escalation, and routes to a human.
 *  • Added an after-hours guardrail driven by structured businessHours.
 *  • Added direct FAQ answering in the intent router.
 *  • Greeting no longer double-counts a turn when it re-routes an opening
 *    message that already contained intent.
 * ==========================================================================*/

import { BLUEPRINTS } from "./blueprints";
import type {
  Blueprint,
  Booking,
  BusinessProfile,
  EngineReply,
  Runtime,
  Session,
  SlotDef,
} from "./types";

export * from "./types";
export { BLUEPRINTS, VERTICAL_ORDER } from "./blueprints";

// ─── Keyword matchers (intent detection) ────────────────────────────────────

const KW = {
  book: /\b(book|appointment|appt|schedule|reserve|reservation|booking|slots?|visit|tables?|rooms?|stay|trip|tour|order|buy|want|need|available|class|session)\b/i,
  price: /\b(prices?|costs?|fees?|charges?|rates?|package|how much|kitna)\b/i,
  hours: /\b(hours?|timing|timings|open|close|closing|when.*open)\b/i,
  location: /\b(where|location|address|located|directions|reach|map)\b/i,
  cancel: /\b(cancel|reschedule|postpone|change my|change the)\b/i,
  human: /\b(human|person|agent|representative|talk to|speak to|manager|owner|real person)\b/i,
  yes: /\b(yes|yeah|yep|sure|ok|okay|confirm|confirmed|correct|go ahead|haan|book it|please do|do it)\b/i,
  no: /\b(no|nope|nah|wrong|incorrect|change|not right|nahi)\b/i,
  stop: /^\s*(stop|unsubscribe|opt.?out)\s*$/i,
};

// ─── Working-hours guardrail ────────────────────────────────────────────────

/** True when `now` falls inside the profile's structured business hours. */
export function isOpenNow(p: BusinessProfile, now = new Date()): boolean {
  const bh = p.businessHours;
  if (!bh) return true; // unknown → assume open, never block a booking
  if (!bh.days.includes(now.getDay())) return false;
  const [oh, om] = bh.open.split(":").map(Number);
  const [ch, cm] = bh.close.split(":").map(Number);
  const cur = now.getHours() * 60 + now.getMinutes();
  return cur >= oh * 60 + om && cur < ch * 60 + cm;
}

// ─── Slot helpers ───────────────────────────────────────────────────────────

function activeSlots(bp: Blueprint, booking: Booking): SlotDef[] {
  return bp.slots.filter((s) => {
    if (!s.dependsOn) return true;
    return booking[s.dependsOn.key]?.toLowerCase() === s.dependsOn.equals;
  });
}

function optionsFor(s: SlotDef, p: BusinessProfile): string[] {
  if (s.optionsFrom === "services") return p.services.map((x) => x.name);
  if (s.optionsFrom === "providers") return p.providers ?? [];
  if (s.optionsFrom === "slots") return p.slots;
  return [];
}

/**
 * Pull a value for a slot out of free text.
 *  - lenient (default): we explicitly asked for this slot, so accept best guess.
 *  - strict: opportunistic pre-fill from an intent message; only accept a
 *    confident, typed match so we never mislabel free text as a name/service.
 */
function extract(s: SlotDef, msg: string, p: BusinessProfile, strict = false): string | null {
  const m = msg.trim();
  if (!m) return null;

  if (s.kind === "fulfil") {
    if (/deliver/i.test(m)) return "delivery";
    if (/pick ?up|collect/i.test(m)) return "pickup";
    return null;
  }
  if (s.kind === "choice") {
    const opts = optionsFor(s, p);
    const hit = opts.find((o) => m.toLowerCase().includes(o.toLowerCase().split(" ")[0]));
    if (hit) return hit;
    return strict ? null : m; // when asked, accept their wording (e.g. "tooth pain")
  }
  if (s.kind === "time") {
    const t = m.match(/\b(\d{1,2})(:\d{2})?\s?(am|pm)\b/i);
    return t ? t[0].toUpperCase().replace(/\s+/, " ") : strict ? null : m;
  }
  if (s.kind === "number") {
    const num = m.match(/\b(\d{1,3})\b/);
    if (num) return num[1];
    return /\b(one|two|three|four|five|six|seven|eight|nine|ten)\b/i.test(m) ? m : null;
  }
  if (s.kind === "phone") {
    const ph = m.replace(/[^\d+]/g, "");
    return ph.length >= 8 ? ph : null;
  }
  if (s.kind === "date") {
    const looksLikeDate =
      /\b(today|tomorrow|day after|next|this|mon|tue|wed|thu|fri|sat|sun|\d{1,2}[/\-]\d{1,2}|\d{1,2}(st|nd|rd|th)?\s+\w+|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b/i.test(m);
    if (looksLikeDate) return m;
    return strict ? null : m.length > 2 ? m : null;
  }
  return strict ? null : m; // plain text (name, address) only when asked
}

function askFor(s: SlotDef, p: BusinessProfile): string {
  if (s.kind === "fulfil") return p.delivery ? "Would you like pickup or delivery?" : "Where would you like to pick this up?";
  let q = s.ask;
  const opts = optionsFor(s, p);
  if (s.optionsFrom === "slots" && opts.length) q += ` Available: ${opts.join(", ")}.`;
  else if (s.optionsFrom === "providers" && opts.length) q += ` Options: ${opts.join(", ")}.`;
  else if (s.optionsFrom === "services" && opts.length && opts.length <= 8) q += ` We offer: ${opts.join(", ")}.`;
  return q;
}

/** Move to the next still-empty active slot (or to confirmation). */
function advanceCollecting(s: Session, bp: Blueprint, p: BusinessProfile): EngineReply {
  const slots = activeSlots(bp, s.booking);
  for (let i = 0; i < slots.length; i++) {
    if (!(slots[i].key in s.booking)) {
      s.slotIdx = i;
      return { reply: askFor(slots[i], p), session: s };
    }
  }
  s.phase = "confirm";
  return { reply: bp.confirm(s.booking, p), session: s };
}

// ─── Public API ─────────────────────────────────────────────────────────────

export function newSession(): Session {
  return { phase: "greeting", booking: {}, slotIdx: 0, turns: 0 };
}

/** Public helper for UIs: the currently-relevant slots given answers so far. */
export function activeSlotsFor(p: BusinessProfile, booking: Booking): SlotDef[] {
  return activeSlots(BLUEPRINTS[p.type], booking);
}

/** Try to answer an FAQ from the profile. Returns null if none matched. */
function matchFaq(p: BusinessProfile, msg: string): string | null {
  if (!p.faqs?.length) return null;
  const words = msg.toLowerCase().split(/\W+/).filter((w) => w.length > 3);
  let best: { a: string; score: number } | null = null;
  for (const f of p.faqs) {
    const q = f.q.toLowerCase();
    const score = words.reduce((acc, w) => acc + (q.includes(w) ? 1 : 0), 0);
    if (score > 0 && (!best || score > best.score)) best = { a: f.a, score };
  }
  return best && best.score >= 2 ? best.a : null;
}

/** Intent routing for an already-greeted session. Pure: mutates the passed s. */
function route(s: Session, msg: string, bp: Blueprint, p: BusinessProfile): EngineReply {
  if (KW.price.test(msg)) {
    const list = p.services.map((x) => `${x.name}${x.price ? ` — ${x.price}` : ""}`).join("\n");
    return { reply: `Here's our pricing:\n${list}\n\nWould you like to book one?`, session: s };
  }
  if (KW.hours.test(msg)) {
    return { reply: `We're open ${p.days}, ${p.hours}. Want me to set up a ${bp.noun.booking}?`, session: s };
  }
  if (KW.location.test(msg)) {
    const loc = p.address
      ? `We're at ${p.address}.${p.mapsUrl ? ` Map: ${p.mapsUrl}` : ""} Shall I book you in?`
      : `Let me get our exact address for you.`;
    return { reply: loc, session: s };
  }
  if (KW.cancel.test(msg)) {
    s.phase = "cancelling";
    s.booking = {};
    return {
      reply: `No problem — I can help with that. What name is the ${bp.noun.booking} under, and what's its current date?`,
      session: s,
    };
  }

  const faq = matchFaq(p, msg);
  if (faq) return { reply: `${faq}\n\nAnything else I can help with?`, session: s };

  // Start the booking flow; opportunistically pre-fill confidently-typed slots.
  s.phase = "collecting";
  s.slotIdx = 0;
  for (const slot of activeSlots(bp, s.booking)) {
    const v = extract(slot, msg, p, true);
    if (v !== null && v !== "") s.booking[slot.key] = v;
  }
  return advanceCollecting(s, bp, p);
}

/**
 * Advance the conversation by one turn.
 * One message in → one reply out (plus optional structured side-effects).
 */
export function step(session: Session, userMsg: string, p: BusinessProfile, rt: Runtime = {}): EngineReply {
  const bp = BLUEPRINTS[p.type];
  const s: Session = { ...session, booking: { ...session.booking }, turns: session.turns + 1 };
  const msg = userMsg || "";

  // Opt-out (WATI-style) — highest priority, terminal.
  if (KW.stop.test(msg)) {
    s.phase = "opted_out";
    s.optedOut = true;
    return {
      reply: "You've been unsubscribed and won't receive further messages. Reply START anytime to opt back in.",
      session: s,
      optOut: true,
    };
  }

  // Global escalation triggers.
  if (KW.human.test(msg) || (s.turns > 16 && s.phase !== "confirm" && s.phase !== "done")) {
    s.phase = "escalated";
    return {
      reply: "I'm connecting you with a team member now — they'll be with you shortly.",
      session: s,
      escalate: "customer requested human / long thread",
    };
  }

  // Cancellation capture.
  if (s.phase === "cancelling") {
    if (!s.booking.name) {
      s.booking.name = msg.trim();
      return { reply: "Thanks. And what date is the booking you'd like to cancel or change?", session: s };
    }
    s.booking.date = msg.trim();
    s.phase = "escalated";
    return {
      reply: `Got it — I've flagged your booking under ${s.booking.name} (${s.booking.date}) for our team to update. They'll confirm shortly.`,
      session: s,
      cancel: { type: p.type, name: s.booking.name, date: s.booking.date },
      escalate: "cancel/reschedule requested",
    };
  }

  // Greeting → detect; if the opener already carries intent, route it now
  // (without spending a second turn).
  if (s.phase === "greeting") {
    s.phase = "detect";
    const opened = isOpenNow(p, rt.now);
    if (!opened) s.afterHours = true;
    const hasIntent =
      KW.book.test(msg) || KW.price.test(msg) || KW.hours.test(msg) || KW.location.test(msg) || KW.cancel.test(msg);
    if (hasIntent) return route(s, msg, bp, p);
    const hoursNote = opened ? "" : ` We're currently closed (${p.days}, ${p.hours}), but I can still take your details.`;
    return { reply: `Hi! I'm ${p.agentName} from ${p.brand}.${hoursNote} How can I help you today?`, session: s };
  }

  if (s.phase === "detect") return route(s, msg, bp, p);

  // Slot filling.
  if (s.phase === "collecting") {
    const slots = activeSlots(bp, s.booking);
    const cur = slots[s.slotIdx];
    if (cur && !(cur.key in s.booking)) {
      const val = extract(cur, msg, p, false);
      if (val === null && !cur.optional) {
        return { reply: `Sorry, I didn't catch that. ${askFor(cur, p)}`, session: s };
      }
      s.booking[cur.key] = val ?? "";
    }
    return advanceCollecting(s, bp, p);
  }

  // Confirmation.
  if (s.phase === "confirm") {
    if (KW.yes.test(msg)) {
      s.phase = "done";
      const tail = s.afterHours
        ? " As we're currently closed, our team will reconfirm the exact slot when we open."
        : "";
      return {
        reply: bp.done(s.booking, p) + tail,
        session: s,
        booking: { type: p.type, ...s.booking },
      };
    }
    if (KW.no.test(msg)) {
      s.phase = "collecting";
      s.slotIdx = 0;
      s.booking = {};
      return { reply: `No problem, let's redo it. ${askFor(activeSlots(bp, {})[0], p)}`, session: s };
    }
    // Ambiguous — re-ask rather than discarding everything.
    return { reply: `Just to confirm — ${bp.confirm(s.booking, p)} (reply "yes" to book, or tell me what to change.)`, session: s };
  }

  return { reply: "Is there anything else I can help with?", session: s };
}

// ─── Prompt generator ───────────────────────────────────────────────────────
// Produces the system prompt for the AI auto-reply layer (Gemini / OpenAI).
// Adapts vocabulary, slots, services and FAQs per vertical.

export function generateSystemPrompt(p: BusinessProfile): string {
  const bp = BLUEPRINTS[p.type];
  const n = bp.noun;
  const fields = bp.slots.map((s) => s.key).join(", ");
  const services = p.services.length
    ? p.services.map((s) => `- ${s.name}${s.price ? `: ${s.price}` : ""}${s.note ? ` (${s.note})` : ""}`).join("\n")
    : "- (none listed — say you will check and escalate)";
  const providers = p.providers?.length ? `\nAvailable ${n.provider}s: ${p.providers.join(", ")}.` : "";
  const faqs = p.faqs?.length ? p.faqs.map((f) => `Q: ${f.q}\nA: ${f.a}`).join("\n\n") : "(none configured)";
  const med = p.type === "clinic" || p.type === "dental";

  return `You are ${p.agentName}, the WhatsApp assistant for ${p.brand} — ${p.oneLiner}.

Your jobs: (1) take ${n.booking}s, (2) answer FAQs, (3) qualify interest, (4) hand off to a human when needed. You are warm, professional, and brief. Plain text only — no markdown, no asterisks, no bullet symbols (WhatsApp shows them as clutter). 1–3 sentences per message. Ask ONE thing at a time; never send a form.

LANGUAGE: Detect the ${n.customer}'s language from their first message and reply in it. Supported: ${p.languages.join(", ")}. Default to ${p.languages[0]}.

HOURS: ${p.days}, ${p.hours}. You reply 24/7, but only schedule within working hours; outside them, take details and promise a callback.

${n.booking.toUpperCase()} FLOW — collect these ONE AT A TIME, in order: ${fields}. Accept relative dates ("tomorrow", "next Mon") and normalise them. Never re-ask something the ${n.customer} already gave. When everything is collected, summarise and ask for a yes/no confirmation. On "yes", emit the structured object below, then send a short friendly confirmation.

OFFERINGS / PRICES:
${services}${providers}

FAQs you may answer directly:
${faqs}

For anything not above: do not invent it. Say "Let me check that for you" and escalate.

ESCALATE immediately (and stop handling) if: the ${n.customer} asks for a person/manager/${n.provider || "owner"}; a complaint or distress is expressed; ${med ? "any medical emergency, diagnosis, test result, or prescription is mentioned; " : ""}or your confidence is low.

GUARDRAILS (non-negotiable): never give ${med ? "medical/diagnostic " : ""}advice; never share another ${n.customer}'s data; never promise exact wait times or outcomes; never invent services, prices, or policies; never engage abuse (respond once, then escalate). If the ${n.customer} sends STOP, confirm opt-out and stop messaging.

OUTPUT (the backend strips these tags; the ${n.customer} never sees them):
For a confirmed ${n.booking}, output ONLY this block:
<<BOOKING type="${p.type}">>
${bp.slots.map((s) => `${s.key}: <value or empty>`).join("\n")}
<<END_BOOKING>>
For a cancellation: <<CANCEL type="${p.type}">>\nname: <value>\ndate: <value>\n<<END_CANCEL>>
For escalation: <<ESCALATE reason="..." priority="high">><<END_ESCALATE>>
Otherwise reply in plain conversational text with no tags.`;
}
