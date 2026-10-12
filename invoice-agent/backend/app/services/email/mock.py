from __future__ import annotations

import uuid
from typing import Any

from app.services.email.base import EmailAdapter


class MockEmailAdapter(EmailAdapter):
    def __init__(self) -> None:
        self.sent_messages: dict[str, dict[str, Any]] = {}

    def send_invoice_email(
        self,
        *,
        to_email: str,
        subject: str,
        body_html: str,
        pdf_attachment_bytes: bytes | None = None,
        secure_download_url: str | None = None,
    ) -> str:
        message_id = f"MOCK-EMAIL-{uuid.uuid4().hex[:12]}"
        self.sent_messages[message_id] = {
            "to_email": to_email,
            "subject": subject,
            "has_attachment": pdf_attachment_bytes is not None,
            "secure_download_url": secure_download_url,
            "status": "sent",
        }
        return message_id

    def receive_delivery_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        message_id = payload.get("message_id", "")
        status = payload.get("status", "delivered")
        if message_id in self.sent_messages:
            self.sent_messages[message_id]["status"] = status
        return {"message_id": message_id, "status": status}

    def resend_invoice_email_with_authorization(
        self, *, original_message_id: str, authorized_by: str, **send_kwargs: Any
    ) -> str:
        if original_message_id not in self.sent_messages:
            raise LookupError(f"mock email adapter has no message {original_message_id}")
        return self.send_invoice_email(**send_kwargs)
