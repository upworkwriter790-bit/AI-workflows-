from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.customers import router as customers_router
from app.api.deliveries import router as deliveries_router
from app.api.downloads import router as downloads_router
from app.api.generated_invoices import router as generated_invoices_router
from app.api.product_catalog import router as product_catalog_router
from app.api.provider_webhooks import router as provider_webhooks_router
from app.api.quick_create import router as quick_create_router
from app.api.users import router as users_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging

configure_logging(get_settings().app_env)

app = FastAPI(title="Invoice Delivery Agent", version="0.1.0")

# Permissive CORS: this is a local/self-hosted deliverable where the
# plain-HTML frontend is typically opened from a different origin
# (file:// or a static-file port) than this API. Tighten this before
# any real deployment.
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(deliveries_router)
app.include_router(generated_invoices_router)
app.include_router(quick_create_router)
app.include_router(customers_router)
app.include_router(product_catalog_router)
app.include_router(downloads_router)
app.include_router(provider_webhooks_router)


@app.on_event("startup")
def _seed_default_admin() -> None:
    """First-run convenience only — see Settings.default_admin_email."""
    from app.core.auth import hash_password
    from app.db.session import SessionLocal
    from app.models.internal_user import InternalUser

    settings = get_settings()
    db = SessionLocal()
    try:
        if db.query(InternalUser).count() == 0:
            db.add(
                InternalUser(
                    email=settings.default_admin_email.strip().lower(),
                    display_name="Default Admin",
                    password_hash=hash_password(settings.default_admin_password),
                    role="ADMIN",
                )
            )
            db.commit()
    finally:
        db.close()


@app.get("/health")
def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict:
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
