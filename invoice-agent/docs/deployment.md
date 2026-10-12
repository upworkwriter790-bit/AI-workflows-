# Deployment

No Docker, per project decision. Deploy as native OS processes (systemd, a
process manager, PaaS buildpack, or `honcho start` against
`backend/Procfile`) against whatever Postgres/Redis you provide credentials
for.

## Secrets

Set directly in the hosting platform's secret manager (not committed
anywhere, not in `.env` in any repo):

- `APP_SECRET_KEY`
- `CRM_WEBHOOK_HMAC_SECRET`
- `CRM_API_KEY`, `ERP_API_KEY`, `PRODUCT_ACCESS_API_KEY`
- `EMAIL_API_KEY`
- `STORAGE_ACCESS_KEY_ID` / `STORAGE_SECRET_ACCESS_KEY`
- Whichever `*_API_KEY` matches `LLM_PROVIDER`
- `SENTRY_DSN`

`app/core/logging.py` redacts any log field whose key contains `api_key`,
`secret`, `password`, `authorization`, `gstin`, `email`, `phone`, or
`token`, plus GSTIN-shaped and email-shaped substrings inside free text —
but that is a safety net, not a substitute for never passing secrets as log
arguments in the first place.

## Database migrations

```bash
python -m alembic upgrade head
```

Run this on deploy, before the new app version starts serving traffic.
`0001_initial_schema` creates all nine Phase-1 tables. Future migrations
are additive — see `alembic/versions/`. Never hand-edit a column in
production outside a migration.

## Queues

Celery (`app/tasks/celery_app.py`) against Redis. Two long-running
processes besides the web process: `worker` and `beat` (see `Procfile`).
`task_acks_late=True` + `worker_prefetch_multiplier=1` are set so a worker
crash mid-task re-delivers the task rather than silently dropping it —
combined with the idempotency-key design, a redelivered task is safe to
re-run.

## Storage

`STORAGE_PROVIDER=local` (default) writes to `STORAGE_LOCAL_DIR` — fine for
development, **not for production** (not durable, not shared across
instances). For production, set `STORAGE_PROVIDER=s3` (or `r2`/
`azure_blob`) with real credentials; invoice PDFs and received documents
are stored privately with short-lived signed URLs only, never public
objects.

## Monitoring

- `SENTRY_DSN` wires error tracking once set (Phase 2+, when there's
  workflow code to instrument).
- Structured JSON logs (`structlog`) on stdout — ship them to whatever log
  aggregator the host already uses.
- `GET /health` is the liveness/readiness probe. It also doubles as a
  config-completeness probe via `live_invoicing_ready` — a production
  deploy with `live_invoicing_ready: false` has shipped without its
  required company/tax configuration and should alert, not just log.

## Backup

Once on real PostgreSQL: standard point-in-time-recovery backups. The
`audit_events` table is append-only by convention (never updated or
deleted by application code) — treat any gap in its history as a sign
something bypassed the audit service, not as expected behavior.

## Security checklist

- [ ] HMAC webhook secret is a real random secret, rotated from the `.env.example` placeholder.
- [ ] All `*_PROVIDER` env vars are set to their real provider, not left on `mock`, before go-live.
- [ ] Admin dashboard has role-based access (`ADMIN`, `FINANCE_REVIEWER`, `OPERATIONS_USER`, `SUPPORT_READ_ONLY`) wired (Phase 3/5).
- [ ] Rate limiting on the public webhook endpoint (Phase 5).
- [ ] No secret, GSTIN, full address, or document byte content ever appears in a log line, error response, or frontend URL.
- [ ] Object storage buckets are private; invoice/document URLs are short-lived signed URLs only.
- [ ] GST tax-calculation rules and invoice-numbering convention reviewed by a qualified tax professional before production use.
