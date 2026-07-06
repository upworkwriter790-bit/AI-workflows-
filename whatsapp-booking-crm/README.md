# WhatsApp Booking CRM — multi-vertical booking automation

Fill in **one business profile** and a WhatsApp agent runs a full **interactive
booking conversation** for it — clinic, dental, salon, hotel, restaurant,
retail, travel, fitness, automotive, or a generic fallback. The business
"texts first", the customer chats back, and the agent collects every detail,
confirms, and emits a clean structured booking your backend syncs to Google
Sheets + Calendar.

Built on the **official Meta WhatsApp Cloud API** (same API as WATI / Interakt /
AiSensy — but self-hosted, no per-message middleman). The conversation brain is
a **deterministic state machine wrapped by an optional Gemini → OpenAI layer**,
so a booking flow *never* loses a field or hallucinates a confirmation.

> Open the app, pick a business type, edit the details, and chat with the bot
> in the phone mockup — no Meta account and no API keys required to test. What
> you test locally is the exact engine that runs against live WhatsApp.

**It's a full CRM, not just a bot:** manage **multiple businesses** in one
deployment (each routed by its own WhatsApp number), a **shared inbox** with
**one-click human takeover**, a live **dashboard**, a **settings/integrations**
page, and an **admin login**.

---

## Why this design

The reference prototype was clinic-only and LLM-only. Two problems with
LLM-only booking bots: they forget to ask for a field, and they sometimes
"confirm" a booking that was never completed. So this uses **two layers**:

| Layer | Role | File |
|-------|------|------|
| **Deterministic FSM** | Guarantees the booking flow completes and emits a clean object. The source of truth for state + structured output. | `src/lib/engine/` |
| **LLM (Gemini → OpenAI)** | *Optional.* Wraps the flow for fuzzy, natural-language understanding and small talk. On any failure it falls back to the FSM. | `src/services/ai-service.ts` |

A business is described by a **`BusinessProfile`** (the fill-in-the-blanks
config) and a **`Blueprint`** (the vertical's vocabulary + which questions to
ask, in order). **Adding a whole new vertical = one entry** in
`src/lib/engine/blueprints.ts`. Nothing else changes — the prompt generator,
the FSM, the simulator UI and the dashboard all read from that registry.

```
Role     | clinic       | hotel       | retail   | travel
---------|--------------|-------------|----------|----------
booking  | appointment  | reservation | order    | trip booking
provider | doctor       | room type   | —        | package
item     | consultation | stay        | product  | trip
customer | patient      | guest       | customer | traveller
```

---

## What was fixed vs. the prototype

- **Retail `fulfilment`** is now its own `fulfil` slot kind. The prototype
  mislabelled it as `optionsFrom: "services"`, which leaked product names into
  the pickup/delivery step.
- **Confirmation no longer wipes the whole booking** on *any* non-"yes" reply.
  It only restarts on an explicit "no/change"; ambiguous replies re-ask.
- **STOP / opt-out handling** (WATI-style broadcast suppression) + **START** to
  re-subscribe.
- **Cancellation** now captures a structured `CANCEL` object and routes to a
  human, instead of a blind escalation.
- **After-hours guardrail** driven by structured `businessHours`.
- **Direct FAQ answering** from the profile.
- **Greeting** no longer double-counts a turn when the opener already carries
  intent.
- **Security**: `.env.example` contains placeholders only — no real keys.
- Full test suite (`npm test`) covering all of the above.

---

## Pages

| Page | What it does |
|------|--------------|
| `/` **Builder** | Pick a vertical, fill in details, chat with the live agent, save it as a business (create/select/delete multiple), set its WhatsApp phone-number ID. |
| `/inbox` **Shared inbox** | Live conversations per business; open a thread, reply manually to **take over** from the bot, or hand it back. |
| `/dashboard` | Bookings, contacts, integration status per business. |
| `/settings` | Integration status, the exact webhook URL to paste into Meta, per-business routing, go-live checklist, logout. |
| `/login` | Admin sign-in (only when `ADMIN_PASSWORD` is set). |

## Multiple businesses

One deployment serves all your businesses (a clinic, a retreat, a shop…). Each
is a saved `BusinessProfile` with its own `phoneNumberId`. Inbound WhatsApp
messages are routed to the right business by the `phone_number_id` in the Meta
webhook payload, so every business gets its own agent, inbox and bookings.

## Quick start (zero config)

```bash
npm install
npm run dev        # http://localhost:3000
```

Everything runs in **demo mode** with no keys: the booking flow works, sends are
logged to the console, and data persists to `.data/store.json`. To run the
tests and a production build:

```bash
npm test           # engine + parser tests (12 cases)
npm run typecheck  # strict TypeScript, no errors
npm run build      # Next.js production build
```

---

## Going live with WhatsApp

The code is complete; going live only needs credentials that must be created
under **your** Meta account (no code can text customers on your behalf):

1. **Create a Meta app** → add the **WhatsApp** product → get a
   **phone-number ID** and a **permanent access token**.
2. Copy `.env.example` → `.env.local` and fill in:
   - `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`
   - `WHATSAPP_VERIFY_TOKEN` (any random string)
   - `META_APP_SECRET` (App Settings → Basic) — verifies inbound webhook HMAC
