"""Twilio WhatsApp adapter — the default real provider per spec §4/§10.
Sends via a pre-approved content template (`WHATSAPP_TEMPLATE_ID`); never
free-form text, since Twilio (like WhatsApp itself) requires an approved
template for business-initiated messages outside a user-initiated
session.

Inactive until `WHATSAPP_PROVIDER=twilio` and real credentials are set —
see app/services/whatsapp/factory.py.
"""

from __future__ import annotations

from typing import Any

from twilio.request_validator import RequestValidator
from twilio.rest import Client

from app.services.whatsapp.base import (
    WhatsAppProvider,
    WhatsAppProviderEvent,
    WhatsAppSendPayload,
)
from app.services.whatsapp.templates import build_template_variables


class TwilioWhatsAppProvider(WhatsAppProvider):
    name = "twilio"

    def __init__(
        self,
        *,
        account_sid: str,
        auth_token: str,
        from_number: str,
        template_id: str,
        support_email: str,
    ) -> None:
        self._client = Client(account_sid, auth_token)
        self._from_number = from_number
        self._template_id = template_id
        self._support_email = support_email
        self._validator = RequestValidator(auth_token)

    def send_invoice_notification(self, payload: WhatsAppSendPayload) -> str:
        variables = build_template_variables(
            recipient_name=payload.recipient_name,
            invoice_number_or_reference=payload.invoice_number_or_reference,
            secure_link=payload.secure_link,
            support_email=self._support_email,
        )
        message = self._client.messages.create(
            from_=f"whatsapp:{self._from_number}",
            to=f"whatsapp:{payload.to_phone_e164}",
            content_sid=self._template_id,
            content_variables=str(variables),
        )
        return message.sid

    def verify_webhook(self, *, headers: dict[str, str], raw_body: bytes) -> bool:
        signature = headers.get("X-Twilio-Signature", "")
        url = headers.get("X-Webhook-Url", "")
        form_params = _parse_form_urlencoded(raw_body)
        return self._validator.validate(url, form_params, signature)

    def handle_status_event(self, event: dict[str, Any]) -> WhatsAppProviderEvent:
        status_map = {
            "queued": "accepted",
            "sent": "sent",
            "delivered": "delivered",
            "read": "read",
            "failed": "failed",
            "undelivered": "failed",
        }
        twilio_status = event.get("MessageStatus", "sent")
        return WhatsAppProviderEvent(
            message_id=event.get("MessageSid", ""),
            status=status_map.get(twilio_status, "sent"),
            occurred_at=None,
            detail_safe={"provider_status": twilio_status},
        )


def _parse_form_urlencoded(raw_body: bytes) -> dict[str, str]:
    from urllib.parse import parse_qsl

    return dict(parse_qsl(raw_body.decode("utf-8")))
