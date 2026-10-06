# HR-02 · Onboarding + Offboarding Agent — Interactive Demo

An interactive, runnable demo of the **illactic HR-02 Onboarding + Offboarding Agent**
described in the PRD (HR-02 v2). It simulates the agent that *generates, drives, and
evidences* every joiner and leaver checklist — requesting documents, validating what
arrives, routing tasks, chasing what's late, and escalating what's stuck.

> v2 has a **real backend**: a Node API with a **SQLite database**, server-side agent logic, and a
> **live stream** (Server-Sent Events) so every open tab updates instantly. Everything you click is
> saved (`data/hr02.db`, uploaded files in `data/uploads/`) and survives restarts. HRIS / ticketing /
> payroll integrations and the AI document reader are not connected: the upload's "Validator finds"
> dropdown stands in for the AI model so you can test every outcome.

## Run it on localhost

Requires **Node 22.5+** (uses built-in `node:sqlite`; nothing to `npm install`).

```bash
cd demo/hr-onboarding-offboarding-agent
npm start           # then open http://localhost:3000   (PORT=8080 npm start to change port)
```

Open it in two browser tabs: a change in one appears in the other immediately.

## Backend

| Endpoint | Purpose |
|---|---|
| `GET /api/state` | all events + activity log |
| `GET /api/stream` | SSE: pushes a `change` event on every write |
| `POST /api/events` | trigger the agent for a new joiner / leaver |
| `POST /api/cards/:id/action` | complete, reopen, chase, confirm ticket, HR-accept, ... |
| `POST /api/cards/:id/upload/:itemId` | real file upload, then validation + 3-strike escalation |
| `DELETE /api/cards/:id`, `POST /api/reset` | delete an event / reset sample data |

A background scheduler runs every 15s: it auto-chases overdue items and escalates any access-revocation
ticket still unconfirmed 4 hours after its effective time as a security incident. The settlement lock is
enforced **server-side** (a direct API call to release it is rejected with 400 until all clearances are green).

## What the demo shows (mapped to the PRD)

The screen is the **lifecycle board** from the PRD Solution Overview — two columns,
**Joining** and **Exiting** — plus a live **Agent activity** log (the immutable evidence trail).

| PRD capability | Where to see it |
|---|---|
| **Checklist generation** by role × location × department × employment-type, no per-combination template | Click **+ New lifecycle event** → the agent assembles owners + due dates anchored to start / last-working date |
| **Document validation** (type, legibility, name-match, expiry) with specific re-requests | Open a joiner → Employee documents → "Submit to agent" with a chosen quality |
| **3-failure escalation to HR** | Submit an invalid document 3× → item escalates, no further automated requests |
| **Worker-classification check at contract issue** | Create a **Contractor** joiner → amber contradiction strip + detail (never reclassifies — legal counsel decides) |
| **IT tasks via ticket only** (never direct API write) | IT group items show ticket system + confirmation tracking |
| **Access-revocation ticket with 4h escalation** | Open a leaver → IT → "Simulate 4h, no confirmation" → logged as a **security incident** |
| **Exit clearance aggregation + settlement hard-lock** ("blocked, not warned") | Leaver cards show the 🔒 blocked banner until every clearance is green |
| **Independent exit interviewer** (never the line manager) | Leaver → HR → exit interview shows the assigned independent interviewer |
| **First-30-days structure** (day-7/14/30 check-ins + measurable 30-day goal + feedback) | Joiner → Manager group |
| **Overdue chase + T-3 escalation** | Overdue items turn red with a one-click **Chase now** |
| **Immutable evidence record per lifecycle event** | The right-hand **Agent activity** log |
| **Involuntary / disciplinary exits owned by HR-07** | Offboarding form takes an optional HR-07 case reference; the agent only executes once authorised |

### Deliberately out of scope (per PRD §7)
The agent **raises tickets; IT provisions and revokes**. It **never** reclassifies a worker,
amends a contract, calculates final settlement, or initiates/justifies an exit.

## Files

```
demo/hr-onboarding-offboarding-agent/
├── server.js            # backend: REST API + SQLite + SSE + scheduler
├── data/                # created at runtime (db + uploads, git-ignored)
├── package.json
├── README.md
└── public/
    ├── index.html       # layout
    ├── style.css        # styling (light/dark aware)
    ├── agent.js         # the agent engine — checklist assembly, validation, classification
    └── app.js           # UI controller — board, drawer, activity log
```
