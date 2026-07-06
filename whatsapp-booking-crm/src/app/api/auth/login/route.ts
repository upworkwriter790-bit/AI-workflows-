/* Admin login — exchange the password for a session cookie. */
import { NextRequest, NextResponse } from "next/server";
import { authEnabled, sessionToken, SESSION_COOKIE } from "@/lib/auth";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  if (!authEnabled()) return NextResponse.json({ ok: true, note: "auth disabled" });

  let password = "";
  try {
    password = (await req.json()).password ?? "";
  } catch {
    return NextResponse.json({ error: "Bad JSON" }, { status: 400 });
  }

  if (password !== process.env.ADMIN_PASSWORD) {
    return NextResponse.json({ error: "Invalid password" }, { status: 401 });
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.set(SESSION_COOKIE, await sessionToken(), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 30, // 30 days
  });
  return res;
}
