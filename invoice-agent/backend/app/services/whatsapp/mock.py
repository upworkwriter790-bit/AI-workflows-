from __future__ import annotations

import uuid
from typing import Any

from app.services.provider_errors import PermanentProviderError, TransientProviderError
from app.services.whatsapp.base import (
    WhatsAppProvider,
    WhatsAppProviderEvent,
    WhatsAppSendPayload,
)


class MockWhatsAppProvider(WhatsAppProvider):
    name = "mock"

    def __init__(self) -> None:
        self.sent: dict[str, WhatsAppSendPayload] = {}
        self.fail_mode: str | None = None

    def send_invoice_notification(self, payload: WhatsAppSendPayload) -> str:
        if self.fail_mode == "transient":
            raise TransientProviderError("simulated 5xx", error_code="provider_5xx")
        if self.fail_mode == "permanent":
            raise PermanentProviderError("simulated template config error", error_code="template_error")

        message_id = f"MOCK-WHATSAPP-{uuid.uuid4().hex[:12]}"
        self.sent[message_id] = payload
        return message_id

    def verify_webhook(self, *, headers: dict[str, str], raw_body: bytes) -> bool:
        return True

    def handle_status_event(self, event: dict[str, Any]) -> WhatsAppProviderEvent:
        return WhatsAppProviderEvent(
            message_id=event["message_id"],
            status=event.get("status", "sent"),
            occurred_at=event.get("occurred_at"),
            detail_safe={},
        )
