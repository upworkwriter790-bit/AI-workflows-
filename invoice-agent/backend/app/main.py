from __future__ import annotations

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.environment)

app = FastAPI(title="Invoice Automation Agent", version="0.1.0")


@app.get("/health")
def health() -> dict:
    missing = settings.missing_live_invoicing_fields()
    return {
        "status": "ok",
        "environment": settings.environment,
        "live_invoicing_ready": len(missing) == 0,
        "missing_company_config": missing,
        "crm_provider": settings.crm_provider,
        "erp_provider": settings.erp_provider,
        "email_provider": settings.email_provider,
        "llm_provider": settings.llm_provider,
    }
