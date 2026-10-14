"""WhatsApp provider interface (spec §10). Notification-only in v1 — no
PDF attachment over WhatsApp. `send_invoice_notification` sends an
approved utility/template message, never free-form text, since
business-initiated WhatsApp messages require a pre-approved template.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class WhatsAppSendPayload:
    to_phone_e164: str
    recipient_name: str
    invoice_number_or_reference: str | None
    secure_link: str | None
    idempotency_key: str


@dataclass
class WhatsAppProviderEvent:
    message_id: str
    status: str  # accepted | sent | delivered | read | failed
    occurred_at: str | None
    detail_safe: dict[str, Any]


class WhatsAppProvider(ABC):
    name: str

    @abstractmethod
    def send_invoice_notification(self, payload: WhatsAppSendPayload) -> str:
        """Returns the provider's message ID."""
        ...

    @abstractmethod
    def verify_webhook(self, *, headers: dict[str, str], raw_body: bytes) -> bool:
        ...

    @abstractmethod
    def handle_status_event(self, event: dict[str, Any]) -> WhatsAppProviderEvent:
        ...
