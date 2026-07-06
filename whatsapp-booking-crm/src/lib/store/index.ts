/* ============================================================================
 * Store — persistence for businesses, conversations, contacts and bookings.
 *
 * Multi-business: one deployment serves many businesses (clinic, retreat,
 * shop…), each its own BusinessProfile with an id. Inbound WhatsApp messages
 * route to a business by its `phoneNumberId`. Contacts, sessions, history and
 * bookings are all scoped per business.
 *
 * Default implementation: in-memory with a JSON file fallback
 * (.data/store.json) so a normal Node host (Railway / Hostinger / a VM) keeps
 * data across restarts. The whole module is swappable for Supabase / Postgres /
 * Redis behind the same exported function signatures.
 * ==========================================================================*/

import { promises as fs } from "node:fs";
import path from "node:path";
import type { BusinessProfile, Session } from "@/lib/engine";
import { newSession } from "@/lib/engine";
import { PRESETS } from "@/lib/presets";

export interface Contact {
  phone: string;
  name?: string;
  tags: string[];
  optedOut?: boolean;
  createdAt: string;
  lastSeen: string;
}

export interface BookingRecord {
  id: string;
  profileId: string;
  contactPhone: string;
  type: string;
  fields: Record<string, string>;
  status: "confirmed" | "cancelled" | "reminded" | "attended" | "missed";
  createdAt: string;
  /** ISO date the booking is FOR, when parseable — used by the reminder cron. */
  forDate?: string;
}

export interface StoredMessage {
  role: "user" | "assistant";
  content: string;
  at: string;
  /** "bot" = engine/AI, "human" = a manual reply from the inbox. */
  via?: "bot" | "human";
}

export interface ConversationSummary {
  phone: string;
  name?: string;
  tags: string[];
  optedOut?: boolean;
  paused: boolean;
  lastMessage: string;
  lastAt: string;
  phase: string;
}

interface DBShape {
  profiles: Record<string, BusinessProfile>; // keyed by profile id
  sessions: Record<string, Session>; // keyed by `${profileId}:${phone}`
  contacts: Record<string, Contact>; // keyed by `${profileId}:${phone}`
  messages: Record<string, StoredMessage[]>; // keyed by `${profileId}:${phone}`
  paused: Record<string, boolean>; // keyed by `${profileId}:${phone}`
  bookings: BookingRecord[];
}

const DATA_DIR = path.join(process.cwd(), ".data");
const DATA_FILE = path.join(DATA_DIR, "store.json");
const key = (profileId: string, phone: string) => `${profileId}:${phone}`;

const db: DBShape = {
  profiles: { default: { ...PRESETS.dental, id: "default" } },
  sessions: {},
  contacts: {},
  messages: {},
  paused: {},
  bookings: [],
};

let loaded = false;

async function load() {
  if (loaded) return;
  loaded = true;
  try {
    const raw = await fs.readFile(DATA_FILE, "utf8");
    Object.assign(db, JSON.parse(raw));
  } catch {
    // First run / no file yet — keep defaults.
  }
}

async function persist() {
  try {
    await fs.mkdir(DATA_DIR, { recursive: true });
    await fs.writeFile(DATA_FILE, JSON.stringify(db, null, 2), "utf8");
  } catch {
    // Read-only FS (e.g. serverless) — in-memory still works for the request.
  }
}

// ─── Profiles (businesses) ──────────────────────────────────────────────────

export async function listProfiles(): Promise<BusinessProfile[]> {
  await load();
  return Object.entries(db.profiles).map(([id, p]) => ({ ...p, id }));
}

export async function getProfile(id = "default"): Promise<BusinessProfile> {
  await load();
  return db.profiles[id] ?? db.profiles.default ?? { ...PRESETS.dental, id: "default" };
}

export async function getProfileByPhoneId(phoneNumberId: string): Promise<{ id: string; profile: BusinessProfile } | null> {
  await load();
  for (const [id, p] of Object.entries(db.profiles)) {
    if (p.phoneNumberId && p.phoneNumberId === phoneNumberId) return { id, profile: { ...p, id } };
  }
  return null;
}

/** Create or update a business. Returns its id (generated when absent). */
export async function saveProfile(profile: BusinessProfile, id?: string): Promise<string> {
  await load();
  const pid = id ?? profile.id ?? (Object.keys(db.profiles).length === 0 ? "default" : crypto.randomUUID());
  db.profiles[pid] = { ...profile, id: pid };
  await persist();
  return pid;
}

export async function deleteProfile(id: string): Promise<void> {
  await load();
  if (id === "default") return; // keep at least the default slot
  delete db.profiles[id];
  for (const k of Object.keys(db.sessions)) if (k.startsWith(`${id}:`)) delete db.sessions[k];
  for (const k of Object.keys(db.messages)) if (k.startsWith(`${id}:`)) delete db.messages[k];
  for (const k of Object.keys(db.contacts)) if (k.startsWith(`${id}:`)) delete db.contacts[k];
  for (const k of Object.keys(db.paused)) if (k.startsWith(`${id}:`)) delete db.paused[k];
  db.bookings = db.bookings.filter((b) => b.profileId !== id);
  await persist();
}

