"use client";

/* ============================================================================
 * Builder — the "fill in your business, watch it book" page.
 *
 * Left: a config form (business type + details) that relabels itself per
 *       vertical from the blueprint vocabulary, plus a live AI system-prompt
 *       preview and a "Save as active business" button.
 * Right: a WhatsApp-style phone that drives the REAL server engine via
 *        /api/simulate — what you test here is what ships to live WhatsApp.
 * ==========================================================================*/

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  activeSlotsFor,
  BLUEPRINTS,
  generateSystemPrompt,
  newSession,
  VERTICAL_ORDER,
  type BusinessProfile,
  type Session,
  type VerticalKey,
} from "@/lib/engine";
import { PRESETS } from "@/lib/presets";

type Side = "in" | "out";
interface Msg { side: Side; text: string; t: string }
interface Receipt { kind: "idle" | "book" | "esc"; title: string; body: string }

const clone = (p: BusinessProfile): BusinessProfile => JSON.parse(JSON.stringify(p));
const nowLabel = () => {
  const d = new Date();
  let h = d.getHours();
  const m = d.getMinutes();
  const ap = h >= 12 ? "pm" : "am";
  h = h % 12 || 12;
  return `${h}:${String(m).padStart(2, "0")} ${ap}`;
};

export default function Builder() {
  const [profile, setProfile] = useState<BusinessProfile>(() => clone(PRESETS.dental));
  const [session, setSession] = useState<Session>(() => ({ ...newSession(), phase: "detect" }));
  const [messages, setMessages] = useState<Msg[]>([]);
  const [typing, setTyping] = useState(false);
  const [input, setInput] = useState("");
  const [receipt, setReceipt] = useState<Receipt>({
    kind: "idle",
    title: "Backend payload — nothing yet",
    body: "When the customer confirms, the structured object your webhook POSTs to Google Sheets / Calendar appears here.",
  });
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved">("idle");
  const [showPrompt, setShowPrompt] = useState(false);
  const chatRef = useRef<HTMLDivElement>(null);

  const bp = BLUEPRINTS[profile.type];
  const systemPrompt = useMemo(() => generateSystemPrompt(profile), [profile]);

  const scrollDown = () => {
    requestAnimationFrame(() => {
      if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
    });
  };

  const restart = useCallback((p: BusinessProfile) => {
    setSession({ ...newSession(), phase: "detect" });
    setMessages([]);
    setReceipt({
      kind: "idle",
      title: "Backend payload — nothing yet",
      body: "When the customer confirms, the structured object your webhook POSTs to Google Sheets / Calendar appears here.",
    });
    setTyping(true);
    setTimeout(() => {
      setTyping(false);
      setMessages([
        {
          side: "in",
          text: `Hi! This is ${p.agentName} from ${p.brand}. You can book right here on WhatsApp — what can I help you with?`,
          t: nowLabel(),
        },
      ]);
      scrollDown();
    }, 450);
  }, []);

  useEffect(() => {
    restart(profile);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectType = (key: VerticalKey) => {
    const p = clone(PRESETS[key]);
    setProfile(p);
    restart(p);
  };

  const send = async (text: string) => {
    const value = text.trim();
    if (!value) return;
    setInput("");
    setMessages((m) => [...m, { side: "out", text: value, t: nowLabel() }]);
    scrollDown();
    setTyping(true);
    try {
      const res = await fetch("/api/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile, session, text: value, mode: "deterministic" }),
      });
      const data = await res.json();
      setSession(data.session);
      setTimeout(() => {
        setTyping(false);
        setMessages((m) => [...m, { side: "in", text: data.reply, t: nowLabel() }]);
        if (data.booking) {
          setReceipt({
            kind: "book",
            title: "✅ Booking confirmed — POST to Sheets / Calendar",
            body: JSON.stringify(data.booking, null, 2),
          });
        } else if (data.escalate) {
          setReceipt({
            kind: "esc",
            title: "🚨 Escalation — assign to human inbox",
            body: `reason: ${data.escalate}\npriority: high`,
          });
        } else if (data.optOut) {
          setReceipt({ kind: "esc", title: "🔕 Opt-out — suppress from broadcasts", body: "tag: opted-out" });
        }
        scrollDown();
      }, 420 + Math.random() * 300);
    } catch {
      setTyping(false);
      setMessages((m) => [...m, { side: "in", text: "(network error reaching the engine)", t: nowLabel() }]);
    }
  };

  const saveProfile = async () => {
    setSaveState("saving");
    try {
      await fetch("/api/profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile }),
      });
      setSaveState("saved");
      setTimeout(() => setSaveState("idle"), 2000);
    } catch {
      setSaveState("idle");
    }
  };

  // Quick-reply chips that mirror the current step.
  const chips = useMemo(() => buildChips(session, profile), [session, profile]);

  const patch = (p: Partial<BusinessProfile>) => setProfile((prev) => ({ ...prev, ...p }));
  const list = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

  return (
    <main className="mx-auto max-w-6xl px-5 pb-16">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-4">
        <div>
          <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold leading-tight tracking-tight sm:text-4xl">
            Your booking agent, <span className="text-accent">live</span>.
          </h1>
          <p className="mt-1.5 max-w-2xl text-[15px] text-ink-soft">
            Fill in any business — clinic, dental, hotel, salon, shop, travel — and watch the WhatsApp agent run a real
            interactive booking. No Meta account, no keys. This is the exact engine that drops into the live webhook.
          </p>
        </div>
        <span className="whitespace-nowrap rounded-full bg-accent-wash px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-accent-ink">
          Test playground
        </span>
      </div>

      <div className="mt-5 grid items-start gap-5 lg:grid-cols-[1.05fr_0.95fr]">
        {/* ---------------- CONFIG ---------------- */}
        <section className="rounded-2xl border border-line bg-white shadow-sm">
          <div className="flex items-center gap-2 px-5 pt-4 font-[family-name:var(--font-display)] text-[13px] font-bold uppercase tracking-wide">
            <span className="grid h-5 w-5 place-items-center rounded bg-accent-wash text-[11px] text-accent-ink">1</span>
            Your business
          </div>
          <div className="px-5 pb-5 pt-3">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {VERTICAL_ORDER.map((k) => (
                <button
                  key={k}
                  onClick={() => selectType(k)}
                  className={`rounded-xl border px-2 py-2.5 text-center text-xs font-semibold transition ${
                    k === profile.type
                      ? "border-accent bg-accent-wash text-accent-ink ring-2 ring-accent-wash"
                      : "border-line bg-[#fbfcfb] text-ink-soft hover:border-[#c7d2cb] hover:bg-white"
                  }`}
                >
                  <span className="mb-1 block text-xl leading-none">{BLUEPRINTS[k].icon}</span>
                  {BLUEPRINTS[k].label.split(" ")[0]}
                </button>
              ))}
            </div>

            <Field2>
              <Field label="Business name" value={profile.brand} onChange={(v) => patch({ brand: v })} />
              <Field label="Agent name" value={profile.agentName} onChange={(v) => patch({ agentName: v })} />
            </Field2>
            <Field label="One-line description" value={profile.oneLiner} onChange={(v) => patch({ oneLiner: v })} />
            <Field2>
              <Field label="Open days" value={profile.days} onChange={(v) => patch({ days: v })} />
              <Field label="Hours" value={profile.hours} onChange={(v) => patch({ hours: v })} />
            </Field2>
            <Field2>
              <Field label="Languages (comma)" value={profile.languages.join(", ")} onChange={(v) => patch({ languages: list(v).length ? list(v) : ["English"] })} />
              <Field label="Time slots (comma)" value={profile.slots.join(", ")} onChange={(v) => patch({ slots: list(v) })} />
            </Field2>
            <Field
              label={`${bp.labels.providers} (comma)`}
              value={(profile.providers ?? []).join(", ")}
              onChange={(v) => patch({ providers: list(v) })}
            />
            <Field label="Address" value={profile.address ?? ""} onChange={(v) => patch({ address: v })} />

            {/* services */}
            <div className="mt-3">
              <label className="mb-1.5 block text-[11.5px] font-semibold uppercase tracking-wide text-ink-soft">
                {bp.labels.services}
              </label>
              <div className="space-y-1.5">
                {profile.services.map((s, i) => (
                  <div key={i} className="grid grid-cols-[1fr_110px_30px] gap-1.5">
                    <input
                      className="rounded-lg border border-line px-2.5 py-1.5 text-[13px] outline-none focus:border-accent focus:ring-2 focus:ring-accent-wash"
                      value={s.name}
                      placeholder="Item"
                      onChange={(e) => {
                        const svc = [...profile.services];
                        svc[i] = { ...svc[i], name: e.target.value };
                        patch({ services: svc });
                      }}
                    />
                    <input
                      className="rounded-lg border border-line px-2.5 py-1.5 text-[13px] outline-none focus:border-accent focus:ring-2 focus:ring-accent-wash"
                      value={s.price ?? ""}
                      placeholder="Price"
                      onChange={(e) => {
                        const svc = [...profile.services];
                        svc[i] = { ...svc[i], price: e.target.value };
                        patch({ services: svc });
                      }}
                    />
                    <button
                      title="Remove"
                      className="rounded-lg bg-[#f2f4f2] text-lg leading-none text-ink-soft hover:bg-[#fde8e4] hover:text-[#b42318]"
                      onClick={() => patch({ services: profile.services.filter((_, j) => j !== i) })}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
              <button
                className="mt-2 w-full rounded-lg border border-dashed border-line py-1.5 text-[13px] font-semibold text-accent-ink hover:bg-accent-wash"
                onClick={() => patch({ services: [...profile.services, { name: "", price: "" }] })}
              >
                + Add item
              </button>
            </div>

            <div className="mt-4 flex items-center gap-2">
              <button
                onClick={saveProfile}
                className="rounded-lg bg-accent px-4 py-2 text-[13px] font-semibold text-white transition hover:bg-accent-ink"
              >
                {saveState === "saving" ? "Saving…" : saveState === "saved" ? "✓ Saved as active" : "Save as active business"}
              </button>
              <span className="text-xs text-ink-soft">This profile becomes what the live WhatsApp webhook uses.</span>
            </div>

            <div className="mt-4 border-t border-dashed border-line pt-3">
              <button
                onClick={() => setShowPrompt((v) => !v)}
                className="text-[13px] font-semibold text-accent-ink"
              >
                {showPrompt ? "▾" : "▸"} View the generated AI system prompt
              </button>
              {showPrompt && (
                <pre className="mt-3 max-h-72 overflow-auto rounded-xl bg-[#0f1a16] p-3.5 text-[12px] leading-relaxed text-[#cfe7dc] whitespace-pre-wrap">
                  {systemPrompt}
                </pre>
              )}
            </div>
          </div>
        </section>

        {/* ---------------- PHONE ---------------- */}
        <section>
          <div className="flex items-center gap-2 pl-0.5 font-[family-name:var(--font-display)] text-[13px] font-bold uppercase tracking-wide">
            <span className="grid h-5 w-5 place-items-center rounded bg-accent-wash text-[11px] text-accent-ink">2</span>
            Test conversation
          </div>
          <div className="sticky top-4 mt-3">
            <div className="mx-auto max-w-sm rounded-[28px] border border-[#0a1116] bg-wa-bg p-2.5 shadow-2xl">
              <div className="overflow-hidden rounded-[20px] bg-wa-bg">
                <div className="flex items-center gap-2.5 bg-wa-head px-3 py-2.5">
                  <div className="grid h-9 w-9 flex-none place-items-center rounded-full bg-gradient-to-br from-[#2a9d77] to-accent text-sm font-bold text-white">
                    {(profile.agentName || "A")[0].toUpperCase()}
                  </div>
                  <div>
                    <div className="text-[14.5px] font-semibold leading-tight text-wa-text">{profile.brand}</div>
                    <div className="mt-0.5 text-[11.5px] text-wa-sub">
                      <span className="text-[#53bdeb]">online</span> · business account
                    </div>
                  </div>
                </div>

                <div ref={chatRef} className="chat-scroll flex h-[430px] flex-col gap-1.5 overflow-y-auto px-3 py-3.5">
                  {messages.map((m, i) => (
                    <div
                      key={i}
                      className={`bubble-pop relative max-w-[80%] whitespace-pre-wrap break-words rounded-lg px-2.5 pb-1.5 pt-1.5 text-[13.5px] text-wa-text ${
                        m.side === "in"
                          ? "self-start rounded-tl-[3px] bg-wa-in"
                          : "self-end rounded-tr-[3px] bg-wa-out"
                      }`}
                    >
                      {m.text}
                      <span className={`mt-0.5 block text-right text-[10px] ${m.side === "out" ? "text-[#9fd8c5]" : "text-wa-sub"}`}>
                        {m.t}
                        {m.side === "out" ? " ✓✓" : ""}
                      </span>
                    </div>
                  ))}
                  {typing && (
                    <div className="self-start rounded-lg rounded-tl-[3px] bg-wa-in px-3 py-2.5">
                      <span className="dot-blink mx-0.5 inline-block h-1.5 w-1.5 rounded-full bg-wa-sub" />
                      <span className="dot-blink mx-0.5 inline-block h-1.5 w-1.5 rounded-full bg-wa-sub" style={{ animationDelay: "0.2s" }} />
                      <span className="dot-blink mx-0.5 inline-block h-1.5 w-1.5 rounded-full bg-wa-sub" style={{ animationDelay: "0.4s" }} />
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2 bg-wa-head p-2.5">
                  <input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && send(input)}
                    placeholder="Message as the customer…"
                    className="flex-1 rounded-full bg-[#2a3942] px-3.5 py-2 text-[13.5px] text-wa-text outline-none placeholder:text-wa-sub"
                  />
                  <button
                    onClick={() => send(input)}
                    aria-label="Send"
                    className="grid h-9 w-9 flex-none place-items-center rounded-full bg-accent text-white hover:bg-accent-ink"
                  >
                    ➤
                  </button>
                </div>
              </div>
            </div>

            <div className="mx-auto mt-2.5 flex max-w-sm flex-wrap justify-center gap-1.5">
              {chips.map((c) => (
                <button
                  key={c}
                  onClick={() => send(c)}
                  className="rounded-full border border-line bg-white px-2.5 py-1 text-xs text-ink-soft transition hover:border-accent hover:bg-accent-wash hover:text-accent-ink"
                >
                  {c}
                </button>
              ))}
            </div>

            <div
              className={`mx-auto mt-3.5 max-w-sm overflow-hidden rounded-xl border shadow-sm transition ${
                receipt.kind === "idle" ? "border-line opacity-60" : "border-accent opacity-100"
              }`}
            >
              <div
                className={`flex items-center gap-2 px-3 py-2.5 text-xs font-semibold uppercase tracking-wide ${
                  receipt.kind === "book"
                    ? "bg-accent-wash text-accent-ink"
                    : receipt.kind === "esc"
                      ? "bg-warn-wash text-warn"
                      : "bg-[#f2f4f2] text-ink-soft"
                }`}
              >
                <span className="h-2 w-2 flex-none rounded-full bg-current" />
                {receipt.title}
              </div>
              <pre className="m-0 bg-white px-3 py-3 text-[12px] leading-relaxed text-[#33413a] whitespace-pre-wrap">
                {receipt.body}
              </pre>
            </div>

            <button onClick={() => restart(profile)} className="mx-auto mt-3.5 block text-[12.5px] text-ink-soft underline underline-offset-4">
              ↺ Restart the test chat
            </button>
            <p className="mx-auto mt-3 max-w-sm text-center text-xs leading-snug text-ink-soft">
              This runs the deterministic booking engine so it always completes. In production your Gemini→OpenAI layer
              wraps it for free-form understanding, with the same structured payload.
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}

// ─── Small form helpers ─────────────────────────────────────────────────────

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div className="mt-3">
      <label className="mb-1.5 block text-[11.5px] font-semibold uppercase tracking-wide text-ink-soft">{label}</label>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-line bg-white px-2.5 py-2 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent-wash"
      />
    </div>
  );
}

function Field2({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-2 gap-2.5">{children}</div>;
}

// ─── Chip suggestions per phase ─────────────────────────────────────────────

function buildChips(s: Session, p: BusinessProfile): string[] {
  if (s.phase === "greeting" || s.phase === "detect") {
    return ["I want to book", "What are your prices?", "Your hours?", "Where are you?"];
  }
  if (s.phase === "collecting") {
    const slots = activeSlotsFor(p, s.booking);
    const cur = slots[s.slotIdx];
    if (cur) {
      if (cur.kind === "time" && p.slots.length) return p.slots.slice(0, 4);
      if (cur.optionsFrom === "services") return p.services.slice(0, 3).map((x) => x.name);
      if (cur.optionsFrom === "providers" && (p.providers ?? []).length) return (p.providers ?? []).slice(0, 3);
      if (cur.kind === "date") return ["Tomorrow", "Next Monday", "15 July"];
      if (cur.kind === "number") return ["1", "2", "4"];
      if (cur.kind === "fulfil") return p.delivery ? ["Pickup", "Delivery"] : ["Pickup"];
      if (cur.key === "name") return ["Priya Sharma", "Rohan Mehta"];
      if (cur.kind === "phone") return ["9876543210"];
    }
  }
  if (s.phase === "confirm") return ["Yes, confirm", "No, change something"];
  if (s.phase === "cancelling") return ["Priya Sharma", "Tomorrow"];
  return ["Thanks!", "Book another"];
}
