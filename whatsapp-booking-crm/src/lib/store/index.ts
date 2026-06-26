/* ============================================================================
 * Store — minimal persistence for profiles, conversation sessions, contacts
 * and a booking log.
 *
 * Default implementation: in-memory, with a best-effort JSON file fallback in
 * dev (.data/store.json) so a restart doesn't wipe a test conversation. This is
 * intentionally swappable: implement the same `Store` interface backed by
 * Supabase / Postgres / Redis for production and export it from here.
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
}

interface DBShape {
  /** The active business profile keyed by id ("default" for the single-tenant). */
  profiles: Record<string, BusinessProfile>;
  sessions: Record<string, Session>; // keyed by `${profileId}:${phone}`
  contacts: Record<string, Contact>; // keyed by phone
  messages: Record<string, StoredMessage[]>; // keyed by `${profileId}:${phone}`
  bookings: BookingRecord[];
}

const DATA_DIR = path.join(process.cwd(), ".data");
const DATA_FILE = path.join(DATA_DIR, "store.json");

const db: DBShape = {
  profiles: { default: PRESETS.dental },
  sessions: {},
  contacts: {},
  messages: {},
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

// ─── Profiles ───────────────────────────────────────────────────────────────

export async function getProfile(id = "default"): Promise<BusinessProfile> {
  await load();
  return db.profiles[id] ?? PRESETS.dental;
}

export async function saveProfile(profile: BusinessProfile, id = "default"): Promise<void> {
  await load();
  db.profiles[id] = { ...profile, id };
  await persist();
}

// ─── Sessions ───────────────────────────────────────────────────────────────

export async function getSession(phone: string, profileId = "default"): Promise<Session> {
  await load();
  return db.sessions[`${profileId}:${phone}`] ?? newSession();
}

export async function saveSession(phone: string, session: Session, profileId = "default"): Promise<void> {
  await load();
  db.sessions[`${profileId}:${phone}`] = session;
  await persist();
}

export async function resetSession(phone: string, profileId = "default"): Promise<void> {
  await load();
  delete db.sessions[`${profileId}:${phone}`];
  delete db.messages[`${profileId}:${phone}`];
  await persist();
}

// ─── Conversation history (for the AI context window) ───────────────────────

export async function getHistory(phone: string, profileId = "default", limit = 12): Promise<StoredMessage[]> {
  await load();
  const all = db.messages[`${profileId}:${phone}`] ?? [];
  return all.slice(-limit);
}

export async function appendHistory(
  phone: string,
  msg: Omit<StoredMessage, "at">,
  profileId = "default",
): Promise<void> {
  await load();
  const key = `${profileId}:${phone}`;
  (db.messages[key] ??= []).push({ ...msg, at: new Date().toISOString() });
  // Keep history bounded.
  if (db.messages[key].length > 40) db.messages[key] = db.messages[key].slice(-40);
  await persist();
}

// ─── Contacts ───────────────────────────────────────────────────────────────

export async function upsertContact(phone: string, patch: Partial<Contact> = {}): Promise<Contact> {
  await load();
  const now = new Date().toISOString();
  const existing = db.contacts[phone];
  const contact: Contact = existing
    ? { ...existing, ...patch, tags: patch.tags ?? existing.tags, lastSeen: now }
    : { phone, tags: patch.tags ?? [], createdAt: now, lastSeen: now, ...patch };
  db.contacts[phone] = contact;
  await persist();
  return contact;
}

export async function tagContact(phone: string, tag: string): Promise<void> {
  const c = await upsertContact(phone);
  if (!c.tags.includes(tag)) {
    c.tags.push(tag);
    await persist();
  }
}

export async function listContacts(): Promise<Contact[]> {
  await load();
  return Object.values(db.contacts).sort((a, b) => b.lastSeen.localeCompare(a.lastSeen));
}

// ─── Bookings ───────────────────────────────────────────────────────────────

export async function logBooking(rec: Omit<BookingRecord, "id" | "createdAt">): Promise<BookingRecord> {
  await load();
  const full: BookingRecord = { ...rec, id: crypto.randomUUID(), createdAt: new Date().toISOString() };
  db.bookings.push(full);
  await persist();
  return full;
}

export async function listBookings(): Promise<BookingRecord[]> {
  await load();
  return [...db.bookings].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export async function updateBookingStatus(id: string, status: BookingRecord["status"]): Promise<void> {
  await load();
  const b = db.bookings.find((x) => x.id === id);
  if (b) {
    b.status = status;
    await persist();
  }
}
