"""Email provider interface (spec §9). Attaches an already-existing PDF —
never generates or edits one. `verify_webhook` and the `handle_*_event`
methods let the webhook route stay provider-agnostic: it verifies the
signature and normalizes the payload here, then the workflow/task layer
only ever sees a normalized event.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class EmailSendPayload:
    to_email: str
    to_name: str
    subject: str
    body_text: str
    pdf_attachment_bytes: bytes | None
    pdf_attachment_filename: str
    idempotency_key: str


@dataclass
class EmailProviderEvent:
    message_id: str
    event_type: str  # delivered | bounced | complaint | failed | sent
    occurred_at: str | None
    detail_safe: dict[str, Any]


class EmailProvider(ABC):
    name: str

    @abstractmethod
    def send_invoice_email(self, payload: EmailSendPayload) -> str:
        """Returns the provider's message ID."""
        ...

    @abstractmethod
    def verify_webhook(self, *, headers: dict[str, str], raw_body: bytes) -> bool:
        ...

    @abstractmethod
    def handle_delivery_event(self, event: dict[str, Any]) -> EmailProviderEvent:
        ...

    @abstractmethod
    def handle_bounce_event(self, event: dict[str, Any]) -> EmailProviderEvent:
        ...

    @abstractmethod
    def handle_complaint_event(self, event: dict[str, Any]) -> EmailProviderEvent:
        ...
