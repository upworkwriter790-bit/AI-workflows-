/* ============================================================================
 * Parse the structured control tags the AI emits, and strip them so the
 * customer only ever sees clean conversational text.
 *
 * Tags handled:
 *   <<BOOKING type="clinic">> key: value ... <<END_BOOKING>>
 *   <<CANCEL type="clinic">>  name: ... date: ... <<END_CANCEL>>
 *   <<ESCALATE reason="..." priority="high">><<END_ESCALATE>>
 * ==========================================================================*/

import type { VerticalKey } from "./types";

export interface ParsedAi {
  /** The message to actually send the customer (tags removed). */
  reply: string;
  booking?: Record<string, string> & { type?: VerticalKey };
  cancel?: { type?: VerticalKey; name?: string; date?: string };
  escalate?: { reason?: string; priority?: string };
}

const BOOKING_RE = /<<BOOKING([^>]*)>>([\s\S]*?)<<END_BOOKING>>/i;
const CANCEL_RE = /<<CANCEL([^>]*)>>([\s\S]*?)<<END_CANCEL>>/i;
const ESCALATE_RE = /<<ESCALATE([^>]*)>>([\s\S]*?)<<END_ESCALATE>>/i;

function attr(raw: string, name: string): string | undefined {
  const m = raw.match(new RegExp(`${name}\\s*=\\s*"([^"]*)"`, "i"));
  return m?.[1];
}

/** Parse `key: value` lines into an object, ignoring empty values. */
function kvLines(block: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of block.split("\n")) {
    const m = line.match(/^\s*([a-zA-Z_]+)\s*:\s*(.+?)\s*$/);
    if (!m) continue;
    const val = m[2].trim();
    // Skip unfilled template placeholders like `<value or empty>`.
    if (/^<.*>$/.test(val)) continue;
    if (val && val.toLowerCase() !== "empty") out[m[1]] = val;
  }
  return out;
}

export function parseAiOutput(text: string): ParsedAi {
  const result: ParsedAi = { reply: text };

  const booking = text.match(BOOKING_RE);
  if (booking) {
    const fields = kvLines(booking[2]);
    const type = attr(booking[1], "type") as VerticalKey | undefined;
    result.booking = { ...fields, ...(type ? { type } : {}) };
  }

  const cancel = text.match(CANCEL_RE);
  if (cancel) {
    const fields = kvLines(cancel[2]);
    result.cancel = {
      type: attr(cancel[1], "type") as VerticalKey | undefined,
      name: fields.name,
      date: fields.date,
    };
  }

  const escalate = text.match(ESCALATE_RE);
  if (escalate) {
    result.escalate = {
      reason: attr(escalate[1], "reason") || "unspecified",
      priority: attr(escalate[1], "priority") || "normal",
    };
  }

  // Strip every tag block and tidy whitespace.
  result.reply = text
    .replace(BOOKING_RE, "")
    .replace(CANCEL_RE, "")
    .replace(ESCALATE_RE, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  return result;
}
