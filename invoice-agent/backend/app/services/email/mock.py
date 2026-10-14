from __future__ import annotations

import uuid
from typing import Any

from app.services.email.base import EmailProvider, EmailProviderEvent, EmailSendPayload
from app.services.provider_errors import PermanentProviderError, TransientProviderError


class MockEmailProvider(EmailProvider):
    name = "mock"

    def __init__(self) -> None:
        self.sent: dict[str, EmailSendPayload] = {}
        # Test-only hook: set to "transient" or "permanent" to simulate a
        # provider failure on the next send_invoice_email call.
        self.fail_mode: str | None = None

    def send_invoice_email(self, payload: EmailSendPayload) -> str:
        if self.fail_mode == "transient":
            raise TransientProviderError("simulated timeout", error_code="timeout")
        if self.fail_mode == "permanent":
            raise PermanentProviderError("simulated invalid recipient", error_code="invalid_recipient")

        message_id = f"MOCK-EMAIL-{uuid.uuid4().hex[:12]}"
        self.sent[message_id] = payload
        return message_id

    def verify_webhook(self, *, headers: dict[str, str], raw_body: bytes) -> bool:
        return True

    def handle_delivery_event(self, event: dict[str, Any]) -> EmailProviderEvent:
        return EmailProviderEvent(
            message_id=event["message_id"],
            event_type="delivered",
            occurred_at=event.get("occurred_at"),
            detail_safe={},
        )

    def handle_bounce_event(self, event: dict[str, Any]) -> EmailProviderEvent:
        return EmailProviderEvent(
            message_id=event["message_id"],
            event_type="bounced",
            occurred_at=event.get("occurred_at"),
            detail_safe={"bounce_type": event.get("bounce_type", "unknown")},
        )

    def handle_complaint_event(self, event: dict[str, Any]) -> EmailProviderEvent:
        return EmailProviderEvent(
            message_id=event["message_id"],
            event_type="complaint",
            occurred_at=event.get("occurred_at"),
            detail_safe={},
        )
