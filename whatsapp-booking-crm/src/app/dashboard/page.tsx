"use client";

import { useEffect, useState } from "react";

interface DashData {
  bookings: { id: string; contactPhone: string; type: string; fields: Record<string, string>; status: string; createdAt: string; forDate?: string }[];
  contacts: { phone: string; name?: string; tags: string[]; optedOut?: boolean; lastSeen: string }[];
  counts: { bookings: number; contacts: number; confirmed: number };
  integrations: { whatsapp: boolean; ai: boolean; sheets: boolean };
}

export default function Dashboard() {
  const [data, setData] = useState<DashData | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    fetch("/api/dashboard")
      .then((r) => r.json())
      .then(setData)
      .catch(() => setErr(true));
  }, []);

  if (err) return <Wrap><p className="text-ink-soft">Could not load dashboard.</p></Wrap>;
  if (!data) return <Wrap><p className="text-ink-soft">Loading…</p></Wrap>;

  return (
    <Wrap>
      <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight">Dashboard</h1>
      <p className="mt-1 text-[15px] text-ink-soft">
        Live bookings, contacts and integration status. Data here is produced by the same engine the WhatsApp webhook runs.
      </p>

      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Bookings" value={data.counts.bookings} />
        <Stat label="Confirmed" value={data.counts.confirmed} />
        <Stat label="Contacts" value={data.counts.contacts} />
        <Stat label="Opted out" value={data.contacts.filter((c) => c.optedOut).length} />
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Pill on={data.integrations.whatsapp} label="WhatsApp Cloud API" />
        <Pill on={data.integrations.ai} label="AI auto-reply (Gemini/OpenAI)" />
        <Pill on={data.integrations.sheets} label="Google Sheets sync" />
      </div>

      <section className="mt-8">
        <h2 className="font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-wide text-ink">Recent bookings</h2>
        <div className="mt-2 overflow-hidden rounded-xl border border-line bg-white">
          {data.bookings.length === 0 ? (
            <p className="p-4 text-sm text-ink-soft">
              No bookings yet. Run a booking to completion in the Builder, then save the profile — live conversations land here.
            </p>
          ) : (
            <table className="w-full text-left text-sm">
              <thead className="bg-[#fbfcfb] text-[11px] uppercase tracking-wide text-ink-soft">
                <tr>
                  <Th>When</Th><Th>Type</Th><Th>Details</Th><Th>For</Th><Th>Status</Th>
                </tr>
              </thead>
              <tbody>
                {data.bookings.map((b) => (
                  <tr key={b.id} className="border-t border-line">
                    <Td>{new Date(b.createdAt).toLocaleString()}</Td>
                    <Td><span className="rounded bg-accent-wash px-1.5 py-0.5 text-[11px] font-semibold text-accent-ink">{b.type}</span></Td>
                    <Td className="text-ink-soft">{summarize(b.fields)}</Td>
                    <Td>{b.forDate ?? "—"}</Td>
                    <Td>{b.status}</Td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      <section className="mt-8">
        <h2 className="font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-wide text-ink">Contacts</h2>
        <div className="mt-2 overflow-hidden rounded-xl border border-line bg-white">
          {data.contacts.length === 0 ? (
            <p className="p-4 text-sm text-ink-soft">No contacts yet.</p>
          ) : (
            <table className="w-full text-left text-sm">
              <thead className="bg-[#fbfcfb] text-[11px] uppercase tracking-wide text-ink-soft">
                <tr><Th>Phone</Th><Th>Name</Th><Th>Tags</Th><Th>Last seen</Th></tr>
              </thead>
              <tbody>
                {data.contacts.map((c) => (
                  <tr key={c.phone} className="border-t border-line">
                    <Td>{c.phone}</Td>
                    <Td>{c.name ?? "—"}</Td>
                    <Td>
                      <span className="flex flex-wrap gap-1">
                        {c.tags.map((t) => (
                          <span key={t} className="rounded bg-[#f2f4f2] px-1.5 py-0.5 text-[11px] text-ink-soft">{t}</span>
                        ))}
                      </span>
                    </Td>
                    <Td className="text-ink-soft">{new Date(c.lastSeen).toLocaleString()}</Td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </Wrap>
  );
}

function summarize(f: Record<string, string>): string {
  return Object.entries(f)
    .filter(([k]) => k !== "type")
    .map(([k, v]) => `${k}: ${v}`)
    .join(" · ");
}

const Wrap = ({ children }: { children: React.ReactNode }) => (
  <main className="mx-auto max-w-6xl px-5 pb-16">{children}</main>
);
const Stat = ({ label, value }: { label: string; value: number }) => (
  <div className="rounded-xl border border-line bg-white p-4">
    <div className="font-[family-name:var(--font-display)] text-2xl font-bold text-ink">{value}</div>
    <div className="text-xs uppercase tracking-wide text-ink-soft">{label}</div>
  </div>
);
const Pill = ({ on, label }: { on: boolean; label: string }) => (
  <span className={`rounded-full px-3 py-1 text-xs font-semibold ${on ? "bg-accent-wash text-accent-ink" : "bg-[#f2f4f2] text-ink-soft"}`}>
    {on ? "● " : "○ "}{label}
  </span>
);
const Th = ({ children }: { children: React.ReactNode }) => <th className="px-3 py-2 font-semibold">{children}</th>;
const Td = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <td className={`px-3 py-2 ${className}`}>{children}</td>
);
