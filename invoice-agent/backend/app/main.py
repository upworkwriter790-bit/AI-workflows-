from __future__ import annotations

from fastapi import FastAPI

from app.api.deliveries import router as deliveries_router
from app.api.downloads import router as downloads_router
from app.api.generated_invoices import router as generated_invoices_router
from app.api.product_catalog import router as product_catalog_router
from app.api.provider_webhooks import router as provider_webhooks_router
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.app_env)

app = FastAPI(title="Invoice Delivery Agent", version="0.1.0")
app.include_router(deliveries_router)
app.include_router(generated_invoices_router)
app.include_router(product_catalog_router)
app.include_router(downloads_router)
app.include_router(provider_webhooks_router)


@app.get("/health")
def health() -> dict:
    missing_seller_fields = settings.missing_seller_identity_fields()
    return {
        "status": "ok",
        "app_env": settings.app_env,
        "email_provider": settings.email_provider,
        "whatsapp_provider": settings.whatsapp_provider,
        "storage_provider": settings.storage_provider,
        "generated_invoices_ready": len(missing_seller_fields) == 0,
        "missing_seller_config": missing_seller_fields,
    }
