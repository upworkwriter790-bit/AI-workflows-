# HR-02 · Onboarding + Offboarding Agent — Interactive Demo

An interactive, runnable demo of the **illactic HR-02 Onboarding + Offboarding Agent**
described in the PRD (HR-02 v2). It simulates the agent that *generates, drives, and
evidences* every joiner and leaver checklist — requesting documents, validating what
arrives, routing tasks, chasing what's late, and escalating what's stuck.

> This is a **front-end simulation** of the agent's decision logic for demonstration and
> testing. There is no real HRIS / ticketing / payroll integration — the "agent" runs
> deterministically in the browser so you can see exactly how it behaves, step by step.

## Run it on localhost

No dependencies to install — it uses only Node's built-in HTTP server.

```bash
cd demo/hr-onboarding-offboarding-agent
npm start           # or: node server.js
```

Then open **http://localhost:3000**

(To use a different port: `PORT=8080 npm start`.)

You can also just open `public/index.html` directly in a browser — it works offline too.

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
├── server.js            # zero-dependency static server (localhost)
├── package.json
├── README.md
└── public/
    ├── index.html       # layout
    ├── style.css        # styling (light/dark aware)
    ├── agent.js         # the agent engine — checklist assembly, validation, classification
    └── app.js           # UI controller — board, drawer, activity log
```
