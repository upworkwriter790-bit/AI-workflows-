"""Email adapter interface. Per spec §14: track delivery/bounce state
explicitly, never resend without authorization, never claim payment success
unless CRM payment_status really is PAID.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class EmailAdapter(ABC):
    @abstractmethod
    def send_invoice_email(
        self,
        *,
        to_email: str,
        subject: str,
        body_html: str,
        pdf_attachment_bytes: bytes | None = None,
        secure_download_url: str | None = None,
    ) -> str:
        """Returns the provider's message ID."""
        ...

    @abstractmethod
    def receive_delivery_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Normalizes a provider delivery webhook into
        {'message_id': str, 'status': 'sent'|'delivered'|'bounced'|'failed'}.
        """
        ...

    @abstractmethod
    def resend_invoice_email_with_authorization(
        self, *, original_message_id: str, authorized_by: str, **send_kwargs: Any
    ) -> str:
        ...
