/* ============================================================================
 * Conversation orchestrator — the single brain both the live WhatsApp webhook
 * and the in-app simulator call.
 *
 * Two layers, exactly as the integration guide describes:
 *   • Deterministic FSM (src/lib/engine) — guarantees a booking flow always
 *     completes and always emits a clean structured object. This is the default
 *     and the source of truth for tags/side-effects.
 *   • LLM layer (Gemini → OpenAI) — optional. When enabled and configured, it
 *     wraps the flow for fuzzy, natural-language understanding; on any failure
 *     it falls back to the FSM so a broken/missing AI never blocks a booking.
 *
 * Side-effects (booking, cancellation, escalation, opt-out) are persisted and
 * synced to Google Sheets/Calendar here, regardless of which layer produced
 * the reply.
 * ==========================================================================*/

import {
  generateSystemPrompt,
  isOpenNow,
  newSession,
  step,
  type BusinessProfile,
  type EngineReply,
  type Session,
} from "@/lib/engine";
import { parseAiOutput } from "@/lib/engine/parse-tags";
import { normalizeDate } from "@/lib/dates";
import { aiConfigured, aiReply, type ChatTurn } from "@/services/ai-service";
import { syncToSheets } from "@/lib/sheets-sync";
import {
  appendHistory,
  getHistory,
  getProfile,
  getSession,
  logBooking,
  resetSession,
  saveSession,
  tagContact,
  upsertContact,
} from "@/lib/store";

export type Mode = "auto" | "deterministic" | "ai";

export interface HandleInput {
  phone: string;
  text: string;
  profileId?: string;
  /** Override the configured profile (used by the stateless simulator). */
  profileOverride?: BusinessProfile;
  /** Provide/seed session externally (stateless simulator). */
  session?: Session;
  mode?: Mode;
  now?: Date;
  /** Skip persistence/sync (pure preview, e.g. simulator). */
  dryRun?: boolean;
}

export interface HandleResult {
  reply: string;
  session: Session;
  provider: string; // "engine" | "gemini-1.5-flash" | ...
  booking?: Record<string, string>;
  cancel?: { name?: string; date?: string };
  escalate?: string;
  optOut?: boolean;
}

/** Decide whether to attempt the AI layer for this turn. */
function useAi(mode: Mode): boolean {
  if (mode === "deterministic") return false;
  if (mode === "ai") return aiConfigured();
  return aiConfigured(); // "auto": AI when keys exist, else FSM
}

export async function handleIncoming(input: HandleInput): Promise<HandleResult> {
  const profileId = input.profileId ?? "default";
  const profile = input.profileOverride ?? (await getProfile(profileId));
  const mode: Mode = input.mode ?? "auto";
  const now = input.now ?? new Date();

  const session: Session = input.session ?? (input.dryRun ? newSession() : await getSession(input.phone, profileId));

  // START re-subscribes an opted-out contact.
  if (/^\s*start\s*$/i.test(input.text)) {
    if (!input.dryRun) {
      await upsertContact(input.phone, { optedOut: false });
      await resetSession(input.phone, profileId);
    }
    return { reply: "You're re-subscribed. How can I help you today?", session: newSession(), provider: "engine" };
  }

  let result: HandleResult;

  if (useAi(mode)) {
    result = await runAiTurn(profile, session, input, now);
  } else {
    result = runEngineTurn(profile, session, input.text, now);
  }

  if (!input.dryRun) {
    await persistTurn(profileId, input.phone, input.text, result, profile);
  }
  return result;
}

// ─── Deterministic layer ────────────────────────────────────────────────────

function runEngineTurn(profile: BusinessProfile, session: Session, text: string, now: Date): HandleResult {
  const out: EngineReply = step(session, text, profile, { now });
  return {
    reply: out.reply,
    session: out.session,
    provider: "engine",
    booking: out.booking,
    cancel: out.cancel,
    escalate: out.escalate,
    optOut: out.optOut,
  };
}

// ─── AI layer (with FSM fallback) ───────────────────────────────────────────

async function runAiTurn(
  profile: BusinessProfile,
  session: Session,
  input: HandleInput,
  now: Date,
): Promise<HandleResult> {
  const history: ChatTurn[] = input.session
    ? [] // stateless simulator: no server history
    : (await getHistory(input.phone, input.profileId ?? "default")).map((m) => ({ role: m.role, content: m.content }));
  history.push({ role: "user", content: input.text });

  let system = generateSystemPrompt(profile);
  if (!isOpenNow(profile, now)) {
    system += `\n\nNOTE: It is currently OUTSIDE working hours. Take details and promise a callback rather than confirming an exact slot.`;
  }

  const ai = await aiReply(system, history);
  if (!ai) {
    // Provider missing or all failed → deterministic guarantee.
    return runEngineTurn(profile, session, input.text, now);
  }

  const parsed = parseAiOutput(ai.text);
  // Detect an explicit human request even if the model didn't emit a tag.
  const escalate = parsed.escalate?.reason;

  return {
    reply: parsed.reply || "Let me check that for you and a team member will follow up shortly.",
    session, // FSM session is left as-is in AI mode; history carries the state
    provider: ai.provider,
    booking: parsed.booking,
    cancel: parsed.cancel,
    escalate,
  };
}

// ─── Persistence + side-effects ─────────────────────────────────────────────

async function persistTurn(
  profileId: string,
  phone: string,
  userText: string,
  result: HandleResult,
  profile: BusinessProfile,
): Promise<void> {
  await saveSession(phone, result.session, profileId);
  await appendHistory(phone, { role: "user", content: userText }, profileId);
  await appendHistory(phone, { role: "assistant", content: result.reply }, profileId);

  const contact = await upsertContact(phone, { name: result.booking?.name });

  // First-time contact tag (Recipe A).
  if (contact.tags.length === 0) await tagContact(phone, "new-lead");

  if (result.optOut) {
    await upsertContact(phone, { optedOut: true });
    await tagContact(phone, "opted-out");
  }

  if (result.escalate) await tagContact(phone, "needs-human");

  if (result.booking) {
    const fields = result.booking;
    const rawDate = fields.date || fields.checkin || "";
    const forDate = rawDate ? normalizeDate(rawDate) : undefined;
    await logBooking({
      contactPhone: phone,
      type: fields.type || profile.type,
      fields,
      status: "confirmed",
      forDate,
    });
    await tagContact(phone, "appointment_confirmed");
    await syncToSheets({
      event: "booking",
      type: fields.type || profile.type,
      contact: phone,
      fields,
      forDate,
      at: new Date().toISOString(),
    });
  }

  if (result.cancel) {
    await tagContact(phone, "cancellation");
    await syncToSheets({
      event: "cancellation",
      type: profile.type,
      contact: phone,
      fields: { name: result.cancel.name ?? "", date: result.cancel.date ?? "" },
      at: new Date().toISOString(),
    });
  }
}

// Re-export so the simulator route can build a fresh session.
export { newSession };
