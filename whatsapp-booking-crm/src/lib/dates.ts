/* ============================================================================
 * Lightweight natural-language date normalisation.
 *
 * Turns "tomorrow", "next monday", "15 July", "12/08" into an ISO yyyy-mm-dd
 * when confident. Used to schedule reminders and to store a sortable `forDate`.
 * Returns undefined when it can't parse — callers keep the raw string too.
 * ==========================================================================*/

const DAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
const MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];

function iso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function normalizeDate(input: string, now = new Date()): string | undefined {
  const s = input.toLowerCase().trim();
  const base = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  if (/\btoday\b/.test(s)) return iso(base);
  if (/\btomorrow\b/.test(s)) return iso(new Date(base.getTime() + 864e5));
  if (/\bday after\b/.test(s)) return iso(new Date(base.getTime() + 2 * 864e5));

  // Weekday, optionally "next"
  const wd = DAYS.findIndex((d) => new RegExp(`\\b${d}`).test(s));
  if (wd >= 0) {
    let delta = (wd - base.getDay() + 7) % 7;
    if (delta === 0 || /\bnext\b/.test(s)) delta = delta === 0 ? 7 : delta;
    if (/\bnext\b/.test(s) && delta < 7) delta += 0; // "next mon" ≈ upcoming mon
    return iso(new Date(base.getTime() + delta * 864e5));
  }

  // "15 July" / "15th Jul"
  const dm = s.match(/\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3,})/);
  if (dm) {
    const day = Number(dm[1]);
    const mon = MONTHS.findIndex((m) => dm[2].startsWith(m));
    if (mon >= 0 && day >= 1 && day <= 31) {
      let year = now.getFullYear();
      const cand = new Date(year, mon, day);
      if (cand < base) year += 1;
      return iso(new Date(year, mon, day));
    }
  }

  // dd/mm or dd-mm
  const num = s.match(/\b(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?\b/);
  if (num) {
    const day = Number(num[1]);
    const mon = Number(num[2]) - 1;
    let year = num[3] ? Number(num[3]) : now.getFullYear();
    if (year < 100) year += 2000;
    if (mon >= 0 && mon <= 11 && day >= 1 && day <= 31) {
      let cand = new Date(year, mon, day);
      if (!num[3] && cand < base) cand = new Date(year + 1, mon, day);
      return iso(cand);
    }
  }

  return undefined;
}

/** Days between two ISO dates (b - a), or null if unparseable. */
export function daysBetween(aIso: string, bIso: string): number | null {
  const a = Date.parse(aIso);
  const b = Date.parse(bIso);
  if (Number.isNaN(a) || Number.isNaN(b)) return null;
  return Math.round((a - b) / 864e5);
}