// ─── Sessions ───────────────────────────────────────────────────────────────

export async function getSession(phone: string, profileId = "default"): Promise<Session> {
  await load();
  return db.sessions[key(profileId, phone)] ?? newSession();
}

export async function saveSession(phone: string, session: Session, profileId = "default"): Promise<void> {
  await load();
  db.sessions[key(profileId, phone)] = session;
  await persist();
}

export async function resetSession(phone: string, profileId = "default"): Promise<void> {
  await load();
  delete db.sessions[key(profileId, phone)];
  delete db.messages[key(profileId, phone)];
  await persist();
}

// ─── Human takeover (pause the bot for one conversation) ────────────────────

export async function isPaused(phone: string, profileId = "default"): Promise<boolean> {
  await load();
  return !!db.paused[key(profileId, phone)];
}

export async function setPaused(phone: string, paused: boolean, profileId = "default"): Promise<void> {
  await load();
  if (paused) db.paused[key(profileId, phone)] = true;
  else delete db.paused[key(profileId, phone)];
  await persist();
}

// ─── Conversation history ───────────────────────────────────────────────────

export async function getHistory(phone: string, profileId = "default", limit = 12): Promise<StoredMessage[]> {
  await load();
  const all = db.messages[key(profileId, phone)] ?? [];
  return all.slice(-limit);
}

export async function getFullHistory(phone: string, profileId = "default"): Promise<StoredMessage[]> {
  await load();
  return db.messages[key(profileId, phone)] ?? [];
}

export async function appendHistory(
  phone: string,
  msg: Omit<StoredMessage, "at">,
  profileId = "default",
): Promise<void> {
  await load();
  const k = key(profileId, phone);
  (db.messages[k] ??= []).push({ ...msg, at: new Date().toISOString() });
  if (db.messages[k].length > 200) db.messages[k] = db.messages[k].slice(-200);
  await persist();
}

// ─── Contacts ───────────────────────────────────────────────────────────────

export async function upsertContact(phone: string, profileId = "default", patch: Partial<Contact> = {}): Promise<Contact> {
  await load();
  const now = new Date().toISOString();
  const k = key(profileId, phone);
  const existing = db.contacts[k];
  const contact: Contact = existing
    ? { ...existing, ...patch, tags: patch.tags ?? existing.tags, lastSeen: now }
    : { phone, tags: patch.tags ?? [], createdAt: now, lastSeen: now, ...patch };
  db.contacts[k] = contact;
  await persist();
  return contact;
}

export async function tagContact(phone: string, tag: string, profileId = "default"): Promise<void> {
  const c = await upsertContact(phone, profileId);
  if (!c.tags.includes(tag)) {
    c.tags.push(tag);
    await persist();
  }
}

export async function getContact(phone: string, profileId = "default"): Promise<Contact | null> {
  await load();
  return db.contacts[key(profileId, phone)] ?? null;
}

export async function listContacts(profileId = "default"): Promise<Contact[]> {
  await load();
  return Object.entries(db.contacts)
    .filter(([k]) => k.startsWith(`${profileId}:`))
    .map(([, c]) => c)
    .sort((a, b) => b.lastSeen.localeCompare(a.lastSeen));
}

// ─── Conversations (inbox) ──────────────────────────────────────────────────

export async function listConversations(profileId = "default"): Promise<ConversationSummary[]> {
  await load();
  const out: ConversationSummary[] = [];
  for (const [k, msgs] of Object.entries(db.messages)) {
    if (!k.startsWith(`${profileId}:`)) continue;
    const phone = k.slice(profileId.length + 1);
    const contact = db.contacts[k];
    const last = msgs[msgs.length - 1];
    const session = db.sessions[k];
    out.push({
      phone,
      name: contact?.name,
      tags: contact?.tags ?? [],
      optedOut: contact?.optedOut,
      paused: !!db.paused[k],
      lastMessage: last?.content ?? "",
      lastAt: last?.at ?? contact?.lastSeen ?? "",
      phase: session?.phase ?? "—",
    });
  }
  return out.sort((a, b) => b.lastAt.localeCompare(a.lastAt));
}

// ─── Bookings ───────────────────────────────────────────────────────────────

export async function logBooking(rec: Omit<BookingRecord, "id" | "createdAt">): Promise<BookingRecord> {
  await load();
  const full: BookingRecord = { ...rec, id: crypto.randomUUID(), createdAt: new Date().toISOString() };
  db.bookings.push(full);
  await persist();
  return full;
}

export async function listBookings(profileId?: string): Promise<BookingRecord[]> {
  await load();
  return db.bookings
    .filter((b) => !profileId || b.profileId === profileId)
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export async function updateBookingStatus(id: string, status: BookingRecord["status"]): Promise<void> {
  await load();
  const b = db.bookings.find((x) => x.id === id);
  if (b) {
    b.status = status;
    await persist();
  }
}