3. **Deploy** (Vercel / Railway / Hostinger / any Node host). You need a public
   HTTPS URL.
4. In Meta → WhatsApp → **Configuration → Webhook**, set:
   - Callback URL: `https://YOUR_DOMAIN/api/whatsapp/webhook`
   - Verify token: the same `WHATSAPP_VERIFY_TOKEN`
   - Subscribe to the **messages** field.
5. (Optional) add `GEMINI_API_KEY` and/or `OPENAI_API_KEY` for the natural-
   language layer; without them the deterministic engine handles everything.
6. (Optional) deploy `scripts/google-apps-script.gs`, paste the `/exec` URL into
   `GOOGLE_SHEETS_WEBHOOK_URL` to sync every booking to Sheets + Calendar.

### Generate the encryption key (don't reuse any example value)

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

---

## Architecture / file map

```
src/
├── lib/engine/
│   ├── types.ts         BusinessProfile, Blueprint, Session, results
│   ├── blueprints.ts    the 10 verticals (vocabulary + ordered questions)
│   ├── index.ts         FSM (step), generateSystemPrompt, isOpenNow
│   ├── parse-tags.ts    strips/parses <<BOOKING>> <<CANCEL>> <<ESCALATE>>
│   └── engine.test.ts   12 tests
├── lib/
│   ├── presets.ts       editable demo profile per vertical
│   ├── dates.ts         "tomorrow"/"next mon"/"15 Jul" → ISO (for reminders)
│   ├── sheets-sync.ts   POST booking → Apps Script (Sheets + Calendar)
│   ├── whatsapp/meta-client.ts  send text/template, HMAC verify, GET handshake
│   └── store/index.ts   profiles, sessions, contacts, bookings, history
├── services/
│   ├── ai-service.ts    Gemini 1.5 → Gemini 2.0 → OpenAI, circuit breaker
│   └── conversation.ts  orchestrator: FSM ⊕ AI, persistence, sync, tagging
├── middleware.ts        admin auth gate (active when ADMIN_PASSWORD is set)
├── lib/auth.ts          session cookie (salted SHA-256, Web Crypto)
├── app/
│   ├── page.tsx         the Builder (multi-business config + phone simulator)
│   ├── inbox/           shared inbox + human takeover
│   ├── dashboard/       bookings, contacts, integration status
│   ├── settings/        integrations, webhook URL, go-live checklist
│   ├── login/           admin sign-in
│   └── api/
│       ├── whatsapp/webhook/  GET verify + POST inbound (routes by phone id)
│       ├── simulate/          stateless engine for the simulator
│       ├── profile/           list/get/create/delete businesses
│       ├── inbox/             list · thread · reply · pause (takeover)
│       ├── dashboard/         data feed (per business)
│       ├── auth/              login · logout
│       ├── cron/reminders/    T-24h reminders + missed follow-up
│       └── broadcast/         template campaign to a tagged segment
└── scripts/google-apps-script.gs   Sheets + Calendar web app
```

---

## Automation recipes (mapped to this code)

| Recipe (from the brief) | How it's implemented |
|--------------------------|----------------------|
| Welcome + first-time tag | `conversation.ts` tags `new-lead` on first contact |
| Appointment reminder T-24h | `GET /api/cron/reminders` (Vercel cron at 9 AM via `vercel.json`) |
| Missed-appointment follow-up | same cron flags same-day unattended bookings |
| Keyword quick-replies (hours/price/location) | intent router in `engine/index.ts` |
| STOP opt-out | engine + orchestrator suppress + tag `opted-out` |
| Cancellation / reschedule | structured `CANCEL` capture → human handoff |
| Broadcast campaign | `POST /api/broadcast` (segment by tag, suppress opt-outs) |
| Agent handoff / escalation | `<<ESCALATE>>` + `needs-human` tag, or one-click **Take over** in the inbox |
| Business-hours guardrail | `isOpenNow` + after-hours greeting/callback |
| Multi-language | AI layer detects + replies in the customer's language |

Schedule the reminder cron (already wired for Vercel in `vercel.json`); for
other hosts call it daily with `Authorization: Bearer $CRON_SECRET`.

---

## Adding a new vertical

Add one entry to `BLUEPRINTS` in `src/lib/engine/blueprints.ts` (label, icon,
`noun`, ordered `slots`, `confirm`/`done` copy), add it to `VERTICAL_ORDER`, and
add a demo profile to `src/lib/presets.ts`. The simulator, prompt generator,
dashboard and webhook pick it up automatically.

---

## Security notes

- Inbound webhooks are verified with **HMAC-SHA256** against `META_APP_SECRET`
  (constant-time compare). With no secret set, the app is in local demo mode.
- `.env*` is git-ignored; `.env.example` ships placeholders only.
- Rotate `ENCRYPTION_KEY` to a fresh 32-byte value before storing real tokens.
- Cron and broadcast endpoints require `Authorization: Bearer $CRON_SECRET`.

## Tech stack

Next.js 16 (App Router, Turbopack) · React 19 · TypeScript (strict) ·
Tailwind v4 · Meta WhatsApp Cloud API · Gemini/OpenAI · Google Apps Script.
