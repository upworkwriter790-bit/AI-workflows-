"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface Integrations { whatsapp: boolean; ai: boolean; sheets: boolean }
interface Business { id: string; brand: string; type: string; phoneNumberId?: string }

export default function Settings() {
  const router = useRouter();
  const [integrations, setIntegrations] = useState<Integrations | null>(null);
  const [businesses, setBusinesses] = useState<Business[]>([]);
  const [origin, setOrigin] = useState("");

  useEffect(() => {
    setOrigin(window.location.origin);
    fetch("/api/dashboard").then((r) => r.json()).then((d) => setIntegrations(d.integrations)).catch(() => {});
    fetch("/api/profile").then((r) => r.json()).then((d) => setBusinesses(d.businesses ?? [])).catch(() => {});
  }, []);

  const logout = async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  };

  const webhookUrl = origin ? `${origin}/api/whatsapp/webhook` : "/api/whatsapp/webhook";

  return (
    <main className="mx-auto max-w-6xl px-5 pb-16">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight">Settings</h1>
          <p className="mt-1 text-[15px] text-ink-soft">Integration status, WhatsApp webhook, and your businesses.</p>
        </div>
        <button onClick={logout} className="rounded-lg border border-line bg-white px-3 py-1.5 text-sm font-medium text-ink-soft hover:bg-[#fbfcfb]">
          Log out
        </button>
      </div>

      <section className="mt-6">
        <h2 className="text-sm font-bold uppercase tracking-wide text-ink">Integrations</h2>
        <div className="mt-2 grid gap-3 sm:grid-cols-3">
          <IntCard on={integrations?.whatsapp} label="WhatsApp Cloud API" help="Set WHATSAPP_ACCESS_TOKEN + WHATSAPP_PHONE_NUMBER_ID" />
          <IntCard on={integrations?.ai} label="AI auto-reply" help="Set GEMINI_API_KEY and/or OPENAI_API_KEY" />
          <IntCard on={integrations?.sheets} label="Google Sheets / Calendar" help="Set GOOGLE_SHEETS_WEBHOOK_URL" />
        </div>
      </section>

      <section className="mt-8">
        <h2 className="text-sm font-bold uppercase tracking-wide text-ink">WhatsApp webhook</h2>
        <div className="mt-2 rounded-xl border border-line bg-white p-4 text-sm">
          <p className="text-ink-soft">In Meta → WhatsApp → Configuration, set the callback URL to:</p>
          <code className="mt-1 block break-all rounded-lg bg-[#0f1a16] px-3 py-2 text-[13px] text-[#cfe7dc]">{webhookUrl}</code>
          <p className="mt-2 text-ink-soft">Verify token = your <code>WHATSAPP_VERIFY_TOKEN</code>. Subscribe to the <b>messages</b> field.</p>
        </div>
      </section>

      <section className="mt-8">
        <h2 className="text-sm font-bold uppercase tracking-wide text-ink">Businesses</h2>
        <div className="mt-2 overflow-hidden rounded-xl border border-line bg-white">
          {businesses.length === 0 ? (
            <p className="p-4 text-sm text-ink-soft">No businesses saved yet. Create one in the Builder.</p>
          ) : (
            <table className="w-full text-left text-sm">
              <thead className="bg-[#fbfcfb] text-[11px] uppercase tracking-wide text-ink-soft">
                <tr><th className="px-3 py-2">Business</th><th className="px-3 py-2">Type</th><th className="px-3 py-2">Phone-number ID</th></tr>
              </thead>
              <tbody>
                {businesses.map((b) => (
                  <tr key={b.id} className="border-t border-line">
                    <td className="px-3 py-2 font-medium">{b.brand}</td>
                    <td className="px-3 py-2">{b.type}</td>
                    <td className="px-3 py-2 text-ink-soft">{b.phoneNumberId || <span className="text-[#b54708]">not set — inbound won&apos;t route</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <p className="mt-2 text-xs text-ink-soft">
          Each business routes by its WhatsApp phone-number ID. Set it in the Builder so inbound messages reach the right agent.
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-sm font-bold uppercase tracking-wide text-ink">Go-live checklist</h2>
        <ul className="mt-2 space-y-1.5 text-sm text-ink-soft">
          <li>1. Add Meta credentials (token, phone-number ID, app secret, verify token) to the environment.</li>
          <li>2. Register the webhook URL above and subscribe to <b>messages</b>.</li>
          <li>3. Configure each business in the Builder and set its phone-number ID.</li>
          <li>4. (Optional) add Gemini/OpenAI keys and the Google Sheets webhook.</li>
          <li>5. Schedule <code>/api/cron/reminders</code> daily (Vercel cron is preconfigured).</li>
          <li>6. Set <code>ADMIN_PASSWORD</code> to lock the CRM (this login).</li>
        </ul>
      </section>
    </main>
  );
}

function IntCard({ on, label, help }: { on?: boolean; label: string; help: string }) {
  return (
    <div className="rounded-xl border border-line bg-white p-4">
      <div className="flex items-center gap-2">
        <span className={`h-2.5 w-2.5 rounded-full ${on ? "bg-accent" : "bg-[#d6ddd8]"}`} />
        <span className="text-sm font-semibold text-ink">{label}</span>
      </div>
      <p className="mt-1 text-xs text-ink-soft">{on ? "Configured" : help}</p>
    </div>
  );
}
