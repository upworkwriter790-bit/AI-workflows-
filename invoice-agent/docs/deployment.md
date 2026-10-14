# Deployment

No Docker, per project decision. Deploy as native OS processes (systemd, a
process manager, PaaS buildpack, or `honcho start` against
`backend/Procfile`) against whatever Postgres/Redis you provide credentials
for.

## Secrets

Set directly in the hosting platform's secret manager (not committed
anywhere, not in `.env` in any repo):

- `JWT_SECRET`
- `EMAIL_API_KEY`, `EMAIL_WEBHOOK_SIGNING_SECRET`
- `WHATSAPP_AUTH_TOKEN`, `WHATSAPP_WEBHOOK_SIGNING_SECRET`
- `STORAGE_ACCESS_KEY_ID` / `STORAGE_SECRET_ACCESS_KEY`

`app/core/logging.py` redacts any log field whose key contains `api_key`,
`secret`, `password`, `authorization`, `email`, `phone`, `token`, or
`jwt_secret`, plus email-shaped and E.164-phone-shaped substrings inside
free text — a safety net, not a substitute for never passing secrets as
log arguments in the first place.

## Database migrations

```bash
python -m alembic upgrade head
```

Run this on deploy, before the new app version starts serving traffic.
`0003_invoice_delivery_agent` is the current schema (it also drops the
prior version's AR/GST tables — see `archive/deprecated/ARCHIVE_NOTES.md`).
Future migrations are additive — see `alembic/versions/`. Never hand-edit
a column in production outside a migration.

## Queues

Celery (`app/tasks/celery_app.py`) against Redis. One worker process
besides the web process (see `Procfile`); `app/tasks/delivery_tasks.py`
dispatches email/WhatsApp attempts and retries transient failures on the
fixed schedule in `docs/delivery-rules.md`. `task_acks_late=True` +
`worker_prefetch_multiplier=1` mean a worker crash mid-task re-delivers
the task rather than silently dropping it — combined with the
idempotency-key design, a redelivered task is safe to re-run.

## Storage

`STORAGE_PROVIDER=local` (default) writes to `STORAGE_LOCAL_DIR` — fine
for development, **not for production** (not durable, not shared across
instances). For production, implement a real S3-compatible adapter
against `app/services/storage/base.py` and register it in
`app/services/storage/factory.py`; invoice PDFs are stored privately with
short-lived signed URLs only, never public objects.

## Monitoring

- Structured JSON logs (`structlog`) on stdout — ship them to whatever
  log aggregator the host already uses.
- `GET /health` is the liveness/readiness probe; it reports which
  provider each category (`email_provider`, `whatsapp_provider`,
  `storage_provider`) currently resolves to, so a deploy that's still on
  `mock` in production is visible at a glance.
- No error-tracking provider is wired in this version (the prior
  version's Sentry integration was never built past documentation —
  nothing to carry over). Add one against `app/main.py` when needed.

## Backup

Once on real PostgreSQL: standard point-in-time-recovery backups. The
`audit_events` table is append-only by convention (never updated or
deleted by application code) — treat any gap in its history as a sign
something bypassed the audit service, not as expected behavior.

## Security checklist

- [ ] `JWT_SECRET` is a real random secret, rotated from the `.env.example` placeholder.
- [ ] `EMAIL_PROVIDER` and `WHATSAPP_PROVIDER` are set to real providers, not left on `mock`, before go-live.
- [ ] At least one real `InternalUser` with role `ADMIN` exists before relying on RBAC in production.
- [ ] Rate limiting on the public `/d/{token}` download route and the provider webhook routes.
- [ ] No secret, recipient email/phone, or document byte content ever appears in a log line, error response, or frontend URL.
- [ ] Object storage buckets are private; invoice document URLs are short-lived signed URLs only, never permanent public links.
- [ ] The WhatsApp utility/template message is approved by the provider (Twilio/Meta) before `WHATSAPP_PROVIDER=twilio` is used in production.
