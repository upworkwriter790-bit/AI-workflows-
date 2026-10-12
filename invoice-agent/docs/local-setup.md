# Local setup (no Docker)

This replaces what would otherwise be a `docker-compose.yml`. Phase 1 needs
nothing beyond Python + SQLite (see `README.md` quick start). Postgres and
Redis are only needed from Phase 2 onward, once the webhook/workflow/queue
code exists.

## PostgreSQL (native install, pick your OS)

```bash
# Debian/Ubuntu
sudo apt install postgresql
sudo -u postgres createuser invoice_agent --pwprompt
sudo -u postgres createdb invoice_agent -O invoice_agent

# macOS (Homebrew)
brew install postgresql@16
brew services start postgresql@16
createuser invoice_agent --pwprompt
createdb invoice_agent -O invoice_agent
```

Then in `.env`:

```
DATABASE_URL=postgresql+psycopg://invoice_agent:<password>@localhost:5432/invoice_agent
```

## Redis (native install)

```bash
# Debian/Ubuntu
sudo apt install redis-server

# macOS (Homebrew)
brew install redis
brew services start redis
```

Default `.env` value (`redis://localhost:6379/0`) works as-is against a
default local install.

## If you'd rather not install Postgres/Redis locally at all

Point `DATABASE_URL`/`REDIS_URL` at any managed instance you already have
(a cloud free tier, a shared dev database, etc.) — nothing in this codebase
assumes localhost. Phase 1's test suite and `alembic upgrade head` both
work against plain SQLite with zero external services, which is enough to
validate the scaffold before any real infrastructure exists.
