/* ============================================================================
 * Engine types — the shared vocabulary for the multi-vertical booking engine.
 * ==========================================================================*/

export type VerticalKey =
  | "clinic"
  | "dental"
  | "salon"
  | "hotel"
  | "restaurant"
  | "retail"
  | "travel"
  | "fitness"
  | "automotive"
  | "generic";

export type SlotKind =
  | "text"
  | "choice"
  | "date"
  | "time"
  | "number"
  | "phone"
  | "fulfil"; // pickup vs delivery (retail)

export interface SlotDef {
  /** Stored field name in the booking object. */
  key: string;
  kind: SlotKind;
  /** Question shown to the customer. */
  ask: string;
  /** Pull selectable choices from the profile. */
  optionsFrom?: "services" | "providers" | "slots";
  optional?: boolean;
  /** Only ask this slot if a prior answer matches. */
  dependsOn?: { key: string; equals: string };
}

export interface Blueprint {
  key: VerticalKey;
  label: string;
  icon: string;
  /** Vocabulary so prompts/messages read native to the trade. */
  noun: { booking: string; customer: string; provider?: string; item: string };
  slots: SlotDef[];
  confirm: (b: Booking, p: BusinessProfile) => string;
  done: (b: Booking, p: BusinessProfile) => string;
  /** Labels used by the dashboard so steps relabel per vertical. */
  labels: { providers: string; services: string };
}

export interface PricedItem {
  name: string;
  price?: string;
  note?: string;
}

export interface BusinessHours {
  /** 0=Sun … 6=Sat. */
  days: number[];
  open: string; // "HH:MM" 24h
  close: string; // "HH:MM" 24h
}

export interface BusinessProfile {
  id?: string;
  /** Meta WhatsApp phone-number ID this business receives messages on (routing). */
  phoneNumberId?: string;
  type: VerticalKey;
  brand: string;
  agentName: string;
  oneLiner: string;
  languages: string[];
  days: string; // human readable, e.g. "Mon–Sat"
  hours: string; // human readable, e.g. "9 AM – 7 PM"
  slots: string[]; // selectable times
  providers?: string[];
  services: PricedItem[];
  address?: string;
  mapsUrl?: string;
  faqs?: { q: string; a: string }[];
  escalationPhone?: string;
  delivery?: boolean; // retail
  /** Optional structured hours for the after-hours guardrail. */
  businessHours?: BusinessHours;
}

export type Booking = Record<string, string>;

export type Phase =
  | "greeting"
  | "detect"
  | "collecting"
  | "confirm"
  | "cancelling"
  | "done"
  | "escalated"
  | "opted_out";

export interface Session {
  phase: Phase;
  booking: Booking;
  slotIdx: number;
  turns: number;
  /** Set once if the conversation opened outside working hours. */
  afterHours?: boolean;
  optedOut?: boolean;
}

/** A clean structured booking the backend can persist / sync. */
export interface BookingResult extends Booking {
  type: VerticalKey;
}

export interface CancelResult {
  type: VerticalKey;
  name: string;
  date: string;
}

export interface EngineReply {
  reply: string;
  session: Session;
  /** Present only when a booking just completed. */
  booking?: BookingResult;
  /** Present only when a cancellation was captured. */
  cancel?: CancelResult;
  /** Present when the conversation should be handed to a human. */
  escalate?: string;
  /** Present when the customer opted out of messaging. */
  optOut?: boolean;
}

export interface Runtime {
  /** Override "now" (tests / simulator). */
  now?: Date;
}
