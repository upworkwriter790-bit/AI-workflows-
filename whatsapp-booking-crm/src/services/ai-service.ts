/* ============================================================================
 * AI auto-reply service.
 *
 * Fallback chain (matches the reference CRM): Gemini 1.5-flash → Gemini
 * 2.0-flash → OpenAI gpt-4o-mini (or any OpenAI-compatible endpoint, e.g.
 * OpenRouter). Each provider is wrapped in a tiny circuit breaker so a flaky
 * provider is skipped for a cool-off window instead of slowing every reply.
 *
 * Uses plain `fetch` against the REST APIs — no SDK dependencies, so the app
 * installs light and runs anywhere. If NO key is configured, `aiReply` returns
 * null and the caller falls back to the deterministic engine.
 * ==========================================================================*/

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

interface Provider {
  name: string;
  enabled: () => boolean;
  call: (system: string, history: ChatTurn[]) => Promise<string>;
}

// ─── Circuit breaker ────────────────────────────────────────────────────────

const COOL_OFF_MS = 60_000;
const breaker = new Map<string, number>(); // provider → openUntil (epoch ms)

function isOpen(name: string): boolean {
  const until = breaker.get(name);
  return until !== undefined && Date.now() < until;
}
function trip(name: string) {
  breaker.set(name, Date.now() + COOL_OFF_MS);
}
function reset(name: string) {
  breaker.delete(name);
}

// ─── Provider implementations ───────────────────────────────────────────────

async function callGemini(model: string, system: string, history: ChatTurn[]): Promise<string> {
  const key = process.env.GEMINI_API_KEY!;
  const contents = history.map((t) => ({
    role: t.role === "assistant" ? "model" : "user",
    parts: [{ text: t.content }],
  }));
  const res = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${key}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        systemInstruction: { parts: [{ text: system }] },
        contents,
        generationConfig: { temperature: 0.4, maxOutputTokens: 400 },
      }),
      signal: AbortSignal.timeout(15_000),
    },
  );
  if (!res.ok) throw new Error(`Gemini ${model} HTTP ${res.status}`);
  const data = await res.json();
  const text = data?.candidates?.[0]?.content?.parts?.map((p: { text?: string }) => p.text).join("") ?? "";
  if (!text) throw new Error(`Gemini ${model} empty response`);
  return text.trim();
}

async function callOpenAI(system: string, history: ChatTurn[]): Promise<string> {
  const key = process.env.OPENAI_API_KEY!;
  const base = process.env.OPENAI_BASE_URL || "https://api.openai.com/v1";
  const model = process.env.OPENAI_MODEL || "gpt-4o-mini";
  const res = await fetch(`${base}/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
    body: JSON.stringify({
      model,
      temperature: 0.4,
      max_tokens: 400,
      messages: [{ role: "system", content: system }, ...history],
    }),
    signal: AbortSignal.timeout(15_000),
  });
  if (!res.ok) throw new Error(`OpenAI HTTP ${res.status}`);
  const data = await res.json();
  const text = data?.choices?.[0]?.message?.content ?? "";
  if (!text) throw new Error("OpenAI empty response");
  return text.trim();
}

const PROVIDERS: Provider[] = [
  { name: "gemini-1.5-flash", enabled: () => !!process.env.GEMINI_API_KEY, call: (s, h) => callGemini("gemini-1.5-flash", s, h) },
  { name: "gemini-2.0-flash", enabled: () => !!process.env.GEMINI_API_KEY, call: (s, h) => callGemini("gemini-2.0-flash", s, h) },
  { name: "openai", enabled: () => !!process.env.OPENAI_API_KEY, call: callOpenAI },
];

export function aiConfigured(): boolean {
  return PROVIDERS.some((p) => p.enabled());
}

/**
 * Get an AI reply, walking the fallback chain. Returns null if no provider is
 * configured or every provider failed — the caller then uses the deterministic
 * engine, so a missing/broken AI layer never blocks a booking.
 */
export async function aiReply(system: string, history: ChatTurn[]): Promise<{ text: string; provider: string } | null> {
  let lastErr: unknown;
  for (const p of PROVIDERS) {
    if (!p.enabled() || isOpen(p.name)) continue;
    try {
      const text = await p.call(system, history);
      reset(p.name);
      return { text, provider: p.name };
    } catch (err) {
      lastErr = err;
      trip(p.name);
      console.warn(`[ai-service] ${p.name} failed:`, (err as Error).message);
    }
  }
  if (lastErr) console.error("[ai-service] all providers failed", lastErr);
  return null;
}
