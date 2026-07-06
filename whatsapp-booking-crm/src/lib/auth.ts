/* ============================================================================
 * Lightweight admin auth.
 *
 * If ADMIN_PASSWORD is set, the CRM pages + data APIs require a session cookie
 * obtained by logging in. If it is NOT set, auth is disabled (local/demo mode)
 * and everything is open. Uses Web Crypto (SHA-256) so the same token can be
 * computed in both the Edge middleware and Node route handlers.
 *
 * The cookie stores a salted hash of the password, never the password itself.
 * ==========================================================================*/

const SALT = "wa-booking-crm/session/v1";
export const SESSION_COOKIE = "wa_session";

export function authEnabled(): boolean {
  return !!process.env.ADMIN_PASSWORD;
}

export async function sessionToken(): Promise<string> {
  const pw = process.env.ADMIN_PASSWORD || "";
  const data = new TextEncoder().encode(`${SALT}:${pw}`);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function isValidSession(token: string | undefined): Promise<boolean> {
  if (!authEnabled()) return true;
  if (!token) return false;
  const expected = await sessionToken();
  return token.length === expected.length && timingSafeEqualHex(token, expected);
}

function timingSafeEqualHex(a: string, b: string): boolean {
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
