from __future__ import annotations

from app.core.config import Settings
from app.services.whatsapp.base import WhatsAppProvider
from app.services.whatsapp.mock import MockWhatsAppProvider


def get_whatsapp_provider(settings: Settings) -> WhatsAppProvider:
    if settings.whatsapp_provider == "mock":
        return MockWhatsAppProvider()

    if settings.whatsapp_provider == "twilio":
        missing = [
            name
            for name, value in {
                "WHATSAPP_ACCOUNT_SID": settings.whatsapp_account_sid,
                "WHATSAPP_AUTH_TOKEN": settings.whatsapp_auth_token,
                "WHATSAPP_FROM_NUMBER": settings.whatsapp_from_number,
                "WHATSAPP_TEMPLATE_ID": settings.whatsapp_template_id,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(f"WHATSAPP_PROVIDER=twilio requires: {', '.join(missing)}")

        from app.services.whatsapp.twilio_provider import TwilioWhatsAppProvider

        return TwilioWhatsAppProvider(
            account_sid=settings.whatsapp_account_sid,
            auth_token=settings.whatsapp_auth_token,
            from_number=settings.whatsapp_from_number,
            template_id=settings.whatsapp_template_id,
            support_email=settings.support_email or "",
        )

    raise NotImplementedError(
        f"WHATSAPP_PROVIDER={settings.whatsapp_provider!r} has no adapter yet. "
        "Implement one under app/services/whatsapp/ matching WhatsAppProvider "
        "and register it here."
    )
