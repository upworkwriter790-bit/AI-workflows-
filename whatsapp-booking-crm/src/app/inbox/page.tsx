"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface Convo {
  phone: string;
  name?: string;
  tags: string[];
  optedOut?: boolean;
  paused: boolean;
  lastMessage: string;
  lastAt: string;
  phase: string;
}
interface Business { id: string; brand: string; type: string }
interface Thread {
  phone: string;
  messages: { role: "user" | "assistant"; content: string; at: string; via?: string }[];
  contact: { name?: string; tags: string[]; optedOut?: boolean } | null;
  phase: string;
  paused: boolean;
}

export default function Inbox() {
  const [business, setBusiness] = useState("default");
  const [businesses, setBusinesses] = useState<Business[]>([]);
  const [convos, setConvos] = useState<Convo[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [thread, setThread] = useState<Thread | null>(null);
  const [reply, setReply] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadList = useCallback(async () => {
    const r = await fetch(`/api/inbox?business=${business}`);
    const d = await r.json();
    setConvos(d.conversations ?? []);
    setBusinesses(d.businesses ?? []);
  }, [business]);

  const loadThread = useCallback(async (phone: string) => {
    const r = await fetch(`/api/inbox/thread?business=${business}&phone=${encodeURIComponent(phone)}`);
    setThread(await r.json());
    requestAnimationFrame(() => bottomRef.current?.scrollIntoView());
  }, [business]);

  useEffect(() => { loadList(); }, [loadList]);
  useEffect(() => { if (active) loadThread(active); }, [active, loadThread]);

  // Light polling so live inbound messages appear.
  useEffect(() => {
    const t = setInterval(() => { loadList(); if (active) loadThread(active); }, 8000);
    return () => clearInterval(t);
  }, [active, loadList, loadThread]);

  const send = async () => {
    if (!active || !reply.trim()) return;
    setSending(true);
    await fetch("/api/inbox/reply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ business, phone: active, text: reply }),
    });
    setReply("");
    setSending(false);
    await loadThread(active);
    await loadList();
  };

  const togglePause = async () => {
    if (!active || !thread) return;
    await fetch("/api/inbox/pause", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ business, phone: active, paused: !thread.paused }),
    });
    await loadThread(active);
    await loadList();
  };

  return (
    <main className="mx-auto max-w-6xl px-5 pb-16">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight">Inbox</h1>
          <p className="mt-1 text-[15px] text-ink-soft">Live conversations. Reply manually to take over from the bot, or hand it back.</p>
        </div>
        <select
          value={business}
          onChange={(e) => { setBusiness(e.target.value); setActive(null); setThread(null); }}
          className="rounded-lg border border-line bg-white px-3 py-2 text-sm"
        >
          {(businesses.length ? businesses : [{ id: "default", brand: "Default", type: "" }]).map((b) => (
            <option key={b.id} value={b.id}>{b.brand}</option>
          ))}
        </select>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-[280px_1fr]">
        {/* conversation list */}
        <div className="overflow-hidden rounded-xl border border-line bg-white">
          {convos.length === 0 ? (
            <p className="p-4 text-sm text-ink-soft">No conversations yet. Send a message to your WhatsApp number (or run the Builder simulator with a saved business).</p>
          ) : (
            convos.map((c) => (
              <button
                key={c.phone}
                onClick={() => setActive(c.phone)}
                className={`block w-full border-b border-line px-3 py-2.5 text-left transition hover:bg-[#fbfcfb] ${active === c.phone ? "bg-accent-wash" : ""}`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-ink">{c.name || c.phone}</span>
                  {c.paused && <span className="rounded bg-warn-wash px-1.5 py-0.5 text-[10px] font-semibold text-warn">human</span>}
                </div>
                <div className="mt-0.5 truncate text-xs text-ink-soft">{c.lastMessage}</div>
                <div className="mt-1 flex flex-wrap gap-1">
                  {c.optedOut && <span className="rounded bg-[#f2f4f2] px-1.5 py-0.5 text-[10px] text-ink-soft">opted-out</span>}
                  {c.tags.slice(0, 3).map((t) => (
                    <span key={t} className="rounded bg-[#f2f4f2] px-1.5 py-0.5 text-[10px] text-ink-soft">{t}</span>
                  ))}
                </div>
              </button>
            ))
          )}
        </div>

        {/* thread */}
        <div className="flex min-h-[520px] flex-col overflow-hidden rounded-xl border border-line bg-white">
          {!thread ? (
            <div className="grid flex-1 place-items-center text-sm text-ink-soft">Select a conversation</div>
          ) : (
            <>
              <div className="flex items-center justify-between border-b border-line px-4 py-3">
                <div>
                  <div className="text-sm font-semibold text-ink">{thread.contact?.name || thread.phone}</div>
                  <div className="text-xs text-ink-soft">{thread.phone} · flow: {thread.phase}</div>
                </div>
                <button
                  onClick={togglePause}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${thread.paused ? "bg-accent text-white hover:bg-accent-ink" : "bg-[#f2f4f2] text-ink-soft hover:bg-[#e6ebe6]"}`}
                >
                  {thread.paused ? "▶ Resume bot" : "⏸ Take over"}
                </button>
              </div>

              <div className="chat-scroll flex flex-1 flex-col gap-1.5 overflow-y-auto bg-[#f6f8f6] p-4">
                {thread.messages.map((m, i) => (
                  <div
                    key={i}
                    className={`max-w-[75%] whitespace-pre-wrap rounded-lg px-3 py-2 text-[13.5px] ${
                      m.role === "user"
                        ? "self-start border border-line bg-white text-ink"
                        : m.via === "human"
                          ? "self-end bg-[#0a6b4e] text-white"
                          : "self-end bg-accent text-white"
                    }`}
                  >
                    {m.content}
                    <span className="mt-0.5 block text-right text-[10px] opacity-70">
                      {m.role === "assistant" ? (m.via === "human" ? "agent · " : "bot · ") : ""}
                      {new Date(m.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                ))}
                <div ref={bottomRef} />
              </div>

              <div className="flex items-center gap-2 border-t border-line p-3">
                <input
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && send()}
                  placeholder="Type a reply as the agent…"
                  className="flex-1 rounded-lg border border-line px-3 py-2 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent-wash"
                />
                <button
                  onClick={send}
                  disabled={sending}
                  className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-accent-ink disabled:opacity-50"
                >
                  {sending ? "…" : "Send"}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </main>
  );
}
