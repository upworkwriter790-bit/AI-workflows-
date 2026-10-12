# Invoice Automation Agent

AI-assisted, post-payment invoice automation for two use cases only:

1. **Use Case 1 — AR**: a paid website/CRM order → GST-compliant tax invoice
   → ERP → customer email → Operations notified for product access.
2. **Use Case 2 — Received document review**: an incoming invoice/document
   is read, validated, checked for duplicates, and routed to
   `ACCEPT` / `HOLD_FOR_REVIEW` / `REJECT` — a human or deterministic backend
   rule makes the final call, never the LLM alone.

Payment collection, Accounts Payable, and supplier-payment automation are
explicitly **out of scope** — see `docs/architecture.md`.

This is **Phase 1 only** (project scaffold, DB schema, audit log, mock
CRM/ERP/email/operations/product-access adapters, health endpoint). Phases
2–5 (webhook intake, GST calculation, PDF generation, real integrations,
Claude/LLM extraction wiring, admin dashboard, production hardening) are not
yet built — see `docs/test-plan.md` and the phase list at the bottom of this
file.

## No Docker

By design (per project decision) this repo has **no Dockerfile or
docker-compose.yml**. Run everything as native OS processes — see
`backend/Procfile` for the three processes a production host needs
(`web`, `worker`, `beat`) and the local setup below for development.

## Local development setup

Requires Python 3.11+ (tested on 3.13), and — once Phase 2+ work needs
them — a local PostgreSQL and Redis. Phase 1 works fully on SQLite with no
external services.

```bash
cd invoice-agent/backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp ../.env.example .env
# Phase 1 / local dev: you can leave DATABASE_URL as the sqlite default in
# config.py, or set it explicitly:
echo 'DATABASE_URL=sqlite:///./invoice_agent_dev.db' >> .env

python -m alembic upgrade head      # creates all tables
uvicorn app.main:app --reload       # http://localhost:8000/health
```

Running against real PostgreSQL + Redis instead (needed from Phase 2
onward): install Postgres and Redis however you normally would (native
package manager, a managed cloud instance, or any Postgres/Redis you already
run) — there is no bundled container. Point `DATABASE_URL` /`REDIS_URL` in
`.env` at them and re-run `alembic upgrade head`.

### Running tests

```bash
cd invoice-agent/backend
source .venv/bin/activate
python -m pytest -q
```

25 tests cover: health endpoint + live-invoicing-readiness gate, every DB
model round-tripping through SQLAlchemy, all five mock adapters (CRM, ERP,
email, Operations, product-access), HMAC webhook-signature verification
(valid / tampered / stale timestamp), structured-log redaction (API keys,
GSTINs, emails), and the multi-provider LLM client's provider-selection and
JSON-extraction logic.

### Linting

```bash
python -m ruff check app
```

## Environment variables

See `.env.example` at the repo root for the full list, grouped by: company/
tax identity, database/queue, CRM, ERP, product access, email, Operations
notification, storage, LLM provider + keys, decision thresholds, and
monitoring.

**Nothing related to company identity, tax numbers, or live integrations
has a working default.** `GET /health` reports `live_invoicing_ready: false`
and lists exactly which company/tax fields are still unset — this is
intentional: the system refuses to pretend it has real invoicing data until
you provide it.

## Choosing an LLM provider (Use Case 2)

Set `LLM_PROVIDER` to one of `anthropic`, `openai`, `openrouter`, `gemini`,
`sarvam`, and set that provider's API key. All five share the exact same
system prompt (`backend/app/prompts/invoice_document_review_system.txt`)
and the exact same required JSON schema
(`backend/app/schemas/invoice_extraction_schema.py`) — switching providers
never changes what the backend expects back, only which model answers.
See `docs/architecture.md` for notes on each provider's document/PDF input
support, and the honest caveat on Sarvam's multimodal support, which should
be re-verified against their current docs before production use.

## Production configuration checklist

Before `ENVIRONMENT=production`:

- [ ] All company/tax identity fields set (`COMPANY_LEGAL_NAME`,
      `SELLER_GSTIN`, `SELLER_STATE_NAME`/`CODE`, etc.) — confirm with a
      qualified tax professional, not just engineering.
- [ ] `APP_SECRET_KEY` and `CRM_WEBHOOK_HMAC_SECRET` rotated to real secrets.
- [ ] Real CRM/ERP/email/product-access/storage credentials set; the
      corresponding `*_PROVIDER` env vars switched off `mock` once each real
      adapter is implemented (Phase 3).
- [ ] `AUTO_ACCEPT_MAX_AMOUNT` set deliberately — it defaults to `0`, which
      means nothing auto-accepts until you choose a real ceiling.
- [ ] `DATABASE_URL` points at a real, backed-up PostgreSQL instance.
- [ ] `SENTRY_DSN` set.
- [ ] Role-based access configured on the admin dashboard (Phase 3/5).

## Phases (see docs for detail)

1. ✅ Scaffold, DB models, audit log, mock adapters, health check — **this repo, now**.
2. Paid-order webhook, GST rules, invoice numbering, PDF generation.
3. Real ERP/CRM/email adapters, Operations task flow, admin dashboard.
4. Received-document intake, LLM extraction, deterministic decision engine, review queue.
5. Production hardening: RBAC, rate limits, metrics, deployment.

## Docs

- `docs/architecture.md` — components, data flow, trust boundaries, failure/retry behavior.
- `docs/api-contracts.md` — every endpoint and webhook contract (Phase 2+ endpoints marked not-yet-built).
- `docs/decision-rules.md` — the Use Case 2 ACCEPT/HOLD/REJECT matrix and GST checklist.
- `docs/deployment.md` — secrets, migrations, queues, storage, monitoring, security checklist.
- `docs/test-plan.md` — required test cases from the spec and which are implemented so far.
