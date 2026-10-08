# Lead Response & Qualification Agent

An AI agent that **responds to inbound leads in seconds, qualifies them against
a client's ICP + weighted BANT, scores them, routes them to the right rep, books
a meeting for hot leads, and logs everything with a full audit trail.**

Built with **FastAPI + LangGraph + (Ollama | Cloud LLM) + RAG (Chroma)**, exactly
as scoped in the PRD. It runs **out of the box with zero model setup** thanks to a
deterministic stub backend, then upgrades to local Ollama or a cloud LLM by
flipping one env var.

---

## What it does (the flow)

```
Lead source (web form / email / WhatsApp / LinkedIn)
        │  POST /leads/ingest
        ▼
┌──────────────────────── LangGraph workflow ────────────────────────┐
│ load_lead_and_config → dedup_and_verify → retrieve_rag_context →    │
│ parse_and_enrich → qualify_lead → decide_next_step → draft_response │
│        → [human approval?] → send_and_log → [book_meeting?] →       │
│           schedule_meeting → END                                    │
└─────────────────────────────────────────────────────────────────────┘
        │
        ├─ SQLite  (leads, conversations, qualifications, audit)
        ├─ Chroma  (per-client ICP docs & playbooks — RAG)
        ├─ Mock CRM (per-client CSV with dedup + provenance)
        └─ Scheduler (Calendly-style link per rep)
```

- **Dedup & verify (QC gauntlet):** every lead is email-verified and dedup-checked
  *before* any LLM effort is spent.
- **Weighted BANT:** each of Budget/Authority/Need/Timeline scored 0–3, combined
  with per-client weights, thresholds and hard rules (all tunable, no code change).
- **ICP fit** is computed deterministically in code (auditable), then blended with
  BANT for the total score → Hot / Warm / Cold.
- **Explainability:** every qualification stores per-dimension scores, signals,
  reasons and a reasoning summary. Every decision is written to an audit trail.
- **Human-in-the-loop:** when a client requires approval, the graph pauses after
  drafting; the rep approves/edits via `/approve` and delivery resumes.

---

## Quick start (stub mode — no Ollama needed)

```bash
cd lead-qual-agent
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # defaults to USE_STUB_LLM=true

# seed a demo client (Acme Logistics) + ICP + BANT config + reps + RAG docs
python scripts/seed.py

# run the whole pipeline on 3 sample leads and print results
python scripts/smoke_test.py

# or start the API
uvicorn app.main:app --reload
```

Then ingest a lead:

```bash
curl -X POST http://localhost:8000/leads/ingest -H "Content-Type: application/json" -d '{
  "source": "web_form",
  "client_id": "client_001",
  "lead": {
    "name": "Rahul Sharma", "email": "rahul@acme.in", "company": "Acme Logistics",
    "title": "Operations Head", "phone": "+91-9800000000", "website": "https://acme.in",
    "message": "We lose ~15% of deliveries to poor routing. Need a fix before Q1 peak season. I own this but need CFO sign-off above $30k.",
    "company_size": 150, "industry": "Logistics", "region": "IN", "budget_range": "$20k-$50k"
  }
}'
```

Interactive API docs: <http://localhost:8000/docs>

---

## Switching the LLM backend

Edit `.env`:

| Mode   | Settings                                                                 |
|--------|--------------------------------------------------------------------------|
| Stub   | `USE_STUB_LLM=true` — keyword heuristic, no server, fully testable        |
| Ollama | `USE_STUB_LLM=false`, `USE_CLOUD_LLM=false`, Ollama running locally       |
| Cloud  | `USE_STUB_LLM=false`, `USE_CLOUD_LLM=true`, `OPENAI_API_KEY=sk-...`       |

### Ollama setup
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1:8b
ollama pull nomic-embed-text      # embeddings for RAG
ollama serve
```
The code degrades gracefully: if the LLM returns unparseable output, it falls
back to the heuristic; if Chroma/Ollama embeddings aren't available, RAG returns
empty context and the agent still runs.

---

## API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/health` | status + current LLM mode |
| POST | `/leads/ingest` | ingest + auto-process a lead (any channel) |
| POST | `/leads/{id}/process` | run the graph on a stored lead |
| POST | `/leads/{id}/approve` | approve/edit a pending draft (human-in-the-loop) |
| POST | `/leads/{id}/override` | override score/label (audited) |
| GET  | `/leads/{id}` | full record: lead, qualification, conversation, meeting, audit |
| GET  | `/clients/{id}/leads` | list leads with scores |
| GET  | `/clients/{id}/dashboard` | LTVL, data completeness, booking rate, response time |
| POST | `/clients/{id}/rag/index` | index ICP/playbook docs for a client |

---

## Project layout

```
lead-qual-agent/
  app/
    main.py        FastAPI endpoints + ingestion normalization
    graph.py       LangGraph workflow (9 nodes, approval + schedule branches)
    bant.py        BANT scoring engine (fit + weighted BANT + rules + prompts)
    llm.py         stub/ollama/cloud providers + heuristic fallback
    rag.py         Chroma per-client retrieval (lazy, degrades gracefully)
    enrich.py      email verification + firmographic enrichment (QC gauntlet)
    crm.py         mock CRM (CSV) with dedup + provenance fields
    routing.py     owner assignment (round-robin / territory / segment)
    scheduler.py   meeting proposal/booking
    messaging.py   outbound send (email/WhatsApp stub)
    db.py          SQLite persistence
    models.py      Client, ICPConfig, BANTConfig, Lead, ConversationMessage,
                   QualificationResult, Meeting, Rep, AuditEntry
  scripts/
    seed.py        demo client + ICP + BANT + reps + RAG docs
    smoke_test.py  full end-to-end run on 3 sample leads
  requirements.txt
  .env.example
```

---

## How this maps to the PRD

- **Data model** — `app/models.py` implements every entity from the PRD.
- **BANT** — weighted 0–3 model with per-client `BANTConfig` (weights, thresholds,
  hard rules), computed in code for auditability; the 13 strategic questions guide
  the LLM prompt.
- **Pillars applied** — predictive-style scoring with trait drivers (Pillar 1),
  grounded personalization via RAG (Pillar 2), dedup/verify QC gauntlet + provenance
  (Pillar 3), conversational BANT qualification (Pillar 4), AI-specific dashboard
  KPIs — LTVL, data completeness, booking rate, response time (Pillar 8).
- **Guardrails** — configurable human approval, never send to an unverified email
  path, full audit trail, per-client data isolation (DB + RAG namespacing).

## Roadmap (next phases)

- Real connectors: HubSpot/Pipedrive/Salesforce, Gmail/SMTP, Twilio/Meta WhatsApp,
  Calendly/Google Calendar.
- Phase-2 scoring: Logistic Regression → ensemble once ≥100 labeled conversions
  exist (the `scoring_method`/`model_version` fields already carry the version).
- Admin UI (Streamlit/Next.js), A/B testing of messages, multi-agent split.
