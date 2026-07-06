/* ============================================================================
 * Auth middleware — protects the CRM UI + data APIs when ADMIN_PASSWORD is set.
 * Public always: /login, /api/auth/*, the WhatsApp webhook, the simulator, and
 * the cron/broadcast endpoints (those are guarded by CRON_SECRET instead).
 * ==========================================================================*/

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { authEnabled, isValidSession, SESSION_COOKIE } from "@/lib/auth";

export async function middleware(req: NextRequest) {
  if (!authEnabled()) return NextResponse.next();

  const token = req.cookies.get(SESSION_COOKIE)?.value;
  if (await isValidSession(token)) return NextResponse.next();

  const { pathname } = req.nextUrl;
  if (pathname.startsWith("/api/")) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.searchParams.set("next", pathname);
  return NextResponse.redirect(url);
}

export const config = {
  matcher: [
    "/",
    "/dashboard/:path*",
    "/inbox/:path*",
    "/settings/:path*",
    "/api/profile",
    "/api/profile/:path*",
    "/api/inbox/:path*",
    "/api/dashboard",
  ],
};
